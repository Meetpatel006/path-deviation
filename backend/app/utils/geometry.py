"""
Geometry utility functions for GPS calculations

This module provides essential geometric calculations for the deviation detection system:
- Haversine distance between GPS coordinates
- Bearing calculations
- Point-to-line distance calculations
- Progress along route calculations
"""
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from typing import List, Tuple, Optional
import numpy as np

from app.utils.logger import logger


def haversine_distance(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    """
    Calculate great-circle distance between two GPS points using Haversine formula
    
    Args:
        point1: (lat, lng) in decimal degrees
        point2: (lat, lng) in decimal degrees
    
    Returns:
        Distance in meters
    
    Example:
        >>> pune = (18.5246, 73.8786)
        >>> mumbai = (18.9582, 72.8321)
        >>> dist = haversine_distance(pune, mumbai)
        >>> print(f"{dist/1000:.1f} km")  # ~148.4 km
    """
    lat1, lon1 = point1
    lat2, lon2 = point2
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Earth radius in meters
    earth_radius = 6371000
    
    distance = earth_radius * c
    
    return distance


def calculate_bearing(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    """
    Calculate initial bearing from point1 to point2
    
    Args:
        point1: (lat, lng) starting point
        point2: (lat, lng) ending point
    
    Returns:
        Bearing in degrees (0-360), where 0° is North, 90° is East
    
    Example:
        >>> start = (18.5246, 73.8786)
        >>> end = (18.9582, 72.8321)
        >>> bearing = calculate_bearing(start, end)
        >>> print(f"{bearing:.1f}°")  # ~290° (Northwest)
    """
    lat1, lon1 = point1
    lat2, lon2 = point2
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Calculate bearing
    dlon = lon2 - lon1
    
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    
    initial_bearing = atan2(x, y)
    
    # Convert to degrees and normalize to 0-360
    bearing = (degrees(initial_bearing) + 360) % 360
    
    return bearing


def point_to_segment_distance(
    point: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float]
) -> Tuple[Tuple[float, float], float]:
    """
    Calculate perpendicular distance from point to line segment
    
    Args:
        point: (lat, lng) point to measure from
        seg_start: (lat, lng) segment start
        seg_end: (lat, lng) segment end
    
    Returns:
        Tuple of (closest_point_on_segment, distance_in_meters)
    
    Algorithm:
        1. Project point onto infinite line containing segment
        2. If projection is outside segment, use nearest endpoint
        3. Calculate distance to closest point
    """
    # Special case: segment is a point
    if seg_start == seg_end:
        return seg_start, haversine_distance(point, seg_start)
    
    # Calculate vectors
    # We work in a local coordinate system for small distances
    # Convert to approximate meters (this is accurate enough for small distances)
    
    lat_to_m = 111320  # meters per degree latitude
    lng_to_m = 111320 * cos(radians(point[0]))  # adjusted for latitude
    
    # Convert to local coordinates (meters)
    px = (point[1] - seg_start[1]) * lng_to_m
    py = (point[0] - seg_start[0]) * lat_to_m
    
    sx = (seg_end[1] - seg_start[1]) * lng_to_m
    sy = (seg_end[0] - seg_start[0]) * lat_to_m
    
    # Calculate projection parameter
    segment_length_sq = sx * sx + sy * sy
    
    if segment_length_sq == 0:
        # Segment is essentially a point
        closest_point = seg_start
    else:
        # Calculate projection parameter t
        t = max(0, min(1, (px * sx + py * sy) / segment_length_sq))
        
        # Calculate closest point
        closest_lat = seg_start[0] + t * (seg_end[0] - seg_start[0])
        closest_lng = seg_start[1] + t * (seg_end[1] - seg_start[1])
        closest_point = (closest_lat, closest_lng)
    
    # Calculate distance
    distance = haversine_distance(point, closest_point)
    
    return closest_point, distance


def find_nearest_point_on_line(
    point: Tuple[float, float],
    line: List[Tuple[float, float]]
) -> Tuple[Tuple[float, float], float, int]:
    """
    Find nearest point on a polyline to given point
    
    Args:
        point: (lat, lng) point to measure from
        line: List of (lat, lng) coordinates forming polyline
    
    Returns:
        Tuple of (nearest_point, distance_meters, segment_index)
    
    Example:
        >>> route = [(18.5246, 73.8786), (18.5300, 73.8700), (18.5400, 73.8600)]
        >>> gps_point = (18.5250, 73.8750)
        >>> nearest, dist, idx = find_nearest_point_on_line(gps_point, route)
        >>> print(f"Distance: {dist:.1f}m, Segment: {idx}")
    """
    if not line:
        raise ValueError("Line cannot be empty")
    
    if len(line) == 1:
        return line[0], haversine_distance(point, line[0]), 0
    
    min_distance = float('inf')
    nearest_point: Tuple[float, float] = line[0]  # Initialize with first point
    segment_index = 0
    
    # Check each segment
    for i in range(len(line) - 1):
        seg_start = line[i]
        seg_end = line[i + 1]
        
        closest_on_segment, distance = point_to_segment_distance(
            point, seg_start, seg_end
        )
        
        if distance < min_distance:
            min_distance = distance
            nearest_point = closest_on_segment
            segment_index = i
    
    logger.debug(
        f"Nearest point on line: distance={min_distance:.2f}m, segment={segment_index}"
    )
    
    return nearest_point, min_distance, segment_index


def calculate_progress_along_route(
    start_point: Tuple[float, float],
    current_point: Tuple[float, float],
    route_geometry: List[Tuple[float, float]]
) -> float:
    """
    Calculate how far along the route the user has traveled
    
    Args:
        start_point: Journey start location (lat, lng)
        current_point: Current GPS location (lat, lng)
        route_geometry: List of (lat, lng) coordinates for the route
    
    Returns:
        Distance traveled in meters from start of route
    
    Algorithm:
        1. Find nearest point on route to current GPS location
        2. Calculate distance from route start to that nearest point
    """
    if not route_geometry or len(route_geometry) < 2:
        return 0.0
    
    # Find nearest point on route
    nearest_point, _, segment_index = find_nearest_point_on_line(
        current_point, route_geometry
    )
    
    # Calculate cumulative distance to nearest point
    distance_traveled = 0.0
    
    # Sum distances from start to the segment containing nearest point
    for i in range(segment_index):
        distance_traveled += haversine_distance(
            route_geometry[i],
            route_geometry[i + 1]
        )
    
    # Add distance within the current segment
    distance_traveled += haversine_distance(
        route_geometry[segment_index],
        nearest_point
    )
    
    logger.debug(f"Progress along route: {distance_traveled:.2f}m")
    
    return distance_traveled


def calculate_total_route_distance(
    route_geometry: List[Tuple[float, float]]
) -> float:
    """
    Calculate total distance of a route
    
    Args:
        route_geometry: List of (lat, lng) coordinates
    
    Returns:
        Total distance in meters
    """
    if not route_geometry or len(route_geometry) < 2:
        return 0.0
    
    total_distance = 0.0
    for i in range(len(route_geometry) - 1):
        total_distance += haversine_distance(
            route_geometry[i],
            route_geometry[i + 1]
        )
    
    return total_distance


def bearing_difference(bearing1: float, bearing2: float) -> float:
    """
    Calculate the absolute difference between two bearings (0-360°)
    
    Args:
        bearing1: First bearing in degrees
        bearing2: Second bearing in degrees
    
    Returns:
        Absolute difference in degrees (0-180)
    
    Example:
        >>> bearing_difference(10, 350)  # Nearly same direction
        20.0
        >>> bearing_difference(90, 270)  # Opposite directions
        180.0
    """
    diff = abs(bearing1 - bearing2)
    if diff > 180:
        diff = 360 - diff
    return diff


def interpolate_point(
    point1: Tuple[float, float],
    point2: Tuple[float, float],
    fraction: float
) -> Tuple[float, float]:
    """
    Interpolate a point between two GPS coordinates
    
    Args:
        point1: (lat, lng) start point
        point2: (lat, lng) end point
        fraction: Interpolation fraction (0.0 = point1, 1.0 = point2)
    
    Returns:
        Interpolated (lat, lng) point
    
    Example:
        >>> start = (18.5246, 73.8786)
        >>> end = (18.9582, 72.8321)
        >>> midpoint = interpolate_point(start, end, 0.5)
    """
    lat = point1[0] + (point2[0] - point1[0]) * fraction
    lng = point1[1] + (point2[1] - point1[1]) * fraction
    return (lat, lng)


def get_route_bearing_at_point(
    route_geometry: List[Tuple[float, float]],
    point: Tuple[float, float]
) -> float:
    """
    Get the bearing of the route at a specific point
    
    Args:
        route_geometry: List of (lat, lng) coordinates
        point: (lat, lng) point on or near the route
    
    Returns:
        Route bearing at that point in degrees
    """
    if len(route_geometry) < 2:
        return 0.0
    
    # Find nearest segment
    _, _, segment_index = find_nearest_point_on_line(point, route_geometry)
    
    # Calculate bearing of that segment
    seg_start = route_geometry[segment_index]
    seg_end = route_geometry[min(segment_index + 1, len(route_geometry) - 1)]
    
    return calculate_bearing(seg_start, seg_end)
