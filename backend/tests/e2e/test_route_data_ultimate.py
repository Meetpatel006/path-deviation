"""
Ultimate E2E Test Using Actual Route Data from routes/route.json

This comprehensive test uses the REAL route data (Google Maps Directions API response)
for the Pune to Mumbai route (155km) to validate the path deviation detection system.

Test Scenarios:
1. Perfect Route Following - Follow exact route path points
2. Early Deviation - Deviate after 10% of the route
3. Mid-Route Deviation - Take wrong turn at halfway point  
4. Return to Route - Deviate then return to correct path
5. Extended Stop - Stop for extended period mid-journey
6. Speed Variation - Test with varying speeds
7. GPS Accuracy Simulation - Test with varying GPS accuracy

Author: Path Deviation Detection System
Date: 2026-01-20
"""

import asyncio
import httpx
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import random
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/journey"

# Get the route.json path relative to this file
ROUTE_JSON_PATH = Path(__file__).parent.parent.parent.parent / "routes" / "route.json"


# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_section(text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- {text} ---{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")


class RouteDataLoader:
    """Load and parse route data from route.json"""
    
    def __init__(self, json_path: Path):
        self.json_path = json_path
        self.data = None
        self.route_points: List[Tuple[float, float]] = []
        self.steps_info: List[Dict] = []
        
    def load(self) -> bool:
        """Load route data from JSON file"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print_error(f"Failed to load route data: {e}")
            return False
    
    def extract_route_points(self) -> List[Tuple[float, float]]:
        """Extract all path coordinates from the route"""
        if not self.data:
            return []
        
        points = []
        routes = self.data.get("routes", [])
        
        if not routes:
            return []
        
        # Get the first route
        route = routes[0]
        legs = route.get("legs", [])
        
        for leg in legs:
            steps = leg.get("steps", [])
            for step in steps:
                # Get path points from each step
                path = step.get("path", [])
                for point in path:
                    lat = point.get("lat")
                    lng = point.get("lng")
                    if lat and lng:
                        points.append((lat, lng))
                        
                # Store step info
                self.steps_info.append({
                    "distance": step.get("distance", {}).get("value", 0),
                    "duration": step.get("duration", {}).get("value", 0),
                    "instructions": step.get("instructions", ""),
                    "start": step.get("start_point", {}),
                    "end": step.get("end_point", {})
                })
        
        self.route_points = points
        return points
    
    def get_origin_destination(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get origin and destination from route data"""
        if not self.data:
            return ((0, 0), (0, 0))
        
        routes = self.data.get("routes", [])
        if not routes:
            return ((0, 0), (0, 0))
        
        legs = routes[0].get("legs", [])
        if not legs:
            return ((0, 0), (0, 0))
        
        leg = legs[0]
        start = leg.get("start_location", {})
        end = leg.get("end_location", {})
        
        origin = (start.get("lat", 0), start.get("lng", 0))
        destination = (end.get("lat", 0), end.get("lng", 0))
        
        return (origin, destination)
    
    def get_route_info(self) -> Dict:
        """Get route metadata"""
        if not self.data:
            return {}
        
        routes = self.data.get("routes", [])
        if not routes:
            return {}
        
        leg = routes[0].get("legs", [{}])[0]
        
        return {
            "distance_text": leg.get("distance", {}).get("text", ""),
            "distance_meters": leg.get("distance", {}).get("value", 0),
            "duration_text": leg.get("duration", {}).get("text", ""),
            "duration_seconds": leg.get("duration", {}).get("value", 0),
            "start_address": leg.get("start_address", ""),
            "end_address": leg.get("end_address", ""),
            "total_points": len(self.route_points)
        }


def generate_gps_trace_from_points(
    points: List[Tuple[float, float]],
    sample_rate: int = 10,
    base_speed: float = 60.0,
    speed_variance: float = 10.0,
    accuracy_base: float = 10.0,
    accuracy_variance: float = 5.0
) -> List[Dict]:
    """
    Generate GPS trace from route points
    
    Args:
        points: List of (lat, lng) tuples from actual route
        sample_rate: Take every Nth point (to avoid too many points)
        base_speed: Base speed in km/h
        speed_variance: Speed variance (+/-)
        accuracy_base: Base GPS accuracy in meters
        accuracy_variance: Accuracy variance
    
    Returns:
        List of GPS point dictionaries
    """
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    sampled_points = points[::sample_rate]  # Sample every Nth point
    
    for i, (lat, lng) in enumerate(sampled_points):
        # Calculate bearing to next point
        bearing = 0.0
        if i < len(sampled_points) - 1:
            next_lat, next_lng = sampled_points[i + 1]
            import math
            bearing = math.degrees(math.atan2(
                next_lng - lng,
                next_lat - lat
            )) % 360
        
        # Vary speed and accuracy
        speed = base_speed + random.uniform(-speed_variance, speed_variance)
        speed = max(5.0, speed)
        
        accuracy = accuracy_base + random.uniform(-accuracy_variance, accuracy_variance)
        accuracy = max(3.0, accuracy)
        
        gps_point = {
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
            "accuracy": round(accuracy, 1),
            "speed": round(speed, 1),
            "bearing": round(bearing, 1)
        }
        gps_points.append(gps_point)
        
        # Increment time (based on estimated travel time between points)
        current_time += timedelta(seconds=random.uniform(5, 15))
    
    return gps_points


def generate_deviation_trace(
    points: List[Tuple[float, float]],
    deviation_start_pct: float = 0.3,
    deviation_end_pct: float = 0.5,
    deviation_offset: Tuple[float, float] = (0.01, 0.02)
) -> List[Tuple[float, float]]:
    """
    Generate a trace that deviates from the route
    
    Args:
        points: Original route points
        deviation_start_pct: Percentage along route to start deviation
        deviation_end_pct: Percentage along route to end deviation
        deviation_offset: (lat_offset, lng_offset) for deviation
    """
    result = []
    total = len(points)
    
    for i, (lat, lng) in enumerate(points):
        pct = i / total
        
        if deviation_start_pct <= pct <= deviation_end_pct:
            # Apply deviation - gradually increase then decrease
            deviation_progress = (pct - deviation_start_pct) / (deviation_end_pct - deviation_start_pct)
            if deviation_progress < 0.5:
                factor = deviation_progress * 2  # Ramp up
            else:
                factor = (1 - deviation_progress) * 2  # Ramp down
            
            lat_offset = deviation_offset[0] * factor
            lng_offset = deviation_offset[1] * factor
            result.append((lat + lat_offset, lng + lng_offset))
        else:
            result.append((lat, lng))
    
    return result


def generate_stopped_trace(
    points: List[Tuple[float, float]],
    stop_at_pct: float = 0.4,
    stop_duration_points: int = 20
) -> Tuple[List[Tuple[float, float]], List[bool]]:
    """
    Generate a trace with a stop in the middle
    
    Returns:
        - Modified points list with repeated stop location
        - Boolean list indicating which points are 'stopped'
    """
    result = []
    is_stopped = []
    total = len(points)
    stop_index = int(total * stop_at_pct)
    
    for i, point in enumerate(points):
        if i == stop_index:
            # Add multiple points at same location (stopped)
            for _ in range(stop_duration_points):
                result.append(point)
                is_stopped.append(True)
        else:
            result.append(point)
            is_stopped.append(False)
    
    return result, is_stopped


async def start_journey(
    client: httpx.AsyncClient,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    travel_mode: str = "driving"
) -> Dict:
    """Start a new journey"""
    payload = {
        "origin": {"lat": origin[0], "lng": origin[1]},
        "destination": {"lat": destination[0], "lng": destination[1]},
        "travel_mode": travel_mode
    }
    
    response = await client.post(f"{API_BASE}/start", json=payload)
    response.raise_for_status()
    return response.json()


async def submit_gps_point(
    client: httpx.AsyncClient,
    journey_id: str,
    gps_point: Dict
) -> Dict:
    """Submit a single GPS point"""
    response = await client.post(
        f"{API_BASE}/{journey_id}/gps",
        json=gps_point
    )
    response.raise_for_status()
    return response.json()


async def get_journey_status(client: httpx.AsyncClient, journey_id: str) -> Dict:
    """Get current journey status"""
    response = await client.get(f"{API_BASE}/{journey_id}")
    response.raise_for_status()
    return response.json()


async def complete_journey(client: httpx.AsyncClient, journey_id: str) -> Dict:
    """Mark journey as complete"""
    response = await client.put(f"{API_BASE}/{journey_id}/complete")
    response.raise_for_status()
    return response.json()


def analyze_deviation_status(status: Dict) -> Dict:
    """Analyze and summarize deviation status"""
    deviation = status.get("deviation_status", {})
    return {
        "spatial": deviation.get("spatial", "UNKNOWN"),
        "temporal": deviation.get("temporal", "UNKNOWN"),
        "directional": deviation.get("directional", "UNKNOWN"),
        "severity": deviation.get("severity", "UNKNOWN"),
        "progress": round(status.get("progress_percentage", 0), 1),
        "time_deviation": round(status.get("time_deviation", 0), 0),
        "route_probs": status.get("route_probabilities", {})
    }


async def run_test_scenario(
    name: str,
    description: str,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    gps_trace: List[Dict],
    expected_deviations: List[str],
    client: httpx.AsyncClient,
    stopped_flags: Optional[List[bool]] = None
) -> Dict:
    """Run a complete test scenario"""
    print_section(f"Test: {name}")
    print_info(f"Description: {description}")
    print_info(f"GPS Points: {len(gps_trace)}")
    
    results = {
        "name": name,
        "passed": True,
        "errors": [],
        "deviation_history": [],
        "final_status": None
    }
    
    try:
        # Step 1: Start journey
        print(f"\n  Starting journey...")
        journey_response = await start_journey(client, origin, destination)
        journey_id = journey_response["journey_id"]
        num_routes = len(journey_response.get("routes", []))
        print_success(f"Journey started: {journey_id[:8]}... ({num_routes} routes)")
        
        # Step 2: Submit GPS points
        print(f"\n  Submitting {len(gps_trace)} GPS points...")
        for i, gps_point in enumerate(gps_trace):
            # Modify speed if stopped
            if stopped_flags and i < len(stopped_flags) and stopped_flags[i]:
                gps_point = gps_point.copy()
                gps_point["speed"] = random.uniform(0, 0.5)
            
            await submit_gps_point(client, journey_id, gps_point)
            
            # Check status periodically
            if (i + 1) % 5 == 0 or i == len(gps_trace) - 1:
                status = await get_journey_status(client, journey_id)
                analysis = analyze_deviation_status(status)
                results["deviation_history"].append(analysis)
                
                severity_color = {
                    "normal": Colors.GREEN,
                    "minor": Colors.YELLOW,
                    "moderate": Colors.YELLOW,
                    "concerning": Colors.RED,
                    "major": Colors.RED
                }.get(analysis["severity"], Colors.ENDC)
                
                print(f"    Point {i+1}/{len(gps_trace)}: "
                      f"{severity_color}{analysis['severity'].upper()}{Colors.ENDC} "
                      f"[{analysis['spatial']}, {analysis['temporal']}, {analysis['directional']}] "
                      f"Progress: {analysis['progress']}%")
            
            await asyncio.sleep(0.02)
        
        # Step 3: Get final status
        final_status = await get_journey_status(client, journey_id)
        results["final_status"] = analyze_deviation_status(final_status)
        
        # Step 4: Verify expected deviations
        print(f"\n  Verifying expected deviations...")
        detected_deviations = set()
        for hist in results["deviation_history"]:
            detected_deviations.add(hist["spatial"])
            detected_deviations.add(hist["temporal"])
            detected_deviations.add(hist["directional"])
        
        for expected in expected_deviations:
            if expected in detected_deviations:
                print_success(f"Detected expected: {expected}")
            else:
                print_warning(f"Did not detect expected: {expected}")
                results["errors"].append(f"Missing expected deviation: {expected}")
        
        # Step 5: Complete journey
        await complete_journey(client, journey_id)
        print_success("Journey completed successfully")
        
    except Exception as e:
        print_error(f"Error: {str(e)}")
        results["passed"] = False
        results["errors"].append(str(e))
    
    if results["errors"]:
        results["passed"] = False
    
    return results


async def run_all_tests():
    """Run all E2E test scenarios using route.json data"""
    print_header("ULTIMATE E2E TEST - USING ROUTE.JSON DATA")
    print_info(f"Server: {BASE_URL}")
    print_info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Route Data: {ROUTE_JSON_PATH}")
    
    # Load route data
    print_section("Loading Route Data")
    loader = RouteDataLoader(ROUTE_JSON_PATH)
    
    if not loader.load():
        print_error("Failed to load route data. Exiting.")
        return []
    
    points = loader.extract_route_points()
    origin, destination = loader.get_origin_destination()
    route_info = loader.get_route_info()
    
    print_success(f"Loaded route: {route_info.get('start_address', 'Unknown')[:50]}...")
    print_success(f"To: {route_info.get('end_address', 'Unknown')[:50]}...")
    print_info(f"Distance: {route_info.get('distance_text', 'Unknown')}")
    print_info(f"Duration: {route_info.get('duration_text', 'Unknown')}")
    print_info(f"Total path points: {route_info.get('total_points', 0)}")
    
    if not points:
        print_error("No route points extracted. Exiting.")
        return []
    
    # Check server health
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            print_success(f"Server is healthy: {response.json()}")
        except Exception as e:
            print_error(f"Server not reachable: {e}")
            print_error("Please start the server with: uvicorn app.main:app --reload")
            return []
    
    all_results = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        
        # ================================================================
        # TEST 1: Perfect Route Following
        # ================================================================
        gps_trace_1 = generate_gps_trace_from_points(
            points,
            sample_rate=50,  # Sample every 50th point for manageable test
            base_speed=70.0,
            speed_variance=10.0
        )
        
        result_1 = await run_test_scenario(
            name="Perfect Route Following (Pune to Mumbai)",
            description="Follow the exact route from route.json",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_1,
            expected_deviations=["ON_ROUTE", "TOWARD_DEST"],
            client=client
        )
        all_results.append(result_1)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 2: Early Deviation (10% into route)
        # ================================================================
        deviated_points_2 = generate_deviation_trace(
            points,
            deviation_start_pct=0.08,
            deviation_end_pct=0.20,
            deviation_offset=(0.05, 0.08)  # Larger offset for 155km route
        )
        
        gps_trace_2 = generate_gps_trace_from_points(
            deviated_points_2,
            sample_rate=50,
            base_speed=50.0,
            speed_variance=10.0
        )
        
        result_2 = await run_test_scenario(
            name="Early Deviation (10% into route)",
            description="Deviate early in the journey, then return",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_2,
            expected_deviations=["OFF_ROUTE", "NEAR_ROUTE"],
            client=client
        )
        all_results.append(result_2)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 3: Mid-Route Deviation
        # ================================================================
        deviated_points_3 = generate_deviation_trace(
            points,
            deviation_start_pct=0.4,
            deviation_end_pct=0.60,
            deviation_offset=(0.06, 0.10)  # Larger offset for highway deviation
        )
        
        gps_trace_3 = generate_gps_trace_from_points(
            deviated_points_3,
            sample_rate=50,
            base_speed=60.0,
            speed_variance=15.0
        )
        
        result_3 = await run_test_scenario(
            name="Mid-Route Deviation (Highway)",
            description="Take wrong turn on highway, then correct",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_3,
            expected_deviations=["OFF_ROUTE", "NEAR_ROUTE"],
            client=client
        )
        all_results.append(result_3)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 4: Extended Stop Mid-Journey
        # ================================================================
        stopped_points, stopped_flags = generate_stopped_trace(
            points[::50],  # Sample first
            stop_at_pct=0.35,
            stop_duration_points=15
        )
        
        gps_trace_4 = generate_gps_trace_from_points(
            stopped_points,
            sample_rate=1,  # Already sampled
            base_speed=60.0,
            speed_variance=10.0
        )
        
        result_4 = await run_test_scenario(
            name="Extended Stop (Traffic/Rest)",
            description="Stop for extended period during journey",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_4,
            expected_deviations=["STOPPED"],
            client=client,
            stopped_flags=stopped_flags
        )
        all_results.append(result_4)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 5: Variable Speed (Slow Traffic)
        # ================================================================
        gps_trace_5 = generate_gps_trace_from_points(
            points,
            sample_rate=80,
            base_speed=25.0,  # Very slow - traffic
            speed_variance=5.0
        )
        
        result_5 = await run_test_scenario(
            name="Slow Traffic Conditions",
            description="Drive at slow speed due to heavy traffic",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_5,
            expected_deviations=["TOWARD_DEST"],
            client=client
        )
        all_results.append(result_5)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 6: High Speed (Highway)
        # ================================================================
        gps_trace_6 = generate_gps_trace_from_points(
            points,
            sample_rate=100,
            base_speed=100.0,  # Highway speed
            speed_variance=15.0
        )
        
        result_6 = await run_test_scenario(
            name="Highway Speed Driving",
            description="Drive at highway speed on expressway",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_6,
            expected_deviations=["TOWARD_DEST", "ON_TIME"],
            client=client
        )
        all_results.append(result_6)
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 7: Poor GPS Accuracy
        # ================================================================
        gps_trace_7 = generate_gps_trace_from_points(
            points,
            sample_rate=60,
            base_speed=55.0,
            speed_variance=20.0,
            accuracy_base=25.0,  # Poor GPS
            accuracy_variance=15.0
        )
        
        result_7 = await run_test_scenario(
            name="Poor GPS Accuracy Simulation",
            description="Simulate urban canyon/tunnel GPS issues",
            origin=origin,
            destination=destination,
            gps_trace=gps_trace_7,
            expected_deviations=["TOWARD_DEST"],
            client=client
        )
        all_results.append(result_7)
    
    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    print_header("TEST RESULTS SUMMARY")
    
    passed = sum(1 for r in all_results if r["passed"])
    failed = len(all_results) - passed
    
    for result in all_results:
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if result["passed"] else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"  [{status}] {result['name']}")
        
        if result["final_status"]:
            fs = result["final_status"]
            print(f"        Final: {fs['severity'].upper()} - "
                  f"[{fs['spatial']}, {fs['temporal']}, {fs['directional']}] "
                  f"Progress: {fs['progress']}%")
        
        if result["errors"]:
            for error in result["errors"]:
                print(f"        {Colors.RED}Error: {error}{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}Total: {passed}/{len(all_results)} tests passed{Colors.ENDC}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.ENDC}")
        print(f"\n{Colors.GREEN}The Path Deviation Detection System correctly handles{Colors.ENDC}")
        print(f"{Colors.GREEN}real route data from Pune to Mumbai (155km){Colors.ENDC}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  {failed} test(s) failed{Colors.ENDC}")
    
    return all_results


if __name__ == "__main__":
    print("\n" + "="*70)
    print("    ULTIMATE E2E TEST - USING REAL ROUTE.JSON DATA")
    print("    Testing with Pune to Mumbai route (155km)")
    print("="*70)
    
    try:
        results = asyncio.run(run_all_tests())
        sys.exit(0 if all(r["passed"] for r in results) else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
