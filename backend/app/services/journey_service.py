"""
Journey management service
"""
import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional

from app.models.schemas import LocationPoint, Route, GPSPoint
from app.database import get_db, execute_query, execute_update
from app.utils.logger import logger


class JourneyService:
    """Service for managing journeys and their data"""
    
    async def create_journey(
        self,
        origin: LocationPoint,
        destination: LocationPoint,
        travel_mode: str,
        routes: List[Route]
    ) -> str:
        """
        Create a new journey in the database
        
        Args:
            origin: Starting location
            destination: Ending location
            travel_mode: 'driving' or 'walking'
            routes: List of route alternatives
        
        Returns:
            journey_id (UUID string)
        """
        journey_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            async with get_db() as conn:
                # Insert journey
                await conn.execute("""
                    INSERT INTO journeys 
                    (id, origin_lat, origin_lng, destination_lat, destination_lng, 
                     travel_mode, start_time, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    journey_id,
                    origin.lat, origin.lng,
                    destination.lat, destination.lng,
                    travel_mode,
                    start_time.isoformat(),
                    'active'
                ))
                
                # Insert routes
                for route in routes:
                    # Convert geometry to JSON string
                    geometry_json = json.dumps(route.geometry)
                    
                    await conn.execute("""
                        INSERT INTO routes 
                        (journey_id, route_index, geometry, distance_meters, 
                         duration_seconds, summary)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        journey_id,
                        route.route_index,
                        geometry_json,
                        route.distance_meters,
                        route.duration_seconds,
                        route.summary
                    ))
                
                await conn.commit()
                
            logger.info(
                f"Created journey {journey_id} with {len(routes)} routes "
                f"({travel_mode} mode)"
            )
            
            return journey_id
            
        except Exception as e:
            logger.error(f"Error creating journey: {e}")
            raise
    
    async def get_journey(self, journey_id: str) -> Optional[Dict]:
        """
        Get journey details by ID
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            Journey data as dictionary, or None if not found
        """
        try:
            results = await execute_query(
                "SELECT * FROM journeys WHERE id = ?",
                (journey_id,)
            )
            
            if not results:
                logger.warning(f"Journey {journey_id} not found")
                return None
            
            return results[0]
            
        except Exception as e:
            logger.error(f"Error fetching journey {journey_id}: {e}")
            raise
    
    async def get_routes(self, journey_id: str) -> List[Route]:
        """
        Get all routes for a journey
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            List of Route objects
        """
        try:
            results = await execute_query(
                """SELECT * FROM routes 
                   WHERE journey_id = ? 
                   ORDER BY route_index""",
                (journey_id,)
            )
            
            routes = []
            for row in results:
                # Parse geometry from JSON
                geometry = json.loads(row["geometry"])
                
                route = Route(
                    route_id=f"route_{row['route_index']}",
                    route_index=row["route_index"],
                    geometry=geometry,
                    distance_meters=row["distance_meters"],
                    duration_seconds=row["duration_seconds"],
                    summary=row["summary"]
                )
                routes.append(route)
            
            logger.debug(f"Retrieved {len(routes)} routes for journey {journey_id}")
            return routes
            
        except Exception as e:
            logger.error(f"Error fetching routes for journey {journey_id}: {e}")
            raise
    
    async def store_gps_point(self, journey_id: str, gps_point: GPSPoint) -> None:
        """
        Store a GPS point for a journey
        
        Args:
            journey_id: Journey UUID
            gps_point: GPS point data
        """
        try:
            await execute_update("""
                INSERT INTO gps_points 
                (journey_id, lat, lng, timestamp, speed, bearing, accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                journey_id,
                gps_point.lat,
                gps_point.lng,
                gps_point.timestamp.isoformat(),
                gps_point.speed,
                gps_point.bearing,
                gps_point.accuracy
            ))
            
            logger.debug(
                f"Stored GPS point for journey {journey_id}: "
                f"({gps_point.lat:.4f}, {gps_point.lng:.4f})"
            )
            
        except Exception as e:
            logger.error(f"Error storing GPS point: {e}")
            raise
    
    async def get_recent_gps_points(
        self,
        journey_id: str,
        limit: int = 10
    ) -> List[GPSPoint]:
        """
        Get most recent GPS points for a journey
        
        Args:
            journey_id: Journey UUID
            limit: Maximum number of points to return
        
        Returns:
            List of GPSPoint objects
        """
        try:
            results = await execute_query("""
                SELECT * FROM gps_points 
                WHERE journey_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (journey_id, limit))
            
            gps_points = []
            for row in results:
                point = GPSPoint(
                    lat=row["lat"],
                    lng=row["lng"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    speed=row["speed"],
                    bearing=row["bearing"],
                    accuracy=row["accuracy"]
                )
                gps_points.append(point)
            
            # Return in chronological order (oldest first)
            return list(reversed(gps_points))
            
        except Exception as e:
            logger.error(f"Error fetching GPS points: {e}")
            raise
    
    async def update_journey_status(
        self,
        journey_id: str,
        status: str,
        end_time: Optional[datetime] = None
    ) -> None:
        """
        Update journey status
        
        Args:
            journey_id: Journey UUID
            status: New status ('active', 'completed', 'abandoned')
            end_time: Optional end time for completed/abandoned journeys
        """
        try:
            if end_time:
                await execute_update("""
                    UPDATE journeys 
                    SET status = ?, end_time = ? 
                    WHERE id = ?
                """, (status, end_time.isoformat(), journey_id))
            else:
                await execute_update("""
                    UPDATE journeys 
                    SET status = ? 
                    WHERE id = ?
                """, (status, journey_id))
            
            logger.info(f"Updated journey {journey_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Error updating journey status: {e}")
            raise
    
    async def store_deviation_event(
        self,
        journey_id: str,
        timestamp: datetime,
        severity: str,
        spatial_status: str,
        temporal_status: str,
        directional_status: str,
        distance_from_route: float,
        time_deviation: float,
        route_probabilities: Dict[str, float]
    ) -> None:
        """
        Store a deviation event
        
        Args:
            journey_id: Journey UUID
            timestamp: Event timestamp
            severity: Severity level
            spatial_status: Spatial deviation status
            temporal_status: Temporal deviation status
            directional_status: Directional deviation status
            distance_from_route: Distance from nearest route in meters
            time_deviation: Time deviation in seconds
            route_probabilities: Route probabilities dictionary
        """
        try:
            await execute_update("""
                INSERT INTO deviation_events 
                (journey_id, timestamp, severity, spatial_status, temporal_status,
                 directional_status, distance_from_route, time_deviation, route_probabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                journey_id,
                timestamp.isoformat(),
                severity,
                spatial_status,
                temporal_status,
                directional_status,
                distance_from_route,
                time_deviation,
                json.dumps(route_probabilities)
            ))
            
            logger.info(
                f"Stored {severity} deviation event for journey {journey_id} "
                f"(spatial: {spatial_status}, temporal: {temporal_status})"
            )
            
        except Exception as e:
            logger.error(f"Error storing deviation event: {e}")
            raise


# Singleton instance
journey_service = JourneyService()
