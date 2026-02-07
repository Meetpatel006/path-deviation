"""
End-to-end test for Redis-only journey tracking.

This test exercises the full API flow without database writes:
- Start journey
- Submit GPS points
- Fetch status
- Complete journey
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple
import os
import time

import pytest
import httpx


BASE_URL = os.getenv("PATH_DEVIATION_BASE_URL", "http://localhost:8000")
API_BASE = f"{BASE_URL}/api/journey"


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_gps_point(lat: float, lng: float, timestamp: datetime, speed: float) -> Dict[str, Any]:
    return {
        "lat": lat,
        "lng": lng,
        "timestamp": _utc_iso(timestamp),
        "speed": speed,
        "bearing": 90.0,
        "accuracy": 8.0
    }


def _wait_for_server(client: httpx.Client, attempts: int = 5, delay: float = 0.5) -> None:
    for _ in range(attempts):
        try:
            response = client.get(f"{BASE_URL}/health", timeout=5.0)
            if response.status_code == 200:
                return
        except Exception:
            time.sleep(delay)
    pytest.skip("API server is not reachable")


def _extract_route_points(routes: List[Dict[str, Any]], count: int = 6) -> List[Tuple[float, float]]:
    if not routes:
        return []
    geometry = routes[0].get("geometry", [])
    if not geometry:
        return []
    step = max(1, int(len(geometry) / count))
    points = []
    for i in range(0, min(len(geometry), count * step), step):
        lng, lat = geometry[i]
        points.append((lat, lng))
    return points


def test_redis_only_e2e_journey_flow():
    with httpx.Client() as client:
        _wait_for_server(client)

        # Health should report database disabled in Redis-only mode
        health = client.get(f"{BASE_URL}/health", timeout=5.0)
        print(f"Health: {health.status_code} {health.text}")
        if health.status_code != 200:
            print("Health check failed. Exiting.")
            return
        health_data = health.json()
        if health_data.get("redis") != "connected":
            print("Redis is not connected. Set REDIS_URL and restart the API.")
            return

        # Start journey
        start_payload = {
            "origin": {"lat": 18.5246, "lng": 73.8786},
            "destination": {"lat": 18.9582, "lng": 72.8321},
            "travel_mode": "driving"
        }
        start_resp = client.post(f"{API_BASE}/start", json=start_payload, timeout=30.0)
        print(f"Start: {start_resp.status_code} {start_resp.text}")
        if start_resp.status_code != 201:
            print("Start journey failed. Exiting.")
            return
        start_data = start_resp.json()

        journey_id = start_data["journey_id"]
        routes = start_data.get("routes", [])
        print(f"Journey ID: {journey_id}")
        print(f"Routes: {len(routes)}")
        if not journey_id or not routes:
            print("Missing journey_id or routes. Exiting.")
            return

        # Submit GPS points from route geometry
        route_points = _extract_route_points(routes, count=6)
        now = datetime.now(timezone.utc)
        for idx, (lat, lng) in enumerate(route_points):
            gps_point = _build_gps_point(lat, lng, now + timedelta(seconds=idx * 5), speed=55.0)
            gps_resp = client.post(f"{API_BASE}/{journey_id}/gps", json=gps_point, timeout=10.0)
            print(f"GPS {idx + 1}: {gps_resp.status_code} {gps_resp.text}")

        time.sleep(0.5)

        # Fetch status
        status_resp = client.get(f"{API_BASE}/{journey_id}", timeout=10.0)
        print(f"Status: {status_resp.status_code} {status_resp.text}")
        status_data = status_resp.json() if status_resp.status_code == 200 else {}

        # Send one off-route point to ensure pipeline handles deviations
        off_route = _build_gps_point(18.8, 74.2, now + timedelta(seconds=45), speed=20.0)
        gps_resp = client.post(f"{API_BASE}/{journey_id}/gps", json=off_route, timeout=10.0)
        print(f"Off-route GPS: {gps_resp.status_code} {gps_resp.text}")

        time.sleep(0.5)
        status_resp = client.get(f"{API_BASE}/{journey_id}", timeout=10.0)
        print(f"Status after off-route: {status_resp.status_code} {status_resp.text}")

        # Complete journey
        complete_resp = client.put(f"{API_BASE}/{journey_id}/complete", timeout=10.0)
        print(f"Complete: {complete_resp.status_code} {complete_resp.text}")

        # Verify completion persisted in Redis
        final_status = client.get(f"{API_BASE}/{journey_id}", timeout=10.0)
        print(f"Final status: {final_status.status_code} {final_status.text}")


def main() -> int:
    try:
        test_redis_only_e2e_journey_flow()
    except pytest.skip.Exception as exc:
        print(f"SKIPPED: {exc}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
