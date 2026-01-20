"""
Unit tests for geometry utilities

Tests critical GPS calculations with known values:
- Haversine distance
- Bearing calculations
- Point-to-line distance
- Progress calculations
"""
import pytest
from app.utils.geometry import (
    haversine_distance,
    calculate_bearing,
    point_to_segment_distance,
    find_nearest_point_on_line,
    calculate_progress_along_route,
    bearing_difference,
    interpolate_point,
    get_route_bearing_at_point
)


class TestHaversineDistance:
    """Test haversine distance calculations"""
    
    def test_known_distance_pune_mumbai(self):
        """Test Pune to Mumbai distance (~148.4 km)"""
        pune = (18.5246, 73.8786)
        mumbai = (18.9582, 72.8321)
        
        distance = haversine_distance(pune, mumbai)
        distance_km = distance / 1000
        
        # Should be approximately 148.4 km (±5 km tolerance)
        assert 143 < distance_km < 153, f"Expected ~148 km, got {distance_km:.1f} km"
    
    def test_zero_distance(self):
        """Test distance from point to itself"""
        point = (18.5246, 73.8786)
        distance = haversine_distance(point, point)
        assert distance < 0.01, "Distance to self should be ~0"
    
    def test_short_distance(self):
        """Test short distance (~100 meters)"""
        # Two points roughly 100m apart
        point1 = (18.5246, 73.8786)
        point2 = (18.5255, 73.8786)  # ~1 km north
        
        distance = haversine_distance(point1, point2)
        assert 900 < distance < 1100, f"Expected ~1000m, got {distance:.1f}m"
    
    def test_symmetry(self):
        """Test that distance(A,B) == distance(B,A)"""
        point1 = (18.5246, 73.8786)
        point2 = (18.9582, 72.8321)
        
        dist1 = haversine_distance(point1, point2)
        dist2 = haversine_distance(point2, point1)
        
        assert abs(dist1 - dist2) < 0.01, "Distance should be symmetric"


class TestBearing:
    """Test bearing calculations"""
    
    def test_bearing_north(self):
        """Test bearing directly north (0°)"""
        start = (18.0, 73.0)
        end = (19.0, 73.0)  # 1 degree north
        
        bearing = calculate_bearing(start, end)
        assert -5 < bearing < 5 or 355 < bearing < 365, f"Expected ~0°, got {bearing:.1f}°"
    
    def test_bearing_east(self):
        """Test bearing directly east (90°)"""
        start = (18.0, 73.0)
        end = (18.0, 74.0)  # 1 degree east
        
        bearing = calculate_bearing(start, end)
        assert 85 < bearing < 95, f"Expected ~90°, got {bearing:.1f}°"
    
    def test_bearing_south(self):
        """Test bearing directly south (180°)"""
        start = (19.0, 73.0)
        end = (18.0, 73.0)  # 1 degree south
        
        bearing = calculate_bearing(start, end)
        assert 175 < bearing < 185, f"Expected ~180°, got {bearing:.1f}°"
    
    def test_bearing_west(self):
        """Test bearing directly west (270°)"""
        start = (18.0, 74.0)
        end = (18.0, 73.0)  # 1 degree west
        
        bearing = calculate_bearing(start, end)
        assert 265 < bearing < 275, f"Expected ~270°, got {bearing:.1f}°"
    
    def test_bearing_difference(self):
        """Test bearing difference calculations"""
        # Similar directions
        assert bearing_difference(10, 20) == 10
        assert bearing_difference(350, 10) == 20  # Wraps around 0°
        
        # Opposite directions
        assert bearing_difference(90, 270) == 180
        assert bearing_difference(0, 180) == 180


class TestPointToSegmentDistance:
    """Test point-to-line distance calculations"""
    
    def test_point_on_segment(self):
        """Test point exactly on segment"""
        point = (18.5250, 73.8786)
        seg_start = (18.5246, 73.8786)
        seg_end = (18.5260, 73.8786)
        
        closest, distance = point_to_segment_distance(point, seg_start, seg_end)
        
        # Point is on the segment, distance should be very small
        assert distance < 10, f"Expected ~0m, got {distance:.1f}m"
    
    def test_point_near_segment_end(self):
        """Test point near segment endpoint"""
        point = (18.5246, 73.8786)
        seg_start = (18.5246, 73.8786)
        seg_end = (18.5260, 73.8786)
        
        closest, distance = point_to_segment_distance(point, seg_start, seg_end)
        
        # Closest point should be near segment start
        assert distance < 10, "Point is at segment start"
    
    def test_perpendicular_distance(self):
        """Test perpendicular distance from point to segment"""
        # Create horizontal segment
        seg_start = (18.5246, 73.8786)
        seg_end = (18.5246, 73.8900)  # Horizontal line
        
        # Point directly above segment midpoint
        point = (18.5256, 73.8843)  # ~1.1 km north of midpoint
        
        closest, distance = point_to_segment_distance(point, seg_start, seg_end)
        
        # Should be roughly 1.1 km
        assert 900 < distance < 1300, f"Expected ~1100m, got {distance:.1f}m"


class TestFindNearestPointOnLine:
    """Test finding nearest point on polyline"""
    
    def test_simple_line(self):
        """Test with simple 3-point line"""
        line = [
            (18.5246, 73.8786),
            (18.5300, 73.8700),
            (18.5400, 73.8600)
        ]
        
        # Point near middle of line
        point = (18.5300, 73.8750)
        
        nearest, distance, segment_idx = find_nearest_point_on_line(point, line)
        
        assert segment_idx in [0, 1], "Should be on one of the segments"
        assert distance < 1000, f"Distance should be small, got {distance:.1f}m"
    
    def test_single_point_line(self):
        """Test with single point (degenerate case)"""
        line = [(18.5246, 73.8786)]
        point = (18.5300, 73.8700)
        
        nearest, distance, segment_idx = find_nearest_point_on_line(point, line)
        
        assert segment_idx == 0
        assert nearest == line[0]


class TestProgressCalculation:
    """Test progress along route calculations"""
    
    def test_progress_at_start(self):
        """Test progress at route start"""
        route = [
            (18.5246, 73.8786),
            (18.5300, 73.8700),
            (18.5400, 73.8600)
        ]
        
        start = route[0]
        current = route[0]
        
        progress = calculate_progress_along_route(start, current, route)
        assert progress < 100, f"Progress at start should be ~0, got {progress:.1f}m"
    
    def test_progress_at_end(self):
        """Test progress at route end"""
        route = [
            (18.5246, 73.8786),
            (18.5300, 73.8700),
            (18.5400, 73.8600)
        ]
        
        start = route[0]
        current = route[-1]
        
        progress = calculate_progress_along_route(start, current, route)
        
        # Calculate total distance
        total = haversine_distance(route[0], route[1]) + haversine_distance(route[1], route[2])
        
        # Progress should be close to total
        assert abs(progress - total) < 100, "Progress at end should equal total distance"
    
    def test_progress_midway(self):
        """Test progress at middle of route"""
        route = [
            (18.5246, 73.8786),
            (18.5300, 73.8700),
            (18.5400, 73.8600)
        ]
        
        start = route[0]
        current = route[1]  # Midpoint
        
        progress = calculate_progress_along_route(start, current, route)
        
        # Should be approximately the distance to first waypoint
        expected = haversine_distance(route[0], route[1])
        assert abs(progress - expected) < 100, f"Progress mismatch: {progress:.1f}m vs {expected:.1f}m"


class TestInterpolation:
    """Test point interpolation"""
    
    def test_interpolate_midpoint(self):
        """Test interpolating midpoint"""
        point1 = (18.5246, 73.8786)
        point2 = (18.5400, 73.8600)
        
        midpoint = interpolate_point(point1, point2, 0.5)
        
        # Check midpoint is roughly halfway
        dist1 = haversine_distance(point1, midpoint)
        dist2 = haversine_distance(midpoint, point2)
        
        assert abs(dist1 - dist2) < 50, "Midpoint should be equidistant from both points"
    
    def test_interpolate_endpoints(self):
        """Test interpolation at endpoints"""
        point1 = (18.5246, 73.8786)
        point2 = (18.5400, 73.8600)
        
        # Fraction = 0 should return point1
        result = interpolate_point(point1, point2, 0.0)
        assert result == point1
        
        # Fraction = 1 should return point2
        result = interpolate_point(point1, point2, 1.0)
        assert result == point2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
