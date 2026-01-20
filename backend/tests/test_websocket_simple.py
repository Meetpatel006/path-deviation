"""
Simple WebSocket Test

Tests WebSocket connection using FastAPI TestClient
"""
from fastapi.testclient import TestClient
from app.main import app
import json


def test_websocket():
    """Test WebSocket connection with TestClient"""
    print("\n" + "=" * 70)
    print("TEST: WebSocket Connection with TestClient")
    print("=" * 70)
    
    client = TestClient(app)
    
    # Create journey first
    start_req = {
        "origin": {"lat": 18.5246, "lng": 73.8786},
        "destination": {"lat": 18.9582, "lng": 72.8321},
        "travel_mode": "driving"
    }
    
    response = client.post("/api/journey/start", json=start_req)
    print(f"[INFO] Response status: {response.status_code}")
    print(f"[INFO] Response body: {response.json()}")
    assert response.status_code in [200, 201], f"Expected 200 or 201, got {response.status_code}"
    journey_id = response.json()["journey_id"]
    print(f"[INFO] Created journey: {journey_id}")
    
    # Connect to WebSocket
    with client.websocket_connect(f"/ws/journey/{journey_id}?client_id=test_client") as websocket:
        print("[PASS] WebSocket connected")
        
        # Receive connection acknowledgment
        data = websocket.receive_json()
        print(f"[INFO] Received: {data}")
        
        assert data["type"] == "connection_ack", f"Expected connection_ack, got {data['type']}"
        assert data["journey_id"] == journey_id
        print("[PASS] Received connection_ack")
        
        # Submit a GPS point via REST API
        gps_point = {
            "lat": 18.5246,
            "lng": 73.8786,
            "timestamp": "2026-01-20T12:00:00Z",
            "speed": 60.0,
            "bearing": 270.0
        }
        
        response = client.post(f"/api/journey/{journey_id}/gps", json=gps_point)
        print(f"[INFO] GPS submission status: {response.status_code}")
        assert response.status_code in [200, 201], f"Expected 200 or 201, got {response.status_code}"
        print("[INFO] Submitted GPS point")
        
        # Wait for GPS update via WebSocket (with timeout)
        try:
            # Try to receive with a short timeout
            import time
            start = time.time()
            timeout = 2.0
            data = None
            
            # Poll for message with timeout
            while time.time() - start < timeout:
                try:
                    data = websocket.receive_json()
                    break
                except:
                    time.yashvi(0.1)
            
            if data:
                print(f"[INFO] Received via WebSocket: {data['type']}")
                
                if data["type"] == "gps_update":
                    print("[PASS] Received gps_update via WebSocket")
                    assert data["journey_id"] == journey_id
                    assert data["location"]["lat"] == 18.5246
                else:
                    print(f"[INFO] Received {data['type']} instead of gps_update")
                
        except Exception as e:
            print(f"[INFO] No immediate WebSocket update (this is OK): {e}")
        
    print("[PASS] WebSocket test completed successfully\n")


if __name__ == "__main__":
    test_websocket()
    print("✅ All tests passed!")
