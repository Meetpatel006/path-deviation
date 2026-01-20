"""
Deviation Detection Service

This service implements the core deviation detection logic:
- Spatial deviation: Is the user on/near/off the route?
- Temporal deviation: Is the user on time, delayed, or stopped?
- Directional deviation: Is the user heading toward the destination?
- Overall severity: Combines all deviation types
"""
from typing import List, Tuple
from datetime import datetime

from app.models.schemas import GPSPoint, Route
from app.utils.geometry import (
    find_nearest_point_on_line,
    calculate_bearing,
    bearing_difference
)
from app.config import settings
from app.utils.logger import logger


class DeviationDetector:
    """
    Detects various types of deviations from planned routes
    
    Attributes:
        routes: List of route alternatives
    """
    
    def __init__(self, routes: List[Route]):
        """
        Initialize deviation detector with route alternatives
        
        Args:
            routes: List of Route objects
        """
        self.routes = routes
        logger.debug(f"Initialized DeviationDetector with {len(routes)} route(s)")
    
    def check_spatial_deviation(
        self,
        gps_point: GPSPoint,
        speed: float
    ) -> Tuple[str, float, str]:
        """
        Determine if user is spatially off-route
        
        Uses dynamic buffer zones based on speed:
        - Walking (< 6 km/h): 20 meters
        - City driving (< 60 km/h): 50 meters
        - Highway (> 60 km/h): 75 meters
        
        Args:
            gps_point: Current GPS location
            speed: Current speed in km/h
        
        Returns:
            Tuple of (status, min_distance, closest_route_id)
            status: 'ON_ROUTE', 'NEAR_ROUTE', 'OFF_ROUTE'
        """
        # Determine dynamic buffer based on speed
        if speed < 6:  # Walking
            buffer = settings.BUFFER_WALKING
        elif speed < 60:  # City driving
            buffer = settings.BUFFER_CITY
        else:  # Highway
            buffer = settings.BUFFER_HIGHWAY
        
        logger.debug(f"Spatial deviation check: speed={speed:.1f}km/h, buffer={buffer}m")
        
        # Check distance to each route
        min_distance = float('inf')
        closest_route_id = self.routes[0].route_id if self.routes else "unknown"
        
        for route in self.routes:
            # Convert route geometry from (lng, lat) to (lat, lng)
            route_coords = [(lat, lng) for lng, lat in route.geometry]
            
            _, distance, _ = find_nearest_point_on_line(
                (gps_point.lat, gps_point.lng),
                route_coords
            )
            
            if distance < min_distance:
                min_distance = distance
                closest_route_id = route.route_id
        
        # Classify spatial status
        if min_distance <= buffer:
            status = "ON_ROUTE"
        elif min_distance <= 2 * buffer:
            status = "NEAR_ROUTE"
        else:
            status = "OFF_ROUTE"
        
        logger.info(
            f"Spatial deviation: {status}, distance={min_distance:.1f}m, "
            f"closest_route={closest_route_id}"
        )
        
        return status, min_distance, closest_route_id
    
    def check_temporal_deviation(
        self,
        journey_start_time: datetime,
        current_time: datetime,
        progress_meters: float,
        expected_route: Route,
        current_speed: float,
        stopped_duration: float = 0.0
    ) -> Tuple[str, float]:
        """
        Determine if user is temporally delayed
        
        Args:
            journey_start_time: When journey started
            current_time: Current timestamp
            progress_meters: Distance traveled so far
            expected_route: The route being followed
            current_speed: Current speed in km/h
            stopped_duration: How long user has been stopped (seconds)
        
        Returns:
            Tuple of (status, time_deviation_seconds)
            status: 'ON_TIME', 'DELAYED', 'SEVERELY_DELAYED', 'STOPPED'
        """
        # Calculate progress percentage
        progress_pct = (progress_meters / expected_route.distance_meters) * 100
        
        # Calculate expected time at current progress
        expected_time = expected_route.duration_seconds * (progress_pct / 100)
        
        # Calculate actual time elapsed
        actual_time = (current_time - journey_start_time).total_seconds()
        
        # Calculate deviation
        time_deviation = actual_time - expected_time
        
        logger.debug(
            f"Temporal check: progress={progress_pct:.1f}%, "
            f"expected={expected_time:.0f}s, actual={actual_time:.0f}s, "
            f"deviation={time_deviation:.0f}s"
        )
        
        # Check if stopped for too long
        if stopped_duration > 600:  # 10 minutes
            status = "STOPPED"
            logger.info(f"Temporal deviation: STOPPED for {stopped_duration:.0f}s")
            return status, time_deviation
        
        # Check if speed is very low (< 1 km/h)
        if current_speed < 1:
            status = "STOPPED"
            logger.info(f"Temporal deviation: STOPPED (speed {current_speed:.1f}km/h)")
            return status, time_deviation
        
        # Classify temporal status
        if time_deviation < 300:  # 5 minutes
            status = "ON_TIME"
        elif time_deviation < 900:  # 15 minutes
            status = "DELAYED"
        else:
            status = "SEVERELY_DELAYED"
        
        logger.info(f"Temporal deviation: {status}, {time_deviation:.0f}s")
        
        return status, time_deviation
    
    def check_directional_deviation(
        self,
        current_point: GPSPoint,
        destination: Tuple[float, float],
        expected_route: Route,
        recent_points: List[GPSPoint]
    ) -> str:
        """
        Determine if user is heading in correct direction
        
        Args:
            current_point: Current GPS location
            destination: Destination coordinates (lat, lng)
            expected_route: The route being followed
            recent_points: Recent GPS points for calculating movement bearing
        
        Returns:
            status: 'TOWARD_DEST', 'PERPENDICULAR', 'AWAY'
        """
        # Calculate bearing to destination
        expected_bearing = calculate_bearing(
            (current_point.lat, current_point.lng),
            destination
        )
        
        # Calculate actual bearing from recent movement
        if len(recent_points) >= 2:
            # Use last two points to determine movement direction
            prev_point = recent_points[-2]
            curr_point = recent_points[-1]
            
            actual_bearing = calculate_bearing(
                (prev_point.lat, prev_point.lng),
                (curr_point.lat, curr_point.lng)
            )
        else:
            # Not enough data, assume aligned
            logger.debug("Directional check: Not enough points, assuming TOWARD_DEST")
            return "TOWARD_DEST"
        
        # Calculate bearing difference
        bearing_diff = bearing_difference(expected_bearing, actual_bearing)
        
        logger.debug(
            f"Directional check: expected={expected_bearing:.1f}°, "
            f"actual={actual_bearing:.1f}°, diff={bearing_diff:.1f}°"
        )
        
        # Classify directional status
        if bearing_diff < 45:
            status = "TOWARD_DEST"
        elif bearing_diff < 135:
            status = "PERPENDICULAR"
        else:
            status = "AWAY"
        
        logger.info(f"Directional deviation: {status} (bearing diff {bearing_diff:.1f}°)")
        
        return status
    
    def determine_severity(
        self,
        spatial: str,
        temporal: str,
        directional: str
    ) -> str:
        """
        Combine all deviation types into overall severity
        
        Severity Levels:
        - Level 0 (normal): On route, on time
        - Level 1 (minor): Near route, still heading to destination
        - Level 2 (moderate): Off route but heading toward destination
        - Level 3 (concerning): Stopped too long
        - Level 4 (major): Off route AND wrong direction
        
        Args:
            spatial: Spatial deviation status
            temporal: Temporal deviation status
            directional: Directional deviation status
        
        Returns:
            severity: 'normal', 'minor', 'moderate', 'concerning', 'major'
        """
        # Level 0 - Normal
        if spatial == "ON_ROUTE" and temporal in ["ON_TIME", "DELAYED"]:
            severity = "normal"
        
        # Level 1 - Minor
        elif spatial == "NEAR_ROUTE" and directional == "TOWARD_DEST":
            severity = "minor"
        
        # Level 2 - Moderate
        elif spatial == "OFF_ROUTE" and directional == "TOWARD_DEST":
            severity = "moderate"
        
        # Level 3 - Concerning
        elif temporal == "STOPPED":
            severity = "concerning"
        
        # Level 4 - Major
        elif spatial == "OFF_ROUTE" and directional in ["PERPENDICULAR", "AWAY"]:
            severity = "major"
        
        # Default to minor for edge cases
        else:
            severity = "minor"
        
        logger.info(
            f"Overall severity: {severity} (spatial={spatial}, "
            f"temporal={temporal}, directional={directional})"
        )
        
        return severity
