"""
Unified Tracking Service

Orchestrates the complete GPS tracking pipeline:
1. Receives GPS points
2. Buffers for batch processing
3. Performs map matching
4. Runs deviation detection
5. Updates route probabilities
6. Stores deviation events
7. Broadcasts updates via WebSocket
"""
import asyncio
import json
from typing import List, Optional, Dict
from datetime import datetime

from app.models.schemas import GPSPoint, Route
from app.services.gps_buffer import GPSBufferManager
from app.services.map_matching import map_matching_service
from app.services.deviation_detector import DeviationDetector
from app.services.route_tracker import RouteTracker
from app.services.journey_service import journey_service
from app.services.journey_store import journey_store
from app.services.websocket_manager import websocket_manager
from app.database import execute_update
from app.utils.logger import logger


class TrackingService:
    """
    Unified service for GPS tracking and deviation detection
    
    Maintains state for all active journeys and coordinates
    the entire tracking pipeline.
    """
    
    def __init__(self):
        """Initialize tracking service"""
        # Journey state tracking
        self.active_journeys: Dict[str, dict] = {}
        
        # Initialize GPS buffer manager with batch callback
        self.buffer_manager = GPSBufferManager(self._process_batch)
        
        logger.info("Initialized Unified Tracking Service with Redis backing")

    async def _load_journey_from_store(self, journey_id: str) -> bool:
        """
        Load journey state from Redis into local cache
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            True if loaded, else False
        """
        if journey_id in self.active_journeys:
            return True
        
        state = await journey_store.get_journey_state(journey_id)
        if not state:
            return False
        
        routes = [Route(**r) for r in state.get("routes", [])]
        start_time = (
            datetime.fromisoformat(state["start_time"])
            if state.get("start_time")
            else datetime.now()
        )
        
        last_deviation = state.get("last_deviation")
        if last_deviation and last_deviation.get("timestamp"):
            try:
                last_deviation["timestamp"] = datetime.fromisoformat(last_deviation["timestamp"])
            except Exception:
                pass
        
        self.active_journeys[journey_id] = {
            "routes": routes,
            "travel_mode": state.get("travel_mode"),
            "origin": tuple(state.get("origin", [0, 0])),
            "destination": tuple(state.get("destination", [0, 0])),
            "start_time": start_time,
            "detector": DeviationDetector(routes),
            "tracker": RouteTracker(routes),
            "total_points_received": state.get("total_points_received", 0),
            "batches_processed": state.get("batches_processed", 0),
            "last_deviation": last_deviation
        }
        
        logger.info(f"Loaded journey {journey_id} from Redis")
        return True

    def _schedule_save(self, journey_id: str, state: dict) -> None:
        """
        Schedule an async save of journey state to Redis
        
        Args:
            journey_id: Journey UUID
            state: Tracking state dict
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(journey_store.save_journey_state(journey_id, state))
        except RuntimeError:
            asyncio.run(journey_store.save_journey_state(journey_id, state))
        except Exception as e:
            logger.error(f"Failed to schedule journey save: {e}", exc_info=True)
    
    def start_journey_tracking(
        self,
        journey_id: str,
        routes: List[Route],
        travel_mode: str,
        origin: tuple,
        destination: tuple
    ) -> None:
        """
        Start tracking for a new journey
        
        Args:
            journey_id: Journey UUID
            routes: List of route alternatives
            travel_mode: driving, walking, cycling
            origin: (lat, lng) tuple
            destination: (lat, lng) tuple
        """
        if journey_id in self.active_journeys:
            logger.warning(f"Journey {journey_id} already being tracked")
            return
        
        # Initialize tracking state
        state = {
            "routes": routes,
            "travel_mode": travel_mode,
            "origin": origin,
            "destination": destination,
            "start_time": datetime.now(),
            "detector": DeviationDetector(routes),
            "tracker": RouteTracker(routes),
            "total_points_received": 0,
            "batches_processed": 0,
            "last_deviation": None
        }
        
        self.active_journeys[journey_id] = state
        self._schedule_save(journey_id, state)
        
        logger.info(
            f"Started tracking for journey {journey_id} "
            f"({len(routes)} routes, mode: {travel_mode})"
        )
    
    async def add_gps_point(self, journey_id: str, gps_point: GPSPoint) -> dict:
        """
        Add GPS point to tracking pipeline
        
        Args:
            journey_id: Journey UUID
            gps_point: GPS point data
        
        Returns:
            Dictionary with processing status
        """
        if journey_id not in self.active_journeys:
            loaded = await self._load_journey_from_store(journey_id)
            if not loaded:
                logger.warning(f"Journey {journey_id} not being tracked")
                return {
                    "status": "error",
                    "message": "Journey not being tracked"
                }
        
        # Update point count
        self.active_journeys[journey_id]["total_points_received"] += 1
        self._schedule_save(journey_id, self.active_journeys[journey_id])
        
        # Broadcast GPS update immediately for real-time UI feedback
        await websocket_manager.broadcast_gps_update(journey_id, {
            "lat": gps_point.lat,
            "lng": gps_point.lng,
            "timestamp": gps_point.timestamp.isoformat(),
            "speed": gps_point.speed,
            "bearing": gps_point.bearing,
            "accuracy": gps_point.accuracy
        })

        # Add to buffer (may trigger batch processing)
        batch_processed = await self.buffer_manager.add_point(journey_id, gps_point)
        
        return {
            "status": "success",
            "batch_processed": batch_processed,
            "buffer_stats": self.buffer_manager.get_buffer_stats(journey_id)
        }
    
    async def _process_batch(self, journey_id: str, gps_points: List[GPSPoint]) -> None:
        """
        Process a batch of GPS points (callback from buffer manager)
        
        Args:
            journey_id: Journey UUID
            gps_points: Batch of GPS points
        """
        if journey_id not in self.active_journeys:
            loaded = await self._load_journey_from_store(journey_id)
            if not loaded:
                logger.error(f"Cannot process batch: journey {journey_id} not tracked")
                return
        
        journey_state = self.active_journeys[journey_id]
        journey_state["batches_processed"] += 1
        batch_num = journey_state["batches_processed"]
        
        logger.info(
            f"Processing batch #{batch_num} for journey {journey_id} "
            f"({len(gps_points)} points)"
        )
        
        try:
            # Step 1: Map matching
            matched_coords, is_matched = await map_matching_service.match_trace_with_fallback(
                gps_points,
                journey_state["travel_mode"]
            )
            
            logger.debug(
                f"Map matching: {'SUCCESS' if is_matched else 'FALLBACK'} "
                f"({len(matched_coords)} coords)"
            )
            
            # Step 2: Update route probabilities
            tracker = journey_state["tracker"]
            for gps in gps_points:
                tracker.update_probabilities(gps, tracker.probabilities)
            
            route_probabilities = tracker.probabilities
            most_likely_route = tracker.get_most_likely_route()
            
            logger.info(
                f"Route probabilities: {', '.join([f'{k}={v:.2%}' for k, v in route_probabilities.items()])}"
            )
            
            # Step 3: Deviation detection on last point
            last_point = gps_points[-1]
            detector = journey_state["detector"]
            
            # Spatial deviation
            current_speed = last_point.speed if last_point.speed is not None else 0.0
            spatial, distance, closest_route = detector.check_spatial_deviation(
                last_point,
                current_speed
            )
            
            # Temporal deviation
            journey_data = await journey_service.get_journey(journey_id)
            if journey_data is None:
                logger.error(f"Journey {journey_id} not found in database")
                return
            
            # Handle start_time - could be string (PostgreSQL) or datetime (SQLite)
            start_time = journey_data["start_time"]
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            current_time = last_point.timestamp
            # Ensure both datetimes have consistent timezone handling
            if start_time.tzinfo is None and current_time.tzinfo is not None:
                # Make start_time timezone-aware (assume UTC)
                from datetime import timezone
                start_time = start_time.replace(tzinfo=timezone.utc)
            elif start_time.tzinfo is not None and current_time.tzinfo is None:
                # Make timestamp timezone-naive
                start_time = start_time.replace(tzinfo=None)
            
            # Calculate stopped duration
            stopped_duration = 0.0
            if len(gps_points) >= 2:
                stopped_count = sum(1 for gps in gps_points if (gps.speed or 0) < 1.0)
                if stopped_count >= 2:
                    time_span = (gps_points[-1].timestamp - gps_points[0].timestamp).total_seconds()
                    stopped_duration = (stopped_count / len(gps_points)) * time_span
            
            # Estimate progress (simplified - using distance from origin)
            from app.utils.geometry import haversine_distance
            progress_meters = haversine_distance(
                journey_state["origin"],
                (last_point.lat, last_point.lng)
            )
            
            temporal, time_deviation = detector.check_temporal_deviation(
                start_time,
                current_time,
                progress_meters,
                most_likely_route,
                current_speed,
                stopped_duration
            )
            
            # Directional deviation
            directional = detector.check_directional_deviation(
                last_point,
                journey_state["destination"],
                most_likely_route,
                gps_points
            )
            
            # Overall severity
            severity = detector.determine_severity(spatial, temporal, directional)
            
            logger.info(
                f"Deviation: {spatial}, {temporal}, {directional} -> {severity.upper()}"
            )
            
            # Step 4: Store deviation event in database
            deviation_event = {
                "journey_id": journey_id,
                "timestamp": last_point.timestamp.isoformat(),
                "severity": severity,
                "spatial_status": spatial,
                "temporal_status": temporal,
                "directional_status": directional,
                "distance_from_route": distance,
                "time_deviation": time_deviation,
                "route_probabilities": json.dumps(route_probabilities)
            }
            
            await self._store_deviation_event(deviation_event)
            
            # Update journey state
            journey_state["last_deviation"] = {
                "spatial": spatial,
                "temporal": temporal,
                "directional": directional,
                "severity": severity,
                "timestamp": last_point.timestamp
            }
            
            await journey_store.save_journey_state(journey_id, journey_state)
            
            # Step 5: Broadcast via WebSocket
            await websocket_manager.broadcast_deviation_update(journey_id, deviation_event)
            
            # Note: broadcast_gps_update moved to add_gps_point for real-time feedback
            
            # Broadcast batch processed notification
            await websocket_manager.broadcast_batch_processed(journey_id, {
                "batch_number": batch_num,
                "points_processed": len(gps_points),
                "map_matched": is_matched
            })
            
            logger.info(f"Batch #{batch_num} processing complete for journey {journey_id}")
            
        except Exception as e:
            logger.error(
                f"Error processing batch for journey {journey_id}: {e}",
                exc_info=True
            )
    
    async def _store_deviation_event(self, event: dict) -> None:
        """
        Store deviation event in database
        
        Args:
            event: Deviation event data
        """
        try:
            timestamp = event["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)

            await execute_update("""
                INSERT INTO deviation_events 
                (journey_id, timestamp, severity, spatial_status, temporal_status, 
                 directional_status, distance_from_route, time_deviation, route_probabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["journey_id"],
                timestamp,
                event["severity"],
                event["spatial_status"],
                event["temporal_status"],
                event["directional_status"],
                event["distance_from_route"],
                event["time_deviation"],
                event["route_probabilities"]
            ))
            
            logger.debug(f"Stored deviation event for journey {event['journey_id']}")
            
        except Exception as e:
            logger.error(f"Error storing deviation event: {e}", exc_info=True)
    
    async def complete_journey(self, journey_id: str) -> None:
        """
        Complete tracking for a journey
        
        Args:
            journey_id: Journey UUID
        """
        if journey_id not in self.active_journeys:
            loaded = await self._load_journey_from_store(journey_id)
            if not loaded:
                logger.warning(f"Journey {journey_id} not being tracked")
                await journey_store.delete_journey_state(journey_id)
                return
        
        # Flush any remaining GPS points
        await self.buffer_manager.flush_buffer(journey_id)
        
        # Get stats
        stats = self.active_journeys[journey_id]
        logger.info(
            f"Completed journey {journey_id}: "
            f"{stats['total_points_received']} points, "
            f"{stats['batches_processed']} batches"
        )
        
        # Cleanup
        self.buffer_manager.remove_buffer(journey_id)
        del self.active_journeys[journey_id]
        await journey_store.delete_journey_state(journey_id)
    
    def get_journey_stats(self, journey_id: str) -> Optional[dict]:
        """
        Get tracking statistics for a journey
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            Dictionary with stats or None if not tracked
        """
        if journey_id not in self.active_journeys:
            return None
        
        stats = self.active_journeys[journey_id].copy()
        
        # Remove complex objects
        stats.pop("detector", None)
        stats.pop("tracker", None)
        stats.pop("routes", None)
        
        # Add buffer stats
        buffer_stats = self.buffer_manager.get_buffer_stats(journey_id)
        if buffer_stats:
            stats["buffer"] = buffer_stats
        
        return stats
    
    def get_active_journey_count(self) -> int:
        """
        Get number of actively tracked journeys
        
        Returns:
            Number of journeys
        """
        return len(self.active_journeys)


# Global instance
tracking_service = TrackingService()
