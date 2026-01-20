"""
Phase 1 validation script - Test Mapbox integration and API endpoints
"""
import asyncio
import httpx
from datetime import datetime

API_BASE = "http://localhost:8000"

# Test data: Pune to Mumbai (from your routes folder)
PUNE_COORDS = {"lat": 18.5246, "lng": 73.8786}
MUMBAI_COORDS = {"lat": 18.9582, "lng": 72.8321}


async def test_phase_1():
    """Test Phase 1 functionality"""
    print("=" * 60)
    print("Phase 1 Validation Test")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: Health check
        print("\n1. Testing health check...")
        response = await client.get(f"{API_BASE}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200
        print("   ✓ Health check passed")
        
        # Test 2: Start journey (calls Mapbox API)
        print("\n2. Testing journey start with Mapbox API...")
        journey_request = {
            "origin": PUNE_COORDS,
            "destination": MUMBAI_COORDS,
            "travel_mode": "driving"
        }
        
        print(f"   Fetching routes from Pune to Mumbai...")
        response = await client.post(
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
        
        print(f"   ✓ Journey created: {journey_id}")
        print(f"   ✓ Retrieved {len(routes)} route alternative(s)")
        
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
            response = await client.post(
                f"{API_BASE}/api/journey/{journey_id}/gps",
                json=gps_point
            )
            assert response.status_code == 200
            print(f"   ✓ GPS point {i+1} submitted successfully")
        
        # Test 4: Get journey status
        print(f"\n4. Testing journey status retrieval...")
        response = await client.get(f"{API_BASE}/api/journey/{journey_id}")
        assert response.status_code == 200
        
        status_data = response.json()
        print(f"   ✓ Journey status: {status_data['current_status']}")
        print(f"   ✓ Progress: {status_data['progress_percentage']:.1f}%")
        print(f"   ✓ Deviation severity: {status_data['deviation_status']['severity']}")
        
        # Test 5: Complete journey
        print(f"\n5. Testing journey completion...")
        response = await client.put(f"{API_BASE}/api/journey/{journey_id}/complete")
        assert response.status_code == 200
        print(f"   ✓ Journey completed successfully")
    
    print("\n" + "=" * 60)
    print("✓ Phase 1 validation completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Phase 2: Implement geometry utilities and deviation detection")
    print("- Phase 3: Implement Map Matching and GPS buffering")
    print("- Phase 4: Implement WebSocket for real-time updates")
    print("- Phase 5: Build frontend with Mapbox GL JS")


if __name__ == "__main__":
    print("Make sure the server is running: python -m app.main")
    print("Then run this test in another terminal\n")
    
    try:
        asyncio.run(test_phase_1())
    except httpx.ConnectError:
        print("\n❌ Error: Cannot connect to server")
        print("Please start the server first: cd backend && python -m app.main")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
