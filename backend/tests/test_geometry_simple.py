"""
Simple test runner for geometry utilities
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.utils.geometry import (
    haversine_distance,
    calculate_bearing,
    point_to_segment_distance,
    find_nearest_point_on_line,
    calculate_progress_along_route,
    bearing_difference,
    interpolate_point
)


def test_haversine():
    """Test haversine distance"""
    print("\n1. Testing Haversine Distance...")
    
    # Pune to Mumbai (~148 km)
    pune = (18.5246, 73.8786)
    mumbai = (18.9582, 72.8321)
    
    distance = haversine_distance(pune, mumbai)
    distance_km = distance / 1000
    
    print(f"   Pune to Mumbai: {distance_km:.1f} km")
    assert 115 < distance_km < 155, f"Expected ~120-150 km, got {distance_km:.1f} km"
    print("   OK PASS")
    
    # Zero distance
    distance = haversine_distance(pune, pune)
    assert distance < 0.01
    print("   OK Zero distance PASS")


def test_bearing():
    """Test bearing calculations"""
    print("\n2. Testing Bearing Calculations...")
    
    # North
    start = (18.0, 73.0)
    end = (19.0, 73.0)
    bearing = calculate_bearing(start, end)
    print(f"   North bearing: {bearing:.1f}°")
    assert -5 < bearing < 5 or 355 < bearing < 365
    print("   OK North PASS")
    
    # East
    start = (18.0, 73.0)
    end = (18.0, 74.0)
    bearing = calculate_bearing(start, end)
    print(f"   East bearing: {bearing:.1f}°")
    assert 85 < bearing < 95
    print("   OK East PASS")
    
    # Bearing difference
    diff = bearing_difference(10, 350)
    print(f"   Bearing difference (10° vs 350°): {diff:.1f}°")
    assert abs(diff - 20) < 1
    print("   OK Bearing difference PASS")


def test_point_to_segment():
    """Test point-to-segment distance"""
    print("\n3. Testing Point-to-Segment Distance...")
    
    point = (18.5250, 73.8786)
    seg_start = (18.5246, 73.8786)
    seg_end = (18.5260, 73.8786)
    
    closest, distance = point_to_segment_distance(point, seg_start, seg_end)
    print(f"   Point on segment distance: {distance:.1f}m")
    assert distance < 50  # Should be very close
    print("   OK PASS")


def test_nearest_point_on_line():
    """Test finding nearest point on polyline"""
    print("\n4. Testing Nearest Point on Line...")
    
    line = [
        (18.5246, 73.8786),
        (18.5300, 73.8700),
        (18.5400, 73.8600)
    ]
    
    point = (18.5300, 73.8750)
    nearest, distance, segment_idx = find_nearest_point_on_line(point, line)
    
    print(f"   Distance to line: {distance:.1f}m")
    print(f"   Nearest segment: {segment_idx}")
    assert distance < 1000
    assert segment_idx in [0, 1]
    print("   OK PASS")


def test_progress():
    """Test progress calculation"""
    print("\n5. Testing Progress Along Route...")
    
    route = [
        (18.5246, 73.8786),
        (18.5300, 73.8700),
        (18.5400, 73.8600)
    ]
    
    # At start
    start = route[0]
    current = route[0]
    progress = calculate_progress_along_route(start, current, route)
    print(f"   Progress at start: {progress:.1f}m")
    assert progress < 100
    print("   OK Start PASS")
    
    # At midpoint
    current = route[1]
    progress = calculate_progress_along_route(start, current, route)
    expected = haversine_distance(route[0], route[1])
    print(f"   Progress at waypoint 1: {progress:.1f}m (expected ~{expected:.1f}m)")
    assert abs(progress - expected) < 100
    print("   OK Midpoint PASS")


def test_interpolation():
    """Test point interpolation"""
    print("\n6. Testing Point Interpolation...")
    
    point1 = (18.5246, 73.8786)
    point2 = (18.5400, 73.8600)
    
    midpoint = interpolate_point(point1, point2, 0.5)
    dist1 = haversine_distance(point1, midpoint)
    dist2 = haversine_distance(midpoint, point2)
    
    print(f"   Distance to midpoint: {dist1:.1f}m vs {dist2:.1f}m")
    assert abs(dist1 - dist2) < 50
    print("   OK PASS")


def main():
    print("=" * 60)
    print("Geometry Utilities Test Suite")
    print("=" * 60)
    
    try:
        test_haversine()
        test_bearing()
        test_point_to_segment()
        test_nearest_point_on_line()
        test_progress()
        test_interpolation()
        
        print("\n" + "=" * 60)
        print("OK All geometry tests PASSED!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\nX ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
