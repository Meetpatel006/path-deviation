"""
Ultimate End-to-End Testing Script for Path Deviation Detection System

This script tests the complete system with real-world unseen data from Pune, India.
It simulates various driving scenarios including:
1. Normal on-route driving
2. Taking an alternate route
3. Deviating off-route (wrong turn)
4. Stopping/delays
5. Going in opposite direction

Real Pune Coordinates Used:
- Shivajinagar: 18.5302, 73.8474
- Deccan Gymkhana: 18.5167, 73.8417
- FC Road: 18.5284, 73.8419
- JM Road: 18.5203, 73.8401
- Pune Railway Station: 18.5285, 73.8742
- Koregaon Park: 18.5362, 73.8939
- Viman Nagar: 18.5679, 73.9143
- Hinjewadi IT Park: 18.5912, 73.7389
- Kothrud: 18.5074, 73.8077
- Swargate: 18.5018, 73.8636

Author: Path Deviation Detection System
Date: 2026-01-20
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
import random
import time
import sys

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/journey"

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

# ============================================================================
# PUNE REAL-WORLD COORDINATES
# ============================================================================

# Major landmarks in Pune
PUNE_LANDMARKS = {
    "shivajinagar": (18.5302, 73.8474),
    "deccan": (18.5167, 73.8417),
    "fc_road": (18.5284, 73.8419),
    "jm_road": (18.5203, 73.8401),
    "pune_station": (18.5285, 73.8742),
    "koregaon_park": (18.5362, 73.8939),
    "viman_nagar": (18.5679, 73.9143),
    "hinjewadi": (18.5912, 73.7389),
    "kothrud": (18.5074, 73.8077),
    "swargate": (18.5018, 73.8636),
    "aundh": (18.5590, 73.8077),
    "baner": (18.5590, 73.7868),
    "wakad": (18.5998, 73.7627),
    "magarpatta": (18.5141, 73.9265),
    "hadapsar": (18.5089, 73.9260),
    "camp": (18.5130, 73.8800),
    "model_colony": (18.5350, 73.8350),
    "law_college_road": (18.5182, 73.8291),
}

# Test Route 1: FC Road to Koregaon Park (via JM Road) - ~4km
ROUTE_1_POINTS = [
    # Starting from FC Road
    (18.5284, 73.8419),  # FC Road start
    (18.5274, 73.8432),  # Moving towards JM Road
    (18.5253, 73.8445),  # Near University
    (18.5223, 73.8467),  # Approaching JM Road junction
    (18.5203, 73.8490),  # JM Road
    (18.5198, 73.8530),  # Continuing east
    (18.5205, 73.8580),  # Near Deccan
    (18.5225, 73.8640),  # Moving towards Camp
    (18.5260, 73.8710),  # Camp area
    (18.5290, 73.8780),  # Approaching Koregaon Park
    (18.5320, 73.8840),  # Near destination
    (18.5350, 73.8900),  # Almost there
    (18.5362, 73.8939),  # Koregaon Park - destination
]

# Test Route 2: Shivajinagar to Hinjewadi (via Aundh) - ~15km
ROUTE_2_POINTS = [
    # Starting from Shivajinagar
    (18.5302, 73.8474),  # Shivajinagar start
    (18.5340, 73.8420),  # Moving towards Model Colony
    (18.5390, 73.8360),  # Model Colony area
    (18.5450, 73.8290),  # Approaching Aundh
    (18.5510, 73.8180),  # Aundh area
    (18.5560, 73.8090),  # Continuing towards Baner
    (18.5590, 73.7950),  # Near Baner
    (18.5650, 73.7850),  # Baner-Balewadi road
    (18.5750, 73.7720),  # Approaching Wakad
    (18.5830, 73.7580),  # Near Hinjewadi
    (18.5880, 73.7480),  # Almost there
    (18.5912, 73.7389),  # Hinjewadi IT Park - destination
]

# Deviation scenario: Wrong turn at midpoint
DEVIATION_POINTS = [
    # Starting normally
    (18.5284, 73.8419),  # FC Road start
    (18.5274, 73.8432),  # On route
    (18.5253, 73.8445),  # On route
    # WRONG TURN - going south instead of east
    (18.5220, 73.8420),  # Deviation starts
    (18.5180, 73.8400),  # Going towards Law College Road
    (18.5140, 73.8350),  # Further off route
    (18.5100, 73.8300),  # Significantly deviated
    # Correction back
    (18.5130, 73.8380),  # Starting to correct
    (18.5170, 73.8450),  # Getting back
    (18.5200, 73.8520),  # Back on track
]

# Opposite direction scenario
OPPOSITE_DIRECTION_POINTS = [
    (18.5284, 73.8419),  # Start at FC Road
    (18.5294, 73.8405),  # Going WEST instead of EAST
    (18.5310, 73.8380),  # Continuing wrong way
    (18.5330, 73.8350),  # Model Colony (opposite direction)
    (18.5360, 73.8310),  # Away from destination
]

# Stopped/delay scenario
STOPPED_SCENARIO_POINTS = [
    (18.5284, 73.8419),  # Start
    (18.5274, 73.8432),  # Moving
    (18.5260, 73.8445),  # Moving
    # Vehicle stopped (same location, multiple timestamps)
    (18.5260, 73.8446),  # Stopped
    (18.5260, 73.8446),  # Still stopped
    (18.5260, 73.8446),  # Still stopped
    (18.5260, 73.8447),  # Still stopped
    # Resuming
    (18.5250, 73.8460),  # Moving again
    (18.5235, 73.8480),  # Back to normal
]


def interpolate_points(start: Tuple[float, float], end: Tuple[float, float], num_points: int) -> List[Tuple[float, float]]:
    """Generate intermediate points between start and end"""
    points = []
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        lat = start[0] + t * (end[0] - start[0])
        lng = start[1] + t * (end[1] - start[1])
        # Add small random noise for realism
        lat += random.uniform(-0.0001, 0.0001)
        lng += random.uniform(-0.0001, 0.0001)
        points.append((lat, lng))
    return points


def generate_gps_trace(waypoints: List[Tuple[float, float]], 
                       points_per_segment: int = 3,
                       base_speed: float = 40.0,
                       speed_variance: float = 10.0) -> List[Dict]:
    """
    Generate a realistic GPS trace from waypoints
    
    Args:
        waypoints: List of (lat, lng) tuples
        points_per_segment: Number of GPS points between waypoints
        base_speed: Base speed in km/h
        speed_variance: Speed variance (+/-)
    
    Returns:
        List of GPS point dictionaries
    """
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    for i in range(len(waypoints) - 1):
        segment_points = interpolate_points(
            waypoints[i], 
            waypoints[i + 1], 
            points_per_segment
        )
        
        for j, (lat, lng) in enumerate(segment_points):
            # Calculate bearing (simplified)
            if i < len(waypoints) - 1:
                next_lat, next_lng = waypoints[i + 1]
                import math
                bearing = math.degrees(math.atan2(
                    next_lng - lng,
                    next_lat - lat
                )) % 360
            else:
                bearing = 0
            
            # Vary speed
            speed = base_speed + random.uniform(-speed_variance, speed_variance)
            speed = max(5.0, speed)  # Minimum 5 km/h
            
            gps_point = {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
                "accuracy": round(random.uniform(5.0, 15.0), 1),
                "speed": round(speed, 1),
                "bearing": round(bearing, 1)
            }
            gps_points.append(gps_point)
            
            # Increment time (5-10 seconds between points)
            current_time += timedelta(seconds=random.uniform(5, 10))
    
    return gps_points


def generate_stopped_trace(waypoints: List[Tuple[float, float]], 
                          stop_index: int = 3,
                          stop_duration_minutes: float = 5.0) -> List[Dict]:
    """Generate GPS trace with a stop in the middle"""
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    for i, (lat, lng) in enumerate(waypoints):
        if i == stop_index:
            # Generate multiple points at same location (stopped)
            num_stopped_points = int(stop_duration_minutes * 60 / 10)  # One point every 10 seconds
            for j in range(num_stopped_points):
                gps_point = {
                    "lat": round(lat + random.uniform(-0.00001, 0.00001), 6),
                    "lng": round(lng + random.uniform(-0.00001, 0.00001), 6),
                    "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
                    "accuracy": round(random.uniform(5.0, 15.0), 1),
                    "speed": round(random.uniform(0, 0.5), 1),  # Nearly zero speed
                    "bearing": round(random.uniform(0, 360), 1)
                }
                gps_points.append(gps_point)
                current_time += timedelta(seconds=10)
        else:
            bearing = random.uniform(0, 360)
            if i < len(waypoints) - 1:
                next_lat, next_lng = waypoints[i + 1]
                import math
                bearing = math.degrees(math.atan2(
                    next_lng - lng,
                    next_lat - lat
                )) % 360
            
            gps_point = {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
                "accuracy": round(random.uniform(5.0, 15.0), 1),
                "speed": round(random.uniform(30, 50), 1),
                "bearing": round(bearing, 1)
            }
            gps_points.append(gps_point)
            current_time += timedelta(seconds=random.uniform(5, 10))
    
    return gps_points


async def start_journey(client: httpx.AsyncClient, 
                       origin: Tuple[float, float], 
                       destination: Tuple[float, float],
                       travel_mode: str = "driving") -> Dict:
    """Start a new journey"""
    payload = {
        "origin": {"lat": origin[0], "lng": origin[1]},
        "destination": {"lat": destination[0], "lng": destination[1]},
        "travel_mode": travel_mode
    }
    
    response = await client.post(f"{API_BASE}/start", json=payload)
    response.raise_for_status()
    return response.json()


async def submit_gps_point(client: httpx.AsyncClient, 
                          journey_id: str, 
                          gps_point: Dict) -> Dict:
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
    client: httpx.AsyncClient
) -> Dict:
    """
    Run a complete test scenario
    
    Returns test results with pass/fail status
    """
    print_section(f"Test: {name}")
    print_info(f"Description: {description}")
    print_info(f"Origin: {origin}")
    print_info(f"Destination: {destination}")
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
        num_routes = len(journey_response["routes"])
        print_success(f"Journey started: {journey_id[:8]}... ({num_routes} routes)")
        
        # Step 2: Submit GPS points
        print(f"\n  Submitting {len(gps_trace)} GPS points...")
        for i, gps_point in enumerate(gps_trace):
            await submit_gps_point(client, journey_id, gps_point)
            
            # Check status every 3 points
            if (i + 1) % 3 == 0 or i == len(gps_trace) - 1:
                status = await get_journey_status(client, journey_id)
                analysis = analyze_deviation_status(status)
                results["deviation_history"].append(analysis)
                
                # Print status
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
            
            # Small delay between points (simulate real-time)
            await asyncio.sleep(0.05)
        
        # Step 3: Get final status
        final_status = await get_journey_status(client, journey_id)
        results["final_status"] = analyze_deviation_status(final_status)
        
        # Step 4: Verify expected deviations were detected
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
    """Run all E2E test scenarios"""
    print_header("PATH DEVIATION DETECTION - E2E TEST SUITE")
    print_info(f"Server: {BASE_URL}")
    print_info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check server health
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            print_success(f"Server is healthy: {response.json()}")
        except Exception as e:
            print_error(f"Server not reachable: {e}")
            print_error("Please start the server with: uvicorn app.main:app --reload")
            return
    
    all_results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # ================================================================
        # TEST 1: Normal On-Route Driving
        # ================================================================
        gps_trace_1 = generate_gps_trace(
            ROUTE_1_POINTS,
            points_per_segment=4,
            base_speed=35.0,
            speed_variance=5.0
        )
        
        result_1 = await run_test_scenario(
            name="Normal On-Route Driving",
            description="Drive from FC Road to Koregaon Park following the route",
            origin=PUNE_LANDMARKS["fc_road"],
            destination=PUNE_LANDMARKS["koregaon_park"],
            gps_trace=gps_trace_1,
            expected_deviations=["ON_ROUTE", "ON_TIME", "TOWARD_DEST"],
            client=client
        )
        all_results.append(result_1)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 2: Long Distance Route
        # ================================================================
        gps_trace_2 = generate_gps_trace(
            ROUTE_2_POINTS,
            points_per_segment=5,
            base_speed=50.0,
            speed_variance=10.0
        )
        
        result_2 = await run_test_scenario(
            name="Long Distance Route (Shivajinagar to Hinjewadi)",
            description="15km drive through Aundh and Baner",
            origin=PUNE_LANDMARKS["shivajinagar"],
            destination=PUNE_LANDMARKS["hinjewadi"],
            gps_trace=gps_trace_2,
            expected_deviations=["ON_TIME", "TOWARD_DEST"],
            client=client
        )
        all_results.append(result_2)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 3: Route Deviation (Wrong Turn)
        # ================================================================
        gps_trace_3 = generate_gps_trace(
            DEVIATION_POINTS,
            points_per_segment=3,
            base_speed=30.0,
            speed_variance=5.0
        )
        
        result_3 = await run_test_scenario(
            name="Route Deviation (Wrong Turn)",
            description="Take a wrong turn and deviate from planned route",
            origin=PUNE_LANDMARKS["fc_road"],
            destination=PUNE_LANDMARKS["koregaon_park"],
            gps_trace=gps_trace_3,
            expected_deviations=["OFF_ROUTE", "NEAR_ROUTE"],
            client=client
        )
        all_results.append(result_3)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 4: Vehicle Stopped
        # ================================================================
        gps_trace_4 = generate_stopped_trace(
            ROUTE_1_POINTS[:6],
            stop_index=3,
            stop_duration_minutes=2.0
        )
        
        result_4 = await run_test_scenario(
            name="Vehicle Stopped (Traffic/Signal)",
            description="Vehicle stops for 2 minutes mid-journey",
            origin=PUNE_LANDMARKS["fc_road"],
            destination=PUNE_LANDMARKS["koregaon_park"],
            gps_trace=gps_trace_4,
            expected_deviations=["STOPPED"],
            client=client
        )
        all_results.append(result_4)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 5: Opposite Direction
        # ================================================================
        gps_trace_5 = generate_gps_trace(
            OPPOSITE_DIRECTION_POINTS,
            points_per_segment=3,
            base_speed=35.0,
            speed_variance=5.0
        )
        
        result_5 = await run_test_scenario(
            name="Opposite Direction Travel",
            description="Driving away from destination",
            origin=PUNE_LANDMARKS["fc_road"],
            destination=PUNE_LANDMARKS["koregaon_park"],
            gps_trace=gps_trace_5,
            expected_deviations=["AWAY", "OFF_ROUTE"],
            client=client
        )
        all_results.append(result_5)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 6: Random Unseen Route (Camp to Viman Nagar)
        # ================================================================
        random_route = [
            PUNE_LANDMARKS["camp"],
            (18.5180, 73.8850),
            (18.5250, 73.8920),
            (18.5350, 73.8980),
            (18.5450, 73.9050),
            (18.5550, 73.9100),
            PUNE_LANDMARKS["viman_nagar"]
        ]
        
        gps_trace_6 = generate_gps_trace(
            random_route,
            points_per_segment=4,
            base_speed=40.0,
            speed_variance=8.0
        )
        
        result_6 = await run_test_scenario(
            name="Unseen Route (Camp to Viman Nagar)",
            description="Brand new route not in training data",
            origin=PUNE_LANDMARKS["camp"],
            destination=PUNE_LANDMARKS["viman_nagar"],
            gps_trace=gps_trace_6,
            expected_deviations=["TOWARD_DEST"],
            client=client
        )
        all_results.append(result_6)
        
        await asyncio.sleep(1)
        
        # ================================================================
        # TEST 7: Kothrud to Magarpatta (Cross-city)
        # ================================================================
        cross_city_route = [
            PUNE_LANDMARKS["kothrud"],
            (18.5050, 73.8200),
            (18.5020, 73.8400),
            (18.5030, 73.8600),
            (18.5080, 73.8800),
            (18.5100, 73.9000),
            PUNE_LANDMARKS["magarpatta"]
        ]
        
        gps_trace_7 = generate_gps_trace(
            cross_city_route,
            points_per_segment=5,
            base_speed=45.0,
            speed_variance=10.0
        )
        
        result_7 = await run_test_scenario(
            name="Cross-City Route (Kothrud to Magarpatta)",
            description="Long cross-city journey ~12km",
            origin=PUNE_LANDMARKS["kothrud"],
            destination=PUNE_LANDMARKS["magarpatta"],
            gps_trace=gps_trace_7,
            expected_deviations=["TOWARD_DEST", "ON_TIME"],
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
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  {failed} test(s) failed{Colors.ENDC}")
    
    return all_results


if __name__ == "__main__":
    print("\n" + "="*70)
    print("    ULTIMATE E2E TEST SCRIPT FOR PATH DEVIATION DETECTION")
    print("    Testing with UNSEEN real-world Pune coordinates")
    print("="*70)
    
    try:
        results = asyncio.run(run_all_tests())
        sys.exit(0 if all(r["passed"] for r in results) else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.ENDC}")
        sys.exit(1)
