"""
API endpoints for journey management
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Optional
from datetime import datetime

from app.models.schemas import (
    JourneyStartRequest,
    JourneyStartResponse,
    GPSPoint,
    GPSPointResponse,
    JourneyState,
    DeviationStatus,
    ErrorResponse
)
from app.services.route_service import route_service
from app.services.journey_service import journey_service
from app.services.geocoding_service import geocoding_service
from app.services.deviation_detector import DeviationDetector
from app.services.route_tracker import RouteTracker
from app.services.tracking_service import tracking_service
from app.utils.geometry import calculate_progress_along_route
from app.utils.logger import logger

logger.info("=== API routes module loaded with deviation detection v2 ===")

router = APIRouter(prefix="/api/journey", tags=["journey"])


@router.post(
    "/start",
    response_model=JourneyStartResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def start_journey(request: JourneyStartRequest) -> JourneyStartResponse:
    """
    Start a new journey by fetching routes and creating database entry
    
    This endpoint:
    1. Fetches route alternatives from Mapbox
    2. Creates a journey record in the database
    3. Stores route alternatives
    4. Returns journey_id and routes
    """
    try:
        logger.info(
            f"Starting journey: {request.origin.lat},{request.origin.lng} -> "
            f"{request.destination.lat},{request.destination.lng} ({request.travel_mode})"
        )
        
        # Fetch routes from Mapbox
        routes = await route_service.fetch_routes(
            request.origin,
            request.destination,
            request.travel_mode
        )
        
        if not routes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No routes found between the given locations"
            )
        
        # Create journey in database
        journey_id = await journey_service.create_journey(
            request.origin,
            request.destination,
            request.travel_mode,
            routes
        )
        
        # Start tracking in background
        tracking_service.start_journey_tracking(
            journey_id=journey_id,
            routes=routes,
            travel_mode=request.travel_mode,
            origin=(request.origin.lat, request.origin.lng),
            destination=(request.destination.lat, request.destination.lng)
        )
        
        start_time = datetime.now()
        
        logger.info(f"Journey {journey_id} started successfully with {len(routes)} route(s)")
        
        return JourneyStartResponse(
            journey_id=journey_id,
            routes=routes,
            start_time=start_time,
            message=f"Journey started successfully with {len(routes)} route alternative(s)"
        )
        
    except ValueError as e:
        logger.error(f"Validation error starting journey: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting journey: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start journey. Please try again."
        )


@router.post(
    "/{journey_id}/gps",
    response_model=GPSPointResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def submit_gps_point(
    journey_id: str,
    gps_point: GPSPoint
) -> GPSPointResponse:
    """
    Submit a GPS point for tracking
    
    This endpoint:
    1. Validates the journey exists
    2. Stores the GPS point
    3. Adds point to tracking pipeline (real-time updates & deviation detection)
    """
    try:
        # Verify journey exists
        journey = await journey_service.get_journey(journey_id)
        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Journey {journey_id} not found"
            )
        
        # Check if journey is active
        if journey["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journey {journey_id} is not active (status: {journey['status']})"
            )
        
        # Store GPS point (persistence)
        await journey_service.store_gps_point(journey_id, gps_point)
        
        logger.debug(
            f"GPS point received for journey {journey_id}: "
            f"({gps_point.lat:.4f}, {gps_point.lng:.4f})"
        )
        
        # Add to tracking pipeline (real-time updates, map matching, deviation detection)
        # This is async and now returns immediately after enqueuing background task
        tracking_result = await tracking_service.add_gps_point(journey_id, gps_point)
        
        if tracking_result.get("status") == "error":
            logger.warning(f"Tracking service error: {tracking_result.get('message')}")
            # We don't fail the request as persistence succeeded, but we acknowledge the issue
        
        return GPSPointResponse(
            status="success",
            journey_id=journey_id,
            message="GPS point received and processed",
            batch_processed=tracking_result.get("batch_processed", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting GPS point: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process GPS point"
        )


@router.get(
    "/{journey_id}",
    response_model=JourneyState,
    responses={
        404: {"model": ErrorResponse}
    }
)
async def get_journey_status(journey_id: str) -> JourneyState:
    """
    Get current status of a journey
    
    Returns journey state including:
    - Current status
    - Route probabilities (using RouteTracker)
    - Progress percentage (calculated from GPS points)
    - Deviation status (using DeviationDetector)
    """
    try:
        logger.info(f"Fetching status for journey {journey_id}")
        
        # Get journey data
        journey = await journey_service.get_journey(journey_id)
        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Journey {journey_id} not found"
            )
        
        # Get routes
        routes = await journey_service.get_routes(journey_id)
        logger.debug(f"Found {len(routes)} routes for journey")
        
        # Get recent GPS points (last 10 for context)
        recent_gps = await journey_service.get_recent_gps_points(journey_id, limit=10)
        last_gps = recent_gps[-1] if recent_gps else None
        logger.info(f"Found {len(recent_gps)} GPS points for journey")
        
        # If no GPS points yet, return default status
        if not recent_gps:
            logger.debug("No GPS points found, returning default status")
            deviation_status = DeviationStatus(
                spatial="ON_ROUTE",
                temporal="ON_TIME",
                directional="TOWARD_DEST",
                severity="normal"
            )
            
            route_probabilities = {
                f"route_{i}": 1.0 / len(routes) if routes else 0.0
                for i in range(len(routes))
            }
            
            return JourneyState(
                journey_id=journey_id,
                current_status=journey["status"],
                route_probabilities=route_probabilities,
                progress_percentage=0.0,
                time_deviation=0.0,
                last_gps=last_gps,
                deviation_status=deviation_status
            )
        
        # Initialize deviation detector and route tracker
        logger.debug("Initializing deviation detector and route tracker")
        try:
            detector = DeviationDetector(routes)
            tracker = RouteTracker(routes)
            
            # Update route tracker with recent GPS points
            logger.debug(f"Updating route tracker with {len(recent_gps)} GPS points")
            for gps in recent_gps:
                tracker.update_probabilities(gps, tracker.probabilities)
            
            # Get most likely route
            route_probabilities = tracker.probabilities
            expected_route = tracker.get_most_likely_route()
            logger.info(f"Most likely route: {expected_route.route_id} with probabilities: {route_probabilities}")
            
        except Exception as e:
            logger.error(f"Error in route tracking: {e}", exc_info=True)
            # Fall back to equal probabilities
            route_probabilities = {
                f"route_{i}": 1.0 / len(routes) if routes else 0.0
                for i in range(len(routes))
            }
            expected_route = routes[0] if routes else None
            if not expected_route:
                raise
        
        # Calculate progress along route
        try:
            start_point = (journey["origin_lat"], journey["origin_lng"])
            current_point = (last_gps.lat, last_gps.lng)
            route_coords = [(lat, lng) for lng, lat in expected_route.geometry]
            progress_meters = calculate_progress_along_route(
                start_point,
                current_point,
                route_coords
            )
            progress_percentage = (progress_meters / expected_route.distance_meters) * 100
            logger.debug(f"Progress: {progress_meters:.0f}m ({progress_percentage:.1f}%)")
        except Exception as e:
            logger.error(f"Error calculating progress: {e}", exc_info=True)
            progress_meters = 0.0
            progress_percentage = 0.0
        
        # Check spatial deviation
        try:
            current_speed = last_gps.speed if last_gps.speed is not None else 0.0
            spatial, distance_from_route, _ = detector.check_spatial_deviation(
                last_gps,
                current_speed
            )
            logger.debug(f"Spatial deviation: {spatial}, distance: {distance_from_route:.1f}m")
        except Exception as e:
            logger.error(f"Error checking spatial deviation: {e}", exc_info=True)
            spatial = "ON_ROUTE"
            distance_from_route = 0.0
        
        # Check temporal deviation
        try:
            start_time = datetime.fromisoformat(journey["start_time"])
            # Ensure both datetimes have consistent timezone handling
            if start_time.tzinfo is None and last_gps.timestamp.tzinfo is not None:
                # Make start_time timezone-aware (assume UTC)
                from datetime import timezone
                start_time = start_time.replace(tzinfo=timezone.utc)
            elif start_time.tzinfo is not None and last_gps.timestamp.tzinfo is None:
                # Make timestamp timezone-naive
                start_time = start_time.replace(tzinfo=None)
            current_time = last_gps.timestamp
            
            # Calculate stopped duration (if speed < 1 km/h for multiple points)
            stopped_duration = 0.0
            if len(recent_gps) >= 2:
                stopped_count = sum(1 for gps in recent_gps if (gps.speed or 0) < 1.0)
                if stopped_count >= 2:
                    # Estimate stopped duration from last few points
                    time_span = (recent_gps[-1].timestamp - recent_gps[0].timestamp).total_seconds()
                    stopped_duration = (stopped_count / len(recent_gps)) * time_span
            
            temporal, time_deviation = detector.check_temporal_deviation(
                journey_start_time=start_time,
                current_time=current_time,
                progress_meters=progress_meters,
                expected_route=expected_route,
                current_speed=current_speed,
                stopped_duration=stopped_duration
            )
            logger.debug(f"Temporal deviation: {temporal}, time dev: {time_deviation:.0f}s")
        except Exception as e:
            logger.error(f"Error checking temporal deviation: {e}", exc_info=True)
            temporal = "ON_TIME"
            time_deviation = 0.0
        
        # Check directional deviation
        try:
            destination = (journey["destination_lat"], journey["destination_lng"])
            directional = detector.check_directional_deviation(
                current_point=last_gps,
                destination=destination,
                expected_route=expected_route,
                recent_points=recent_gps
            )
            logger.debug(f"Directional deviation: {directional}")
        except Exception as e:
            logger.error(f"Error checking directional deviation: {e}", exc_info=True)
            directional = "TOWARD_DEST"
        
        # Determine overall severity
        try:
            severity = detector.determine_severity(spatial, temporal, directional)
            logger.info(f"Overall severity: {severity}")
        except Exception as e:
            logger.error(f"Error determining severity: {e}", exc_info=True)
            severity = "normal"
        
        deviation_status = DeviationStatus(
            spatial=spatial,
            temporal=temporal,
            directional=directional,
            severity=severity
        )
        
        return JourneyState(
            journey_id=journey_id,
            current_status=journey["status"],
            route_probabilities=route_probabilities,
            progress_percentage=progress_percentage,
            time_deviation=time_deviation,
            last_gps=last_gps,
            deviation_status=deviation_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching journey status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch journey status"
        )


@router.put(
    "/{journey_id}/complete",
    responses={
        404: {"model": ErrorResponse}
    }
)
async def complete_journey(journey_id: str) -> Dict[str, str]:
    """
    Mark a journey as completed
    """
    try:
        journey = await journey_service.get_journey(journey_id)
        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Journey {journey_id} not found"
            )
        
        await journey_service.update_journey_status(
            journey_id,
            "completed",
            datetime.now()
        )
        
        await tracking_service.complete_journey(journey_id)
        
        logger.info(f"Journey {journey_id} marked as completed")
        
        return {
            "status": "success",
            "message": f"Journey {journey_id} completed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing journey: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete journey"
        )


# Geocoding endpoints
geocoding_router = APIRouter(prefix="/api/geocoding", tags=["geocoding"])


@geocoding_router.get("/search")
async def search_location(
    q: str,
    limit: int = 5
) -> Dict:
    """
    Search for locations by name (forward geocoding)
    
    Args:
        q: Location query (e.g., "Delhi", "New York", "Mumbai")
        limit: Maximum number of results (default: 5, max: 10)
    
    Returns:
        List of matching locations with coordinates
    
    Example:
        GET /api/geocoding/search?q=Delhi&limit=5
    """
    try:
        if not q or len(q.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query must be at least 2 characters long"
            )
        
        results = await geocoding_service.geocode_location(q, limit=limit)
        
        return {
            "query": q,
            "results": results,
            "count": len(results)
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error searching location '{q}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search location"
        )


@geocoding_router.get("/autocomplete")
async def autocomplete_location(
    q: str,
    limit: int = 5,
    lat: Optional[float] = None,
    lng: Optional[float] = None
) -> Dict:
    """
    Get autocomplete suggestions for location search
    
    Args:
        q: Partial location query
        limit: Maximum number of suggestions
        lat, lng: Optional coordinates to bias results
    
    Returns:
        List of autocomplete suggestions
    """
    try:
        if not q or len(q.strip()) < 1:
            return {"query": q, "suggestions": [], "count": 0}
        
        proximity = (lat, lng) if lat is not None and lng is not None else None
        
        suggestions = await geocoding_service.autocomplete_location(
            q,
            limit=limit,
            proximity=proximity  # type: ignore
        )
        
        return {
            "query": q,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Error autocompleting location '{q}': {e}")
        return {"query": q, "suggestions": [], "count": 0}

