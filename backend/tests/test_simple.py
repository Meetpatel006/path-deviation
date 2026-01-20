"""
Simple Phase 1 test using requests library
"""
import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

# Test data: Pune to Mumbai
PUNE_COORDS = {"lat": 18.5246, "lng": 73.8786}
MUMBAI_COORDS = {"lat": 18.9582, "lng": 72.8321}


def test_phase_1():
    """Test Phase 1 functionality"""
    print("=" * 60)
    print("Phase 1 Validation Test")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    response = requests.get(f"{API_BASE}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   OK Health check passed")
    
    # Test 2: Start journey (calls Mapbox API)
    print("\n2. Testing journey start with Mapbox API...")
    journey_request = {
        "origin": PUNE_COORDS,
        "destination": MUMBAI_COORDS,
        "travel_mode": "driving"
    }
    
    print(f"   Fetching routes from Pune to Mumbai...")
    response = requests.post(
        f"{API_BASE}/api/journey/start",
        json=journey_request
    )
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 201:
        print(f"   Error: {response.text}")
        return
    
    data = response.json()
    journey_id = data["journey_id"]
    routes = data["routes"]
    
    print(f"   OK Journey created: {journey_id}")
    print(f"   OK Retrieved {len(routes)} route alternative(s)")
    
    for i, route in enumerate(routes):
        dist_km = route['distance_meters'] / 1000
        dur_min = route['duration_seconds'] / 60
        points = len(route['geometry'])
        print(f"      Route {i}: {dist_km:.1f}km, {dur_min:.0f}min, {points} points")
    
    # Test 3: Submit GPS points
    print(f"\n3. Testing GPS point submission...")
    gps_points = [
        {
            "lat": 18.5250,
            "lng": 73.8780,
            "timestamp": datetime.now().isoformat() + "Z",
            "speed": 60.0,
            "bearing": 270.0,
            "accuracy": 10.0
        },
        {
            "lat": 18.5270,
            "lng": 73.8750,
            "timestamp": datetime.now().isoformat() + "Z",
            "speed": 65.0,
            "bearing": 275.0,
            "accuracy": 8.0
        }
    ]
    
    for i, gps_point in enumerate(gps_points):
        response = requests.post(
            f"{API_BASE}/api/journey/{journey_id}/gps",
            json=gps_point
        )
        assert response.status_code == 200
        print(f"   OK GPS point {i+1} submitted successfully")
    
    # Test 4: Get journey status
    print(f"\n4. Testing journey status retrieval...")
    response = requests.get(f"{API_BASE}/api/journey/{journey_id}")
    assert response.status_code == 200
    
    status_data = response.json()
    print(f"   OK Journey status: {status_data['current_status']}")
    print(f"   OK Progress: {status_data['progress_percentage']:.1f}%")
    print(f"   OK Deviation severity: {status_data['deviation_status']['severity']}")
    
    # Test 5: Complete journey
    print(f"\n5. Testing journey completion...")
    response = requests.put(f"{API_BASE}/api/journey/{journey_id}/complete")
    assert response.status_code == 200
    print(f"   OK Journey completed successfully")
    
    print("\n" + "=" * 60)
    print("OK Phase 1 validation completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_phase_1()
    except requests.exceptions.ConnectionError:
        print("\nError: Cannot connect to server at " + API_BASE)
        print("Please start the server first:")
        print("  cd backend")
        print("  python -m app.main")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
