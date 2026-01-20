"""
Minimal WebSocket Test

Just tests basic WebSocket connection and connection_ack
"""
from fastapi.testclient import TestClient
from app.main import app
import json


def test_websocket_minimal():
    """Test WebSocket connection"""
    print("\n" + "=" * 70)
    print("TEST: Minimal WebSocket Connection")
    print("=" * 70)
    
    client = TestClient(app)
    
    # Create journey first
    start_req = {
        "origin": {"lat": 18.5246, "lng": 73.8786},
        "destination": {"lat": 18.9582, "lng": 72.8321},
        "travel_mode": "driving"
    }
    
    response = client.post("/api/journey/start", json=start_req)
    journey_id = response.json()["journey_id"]
    print(f"[INFO] Created journey: {journey_id}")
    
    # Connect to WebSocket
    with client.websocket_connect(f"/ws/journey/{journey_id}?client_id=test_client") as websocket:
        print("[PASS] WebSocket connected successfully")
        
        # Receive connection acknowledgment
        data = websocket.receive_json()
        print(f"[INFO] Received: {data}")
        
        assert data["type"] == "connection_ack", f"Expected connection_ack, got {data['type']}"
        assert data["journey_id"] == journey_id
        print("[PASS] Received connection_ack")
        
        print("[PASS] WebSocket connection test completed\n")


if __name__ == "__main__":
    test_websocket_minimal()
    print("[PASS] All tests passed!")
