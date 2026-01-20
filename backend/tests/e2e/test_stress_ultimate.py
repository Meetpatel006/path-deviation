"""
🔥 ULTIMATE STRESS TEST for Path Deviation Detection System 🔥

This script performs extreme stress testing including:
1. Concurrent journey handling (multiple simultaneous journeys)
2. High-frequency GPS point submission (rapid fire)
3. Large batch processing (100+ GPS points per journey)
4. Edge cases (boundary conditions, invalid data handling)
5. Memory and performance stress
6. Rapid route switching simulation
7. Chaos testing (random deviations, U-turns, zigzag patterns)

WARNING: This test will push the system to its limits!

Author: Path Deviation Detection System
Date: 2026-01-20
"""

import asyncio
import httpx
import json
import random
import time
import sys
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import threading

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/journey"

# Stress test parameters
CONCURRENT_JOURNEYS = 10          # Number of simultaneous journeys
GPS_POINTS_PER_JOURNEY = 50       # Points per journey in stress test
RAPID_FIRE_POINTS = 100           # Points for rapid fire test
RAPID_FIRE_DELAY_MS = 10          # Milliseconds between rapid fire points
CHAOS_ITERATIONS = 20             # Number of chaos test iterations

# Color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    BLINK = '\033[5m'

def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'🔥'*3} {text} {'🔥'*3}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

def print_section(text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}▶ {text}{Colors.ENDC}")

def print_success(text: str):
    print(f"{Colors.GREEN}  ✓ {text}{Colors.ENDC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}  ⚠ {text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.RED}  ✗ {text}{Colors.ENDC}")

def print_info(text: str):
    print(f"{Colors.BLUE}  ℹ {text}{Colors.ENDC}")

def print_metric(name: str, value: str):
    print(f"    {Colors.CYAN}{name}:{Colors.ENDC} {value}")

# ============================================================================
# PUNE COORDINATES DATABASE
# ============================================================================

PUNE_LOCATIONS = [
    ("Shivajinagar", 18.5302, 73.8474),
    ("Deccan", 18.5167, 73.8417),
    ("FC Road", 18.5284, 73.8419),
    ("JM Road", 18.5203, 73.8401),
    ("Pune Station", 18.5285, 73.8742),
    ("Koregaon Park", 18.5362, 73.8939),
    ("Viman Nagar", 18.5679, 73.9143),
    ("Hinjewadi", 18.5912, 73.7389),
    ("Kothrud", 18.5074, 73.8077),
    ("Swargate", 18.5018, 73.8636),
    ("Aundh", 18.5590, 73.8077),
    ("Baner", 18.5590, 73.7868),
    ("Wakad", 18.5998, 73.7627),
    ("Magarpatta", 18.5141, 73.9265),
    ("Hadapsar", 18.5089, 73.9260),
    ("Camp", 18.5130, 73.8800),
    ("Model Colony", 18.5350, 73.8350),
    ("Law College Road", 18.5182, 73.8291),
    ("Pimple Saudagar", 18.5987, 73.8056),
    ("Kalyani Nagar", 18.5463, 73.9020),
]


def get_random_route() -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Get two random different locations for origin/destination"""
    loc1, loc2 = random.sample(PUNE_LOCATIONS, 2)
    return (loc1[1], loc1[2]), (loc2[1], loc2[2])


def generate_random_gps_trace(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    num_points: int,
    chaos_level: float = 0.0  # 0.0 = straight, 1.0 = maximum chaos
) -> List[Dict]:
    """Generate GPS trace with configurable chaos level"""
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    for i in range(num_points):
        # Linear interpolation with chaos
        t = i / (num_points - 1) if num_points > 1 else 0
        
        # Base position
        lat = origin[0] + t * (destination[0] - origin[0])
        lng = origin[1] + t * (destination[1] - origin[1])
        
        # Add chaos (random deviation)
        chaos_offset = chaos_level * 0.01  # Max ~1km deviation at chaos_level=1
        lat += random.uniform(-chaos_offset, chaos_offset)
        lng += random.uniform(-chaos_offset, chaos_offset)
        
        # Random speed (with chaos affecting consistency)
        base_speed = 40.0
        speed_chaos = chaos_level * 30
        speed = max(0, base_speed + random.uniform(-speed_chaos, speed_chaos))
        
        # Bearing (with chaos causing sudden direction changes)
        import math
        if i < num_points - 1:
            next_t = (i + 1) / (num_points - 1)
            next_lat = origin[0] + next_t * (destination[0] - origin[0])
            next_lng = origin[1] + next_t * (destination[1] - origin[1])
            bearing = math.degrees(math.atan2(next_lng - lng, next_lat - lat)) % 360
        else:
            bearing = random.uniform(0, 360)
        
        # Add bearing chaos
        bearing += random.uniform(-chaos_level * 90, chaos_level * 90)
        bearing = bearing % 360
        
        gps_point = {
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
            "accuracy": round(random.uniform(5.0, 20.0), 1),
            "speed": round(speed, 1),
            "bearing": round(bearing, 1)
        }
        gps_points.append(gps_point)
        
        # Time increment with chaos (variable intervals)
        base_interval = 5
        interval_chaos = chaos_level * 20
        interval = max(1, base_interval + random.uniform(-interval_chaos, interval_chaos))
        current_time += timedelta(seconds=interval)
    
    return gps_points


def generate_zigzag_trace(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    num_points: int,
    zigzag_amplitude: float = 0.005
) -> List[Dict]:
    """Generate a zigzag pattern trace"""
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        
        # Base position
        lat = origin[0] + t * (destination[0] - origin[0])
        lng = origin[1] + t * (destination[1] - origin[1])
        
        # Zigzag offset (perpendicular to route)
        import math
        zigzag = math.sin(i * math.pi / 2) * zigzag_amplitude
        
        # Calculate perpendicular direction
        route_bearing = math.atan2(
            destination[1] - origin[1],
            destination[0] - origin[0]
        )
        perp_bearing = route_bearing + math.pi / 2
        
        lat += zigzag * math.cos(perp_bearing)
        lng += zigzag * math.sin(perp_bearing)
        
        gps_point = {
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
            "accuracy": round(random.uniform(5.0, 15.0), 1),
            "speed": round(random.uniform(20, 50), 1),
            "bearing": round(random.uniform(0, 360), 1)
        }
        gps_points.append(gps_point)
        current_time += timedelta(seconds=random.uniform(3, 8))
    
    return gps_points


def generate_uturn_trace(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    num_points: int
) -> List[Dict]:
    """Generate trace with U-turn in the middle"""
    gps_points = []
    current_time = datetime.now(timezone.utc)
    
    mid_point = num_points // 2
    
    for i in range(num_points):
        if i < mid_point:
            # Going towards destination
            t = i / mid_point
            lat = origin[0] + t * (destination[0] - origin[0]) * 0.5
            lng = origin[1] + t * (destination[1] - origin[1]) * 0.5
        else:
            # U-turn - going back then forward again
            t = (i - mid_point) / (num_points - mid_point)
            if t < 0.3:
                # Going back
                back_t = t / 0.3
                lat = origin[0] + (0.5 - back_t * 0.2) * (destination[0] - origin[0])
                lng = origin[1] + (0.5 - back_t * 0.2) * (destination[1] - origin[1])
            else:
                # Going forward again
                forward_t = (t - 0.3) / 0.7
                lat = origin[0] + (0.3 + forward_t * 0.7) * (destination[0] - origin[0])
                lng = origin[1] + (0.3 + forward_t * 0.7) * (destination[1] - origin[1])
        
        gps_point = {
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "timestamp": current_time.isoformat().replace('+00:00', 'Z'),
            "accuracy": round(random.uniform(5.0, 15.0), 1),
            "speed": round(random.uniform(20, 50), 1),
            "bearing": round(random.uniform(0, 360), 1)
        }
        gps_points.append(gps_point)
        current_time += timedelta(seconds=random.uniform(3, 8))
    
    return gps_points


class StressTestMetrics:
    """Collect and report stress test metrics"""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.errors: List[str] = []
        self.successful_requests = 0
        self.failed_requests = 0
        self.start_time = None
        self.end_time = None
        self.lock = threading.Lock()
    
    def record_request(self, duration: float, success: bool, error: str = None):
        with self.lock:
            self.response_times.append(duration)
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                if error:
                    self.errors.append(error)
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.end_time = time.time()
    
    def report(self) -> Dict:
        if not self.response_times:
            return {"error": "No data collected"}
        
        total_time = self.end_time - self.start_time if self.end_time else 0
        
        return {
            "total_requests": self.successful_requests + self.failed_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{(self.successful_requests / (self.successful_requests + self.failed_requests)) * 100:.1f}%",
            "total_time_seconds": round(total_time, 2),
            "requests_per_second": round((self.successful_requests + self.failed_requests) / total_time, 2) if total_time > 0 else 0,
            "response_times": {
                "min_ms": round(min(self.response_times) * 1000, 2),
                "max_ms": round(max(self.response_times) * 1000, 2),
                "avg_ms": round(statistics.mean(self.response_times) * 1000, 2),
                "median_ms": round(statistics.median(self.response_times) * 1000, 2),
                "p95_ms": round(sorted(self.response_times)[int(len(self.response_times) * 0.95)] * 1000, 2) if len(self.response_times) > 20 else "N/A",
                "p99_ms": round(sorted(self.response_times)[int(len(self.response_times) * 0.99)] * 1000, 2) if len(self.response_times) > 100 else "N/A",
            },
            "errors": self.errors[:10]  # First 10 errors
        }


async def start_journey(client: httpx.AsyncClient, origin: Tuple[float, float], 
                       destination: Tuple[float, float]) -> Optional[str]:
    """Start a journey and return journey_id"""
    try:
        response = await client.post(
            f"{API_BASE}/start",
            json={
                "origin": {"lat": origin[0], "lng": origin[1]},
                "destination": {"lat": destination[0], "lng": destination[1]},
                "travel_mode": "driving"
            }
        )
        response.raise_for_status()
        return response.json()["journey_id"]
    except Exception as e:
        return None


async def submit_gps_point(client: httpx.AsyncClient, journey_id: str, 
                          gps_point: Dict, metrics: StressTestMetrics) -> bool:
    """Submit GPS point and record metrics"""
    start = time.time()
    try:
        response = await client.post(
            f"{API_BASE}/{journey_id}/gps",
            json=gps_point
        )
        duration = time.time() - start
        success = response.status_code == 200
        metrics.record_request(duration, success)
        return success
    except Exception as e:
        duration = time.time() - start
        metrics.record_request(duration, False, str(e))
        return False


async def get_journey_status(client: httpx.AsyncClient, journey_id: str,
                            metrics: StressTestMetrics) -> Optional[Dict]:
    """Get journey status and record metrics"""
    start = time.time()
    try:
        response = await client.get(f"{API_BASE}/{journey_id}")
        duration = time.time() - start
        success = response.status_code == 200
        metrics.record_request(duration, success)
        if success:
            return response.json()
        return None
    except Exception as e:
        duration = time.time() - start
        metrics.record_request(duration, False, str(e))
        return None


# ============================================================================
# STRESS TEST 1: Concurrent Journeys
# ============================================================================

async def test_concurrent_journeys(num_journeys: int, points_per_journey: int) -> Dict:
    """Test multiple simultaneous journeys"""
    print_section(f"CONCURRENT JOURNEYS TEST ({num_journeys} journeys, {points_per_journey} points each)")
    
    metrics = StressTestMetrics()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Start all journeys
        print_info("Starting journeys...")
        journey_ids = []
        for i in range(num_journeys):
            origin, destination = get_random_route()
            journey_id = await start_journey(client, origin, destination)
            if journey_id:
                journey_ids.append({
                    "id": journey_id,
                    "origin": origin,
                    "destination": destination
                })
        
        print_success(f"Started {len(journey_ids)} journeys")
        
        if not journey_ids:
            print_error("No journeys started!")
            return {"error": "No journeys started"}
        
        # Generate GPS traces for all journeys
        traces = {}
        for j in journey_ids:
            traces[j["id"]] = generate_random_gps_trace(
                j["origin"], j["destination"], 
                points_per_journey, 
                chaos_level=0.2
            )
        
        # Submit GPS points concurrently
        print_info("Submitting GPS points concurrently...")
        metrics.start()
        
        async def submit_journey_points(journey_id: str, gps_trace: List[Dict]):
            for gps_point in gps_trace:
                await submit_gps_point(client, journey_id, gps_point, metrics)
                await asyncio.sleep(0.01)  # Small delay
        
        # Run all journeys concurrently
        await asyncio.gather(*[
            submit_journey_points(j["id"], traces[j["id"]]) 
            for j in journey_ids
        ])
        
        metrics.stop()
        
        # Get final status for all journeys
        print_info("Fetching final status...")
        final_statuses = []
        for j in journey_ids:
            status = await get_journey_status(client, j["id"], metrics)
            if status:
                final_statuses.append(status)
        
        print_success(f"Completed {len(final_statuses)} journeys")
    
    return metrics.report()


# ============================================================================
# STRESS TEST 2: Rapid Fire GPS Points
# ============================================================================

async def test_rapid_fire(num_points: int, delay_ms: int) -> Dict:
    """Test rapid GPS point submission"""
    print_section(f"RAPID FIRE TEST ({num_points} points, {delay_ms}ms delay)")
    
    metrics = StressTestMetrics()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Start a journey
        origin, destination = get_random_route()
        journey_id = await start_journey(client, origin, destination)
        
        if not journey_id:
            print_error("Failed to start journey!")
            return {"error": "Failed to start journey"}
        
        print_success(f"Journey started: {journey_id[:8]}...")
        
        # Generate trace
        gps_trace = generate_random_gps_trace(
            origin, destination, num_points, chaos_level=0.1
        )
        
        # Rapid fire submission
        print_info(f"Firing {num_points} GPS points...")
        metrics.start()
        
        for i, gps_point in enumerate(gps_trace):
            await submit_gps_point(client, journey_id, gps_point, metrics)
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)
            
            # Progress indicator
            if (i + 1) % 25 == 0:
                print(f"    Progress: {i+1}/{num_points} points submitted")
        
        metrics.stop()
        
        # Final status
        final_status = await get_journey_status(client, journey_id, metrics)
        if final_status:
            print_success(f"Final status: {final_status['deviation_status']['severity'].upper()}")
    
    return metrics.report()


# ============================================================================
# STRESS TEST 3: Chaos Testing
# ============================================================================

async def test_chaos(iterations: int) -> Dict:
    """Test with chaotic, unpredictable GPS patterns"""
    print_section(f"CHAOS TEST ({iterations} iterations)")
    
    metrics = StressTestMetrics()
    chaos_results = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(iterations):
            chaos_type = random.choice(["high_chaos", "zigzag", "uturn", "random_stops"])
            origin, destination = get_random_route()
            
            # Start journey
            journey_id = await start_journey(client, origin, destination)
            if not journey_id:
                continue
            
            # Generate chaotic trace
            num_points = random.randint(15, 30)
            
            if chaos_type == "high_chaos":
                gps_trace = generate_random_gps_trace(
                    origin, destination, num_points, chaos_level=0.8
                )
            elif chaos_type == "zigzag":
                gps_trace = generate_zigzag_trace(
                    origin, destination, num_points, zigzag_amplitude=0.008
                )
            elif chaos_type == "uturn":
                gps_trace = generate_uturn_trace(
                    origin, destination, num_points
                )
            else:  # random_stops
                gps_trace = generate_random_gps_trace(
                    origin, destination, num_points, chaos_level=0.3
                )
                # Add random stops
                for j in range(0, len(gps_trace), 5):
                    if j < len(gps_trace):
                        gps_trace[j]["speed"] = round(random.uniform(0, 1), 1)
            
            metrics.start() if i == 0 else None
            
            # Submit points
            for gps_point in gps_trace:
                await submit_gps_point(client, journey_id, gps_point, metrics)
                await asyncio.sleep(0.02)
            
            # Get status
            status = await get_journey_status(client, journey_id, metrics)
            if status:
                chaos_results.append({
                    "type": chaos_type,
                    "severity": status["deviation_status"]["severity"],
                    "spatial": status["deviation_status"]["spatial"],
                    "progress": status["progress_percentage"]
                })
            
            print(f"    Iteration {i+1}/{iterations}: {chaos_type} -> "
                  f"{status['deviation_status']['severity'] if status else 'ERROR'}")
        
        metrics.stop()
    
    # Analyze chaos results
    severity_counts = {}
    for r in chaos_results:
        sev = r["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    result = metrics.report()
    result["chaos_analysis"] = {
        "severity_distribution": severity_counts,
        "total_chaos_tests": len(chaos_results)
    }
    
    return result


# ============================================================================
# STRESS TEST 4: Edge Cases
# ============================================================================

async def test_edge_cases() -> Dict:
    """Test edge cases and boundary conditions"""
    print_section("EDGE CASES TEST")
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: Very short journey (same origin/destination area)
        print_info("Testing very short journey...")
        try:
            response = await client.post(
                f"{API_BASE}/start",
                json={
                    "origin": {"lat": 18.5302, "lng": 73.8474},
                    "destination": {"lat": 18.5305, "lng": 73.8477},  # ~50m away
                    "travel_mode": "driving"
                }
            )
            if response.status_code in [200, 201]:
                print_success("Short journey: PASS")
                results["passed"] += 1
            else:
                print_warning(f"Short journey: {response.status_code}")
                results["failed"] += 1
            results["tests"].append({"name": "short_journey", "status": response.status_code})
        except Exception as e:
            print_error(f"Short journey: {e}")
            results["failed"] += 1
        
        # Test 2: GPS point with extreme values
        print_info("Testing extreme GPS values...")
        origin, dest = get_random_route()
        journey_id = await start_journey(client, origin, dest)
        if journey_id:
            extreme_points = [
                {"lat": 18.5, "lng": 73.8, "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                 "speed": 0.0, "bearing": 0.0, "accuracy": 100.0},  # Very low accuracy
                {"lat": 18.5, "lng": 73.8, "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                 "speed": 200.0, "bearing": 0.0, "accuracy": 5.0},  # Very high speed
                {"lat": 18.5, "lng": 73.8, "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                 "speed": 30.0, "bearing": 359.9, "accuracy": 5.0},  # Edge bearing
            ]
            
            for i, point in enumerate(extreme_points):
                try:
                    response = await client.post(f"{API_BASE}/{journey_id}/gps", json=point)
                    if response.status_code == 200:
                        print_success(f"Extreme point {i+1}: PASS")
                        results["passed"] += 1
                    else:
                        print_warning(f"Extreme point {i+1}: {response.status_code}")
                        results["failed"] += 1
                except Exception as e:
                    print_error(f"Extreme point {i+1}: {e}")
                    results["failed"] += 1
        
        # Test 3: Invalid journey ID
        print_info("Testing invalid journey ID...")
        try:
            response = await client.get(f"{API_BASE}/invalid-uuid-12345")
            if response.status_code == 404:
                print_success("Invalid journey ID: PASS (correctly returned 404)")
                results["passed"] += 1
            else:
                print_warning(f"Invalid journey ID: Expected 404, got {response.status_code}")
                results["failed"] += 1
            results["tests"].append({"name": "invalid_journey_id", "status": response.status_code})
        except Exception as e:
            print_error(f"Invalid journey ID: {e}")
            results["failed"] += 1
        
        # Test 4: Duplicate GPS points (same timestamp)
        print_info("Testing duplicate timestamps...")
        origin, dest = get_random_route()
        journey_id = await start_journey(client, origin, dest)
        if journey_id:
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            dup_point = {
                "lat": 18.53, "lng": 73.85, "timestamp": timestamp,
                "speed": 30.0, "bearing": 45.0, "accuracy": 10.0
            }
            
            try:
                # Submit same point twice
                await client.post(f"{API_BASE}/{journey_id}/gps", json=dup_point)
                response = await client.post(f"{API_BASE}/{journey_id}/gps", json=dup_point)
                if response.status_code == 200:
                    print_success("Duplicate timestamp: PASS (handled gracefully)")
                    results["passed"] += 1
                else:
                    print_warning(f"Duplicate timestamp: {response.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print_error(f"Duplicate timestamp: {e}")
                results["failed"] += 1
        
        # Test 5: Very old timestamp
        print_info("Testing old timestamp...")
        origin, dest = get_random_route()
        journey_id = await start_journey(client, origin, dest)
        if journey_id:
            old_timestamp = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')
            old_point = {
                "lat": 18.53, "lng": 73.85, "timestamp": old_timestamp,
                "speed": 30.0, "bearing": 45.0, "accuracy": 10.0
            }
            
            try:
                response = await client.post(f"{API_BASE}/{journey_id}/gps", json=old_point)
                if response.status_code == 200:
                    print_success("Old timestamp: PASS (accepted)")
                    results["passed"] += 1
                else:
                    print_warning(f"Old timestamp: {response.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print_error(f"Old timestamp: {e}")
                results["failed"] += 1
    
    results["summary"] = f"{results['passed']} passed, {results['failed']} failed"
    return results


# ============================================================================
# STRESS TEST 5: Load Test (High Volume)
# ============================================================================

async def test_high_volume(total_requests: int) -> Dict:
    """Test high volume of requests"""
    print_section(f"HIGH VOLUME TEST ({total_requests} total requests)")
    
    metrics = StressTestMetrics()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Start multiple journeys
        num_journeys = 5
        journey_data = []
        
        print_info(f"Starting {num_journeys} journeys...")
        for _ in range(num_journeys):
            origin, dest = get_random_route()
            journey_id = await start_journey(client, origin, dest)
            if journey_id:
                journey_data.append({
                    "id": journey_id,
                    "origin": origin,
                    "dest": dest,
                    "current_lat": origin[0],
                    "current_lng": origin[1]
                })
        
        print_success(f"Started {len(journey_data)} journeys")
        
        # Generate and submit requests
        print_info(f"Submitting {total_requests} requests...")
        metrics.start()
        
        requests_sent = 0
        
        async def submit_batch(journey: Dict, batch_size: int):
            nonlocal requests_sent
            for _ in range(batch_size):
                # Gradually move towards destination
                t = min(1.0, requests_sent / total_requests)
                lat = journey["origin"][0] + t * (journey["dest"][0] - journey["origin"][0])
                lng = journey["origin"][1] + t * (journey["dest"][1] - journey["origin"][1])
                lat += random.uniform(-0.001, 0.001)
                lng += random.uniform(-0.001, 0.001)
                
                gps_point = {
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "speed": round(random.uniform(20, 60), 1),
                    "bearing": round(random.uniform(0, 360), 1),
                    "accuracy": round(random.uniform(5, 15), 1)
                }
                
                await submit_gps_point(client, journey["id"], gps_point, metrics)
                requests_sent += 1
                
                if requests_sent % 100 == 0:
                    print(f"    Progress: {requests_sent}/{total_requests} requests")
        
        # Distribute requests across journeys
        requests_per_journey = total_requests // len(journey_data)
        
        await asyncio.gather(*[
            submit_batch(j, requests_per_journey) 
            for j in journey_data
        ])
        
        metrics.stop()
        
        print_success(f"Completed {requests_sent} requests")
    
    return metrics.report()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def run_all_stress_tests():
    """Run all stress tests"""
    print_header("🔥 ULTIMATE STRESS TEST SUITE 🔥")
    print_info(f"Server: {BASE_URL}")
    print_info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Python: {sys.version.split()[0]}")
    
    # Check server health
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            print_success(f"Server healthy: {response.json()['status']}")
        except Exception as e:
            print_error(f"Server not reachable: {e}")
            print_error("Start server with: uvicorn app.main:app --reload")
            return
    
    all_results = {}
    
    # Run stress tests
    try:
        # Test 1: Concurrent Journeys
        print("\n")
        result1 = await test_concurrent_journeys(CONCURRENT_JOURNEYS, GPS_POINTS_PER_JOURNEY)
        all_results["concurrent_journeys"] = result1
        print_metric("Requests/sec", str(result1.get("requests_per_second", "N/A")))
        print_metric("Success rate", result1.get("success_rate", "N/A"))
        print_metric("Avg response", f"{result1.get('response_times', {}).get('avg_ms', 'N/A')}ms")
        
        await asyncio.sleep(2)
        
        # Test 2: Rapid Fire
        print("\n")
        result2 = await test_rapid_fire(RAPID_FIRE_POINTS, RAPID_FIRE_DELAY_MS)
        all_results["rapid_fire"] = result2
        print_metric("Requests/sec", str(result2.get("requests_per_second", "N/A")))
        print_metric("Success rate", result2.get("success_rate", "N/A"))
        print_metric("Avg response", f"{result2.get('response_times', {}).get('avg_ms', 'N/A')}ms")
        
        await asyncio.sleep(2)
        
        # Test 3: Chaos Testing
        print("\n")
        result3 = await test_chaos(CHAOS_ITERATIONS)
        all_results["chaos"] = result3
        if "chaos_analysis" in result3:
            print_metric("Severity distribution", str(result3["chaos_analysis"]["severity_distribution"]))
        
        await asyncio.sleep(2)
        
        # Test 4: Edge Cases
        print("\n")
        result4 = await test_edge_cases()
        all_results["edge_cases"] = result4
        print_metric("Results", result4.get("summary", "N/A"))
        
        await asyncio.sleep(2)
        
        # Test 5: High Volume
        print("\n")
        result5 = await test_high_volume(500)
        all_results["high_volume"] = result5
        print_metric("Requests/sec", str(result5.get("requests_per_second", "N/A")))
        print_metric("Success rate", result5.get("success_rate", "N/A"))
        print_metric("P95 latency", f"{result5.get('response_times', {}).get('p95_ms', 'N/A')}ms")
        
    except Exception as e:
        print_error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    # Final Summary
    print_header("📊 STRESS TEST SUMMARY")
    
    total_requests = 0
    total_success = 0
    all_response_times = []
    
    for test_name, result in all_results.items():
        if isinstance(result, dict) and "total_requests" in result:
            total_requests += result["total_requests"]
            total_success += result.get("successful", 0)
            if "response_times" in result and isinstance(result["response_times"], dict):
                avg = result["response_times"].get("avg_ms")
                if avg and avg != "N/A":
                    all_response_times.append(avg)
    
    print(f"\n{Colors.BOLD}Overall Statistics:{Colors.ENDC}")
    print_metric("Total Requests", str(total_requests))
    print_metric("Total Successful", str(total_success))
    print_metric("Overall Success Rate", f"{(total_success/total_requests*100):.1f}%" if total_requests > 0 else "N/A")
    print_metric("Average Response Time", f"{statistics.mean(all_response_times):.2f}ms" if all_response_times else "N/A")
    
    # Pass/Fail determination
    success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0
    avg_response = statistics.mean(all_response_times) if all_response_times else float('inf')
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    if success_rate >= 95 and avg_response < 500:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 STRESS TEST PASSED! System is robust! 🎉{Colors.ENDC}")
    elif success_rate >= 80:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  STRESS TEST PASSED with warnings{Colors.ENDC}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ STRESS TEST FAILED - System needs optimization{Colors.ENDC}")
    
    return all_results


if __name__ == "__main__":
    print("\n" + "🔥"*35)
    print("    ULTIMATE STRESS TEST FOR PATH DEVIATION DETECTION")
    print("    ⚠️  WARNING: This will push the system to its limits!")
    print("🔥"*35 + "\n")
    
    try:
        results = asyncio.run(run_all_stress_tests())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
