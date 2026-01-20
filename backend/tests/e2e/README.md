# 🧪 Path Deviation Detection - E2E Test Suite

## Overview

This test suite validates the complete Path Deviation Detection System using **real-world coordinates from Pune, India**. It simulates various driving scenarios to ensure the deviation detection algorithms work correctly with unseen data.

## 📁 Test Files

| File | Description |
|------|-------------|
| `test_e2e_ultimate.py` | **Main E2E test script** - Comprehensive testing with 7 scenarios |
| `test_deviation.py` | Unit tests for deviation detection algorithms (11 tests) |
| `test_geometry_simple.py` | Unit tests for geometry utilities |
| `test_phase1.py` | Phase 1 API tests |
| `test_phase2_e2e.py` | Phase 2 integration tests |

## 🚀 Quick Start

### Prerequisites

1. **Server must be running** on `http://localhost:8000`:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Required packages**:
   ```bash
   pip install httpx asyncio
   ```

### Run the Tests

```bash
# Run the ultimate E2E test suite
cd backend
python test_e2e_ultimate.py

# Run unit tests for deviation detection
python test_deviation.py
```

## 🗺️ Test Scenarios

### 1. Normal On-Route Driving ✅
- **Route**: FC Road → Koregaon Park (~4km)
- **Expected**: ON_ROUTE, ON_TIME, TOWARD_DEST
- **Purpose**: Verify system correctly identifies normal driving behavior

### 2. Long Distance Route ✅
- **Route**: Shivajinagar → Hinjewadi IT Park (~15km)
- **Expected**: ON_TIME, TOWARD_DEST
- **Purpose**: Test system with longer routes through multiple areas

### 3. Route Deviation (Wrong Turn) ⚠️
- **Route**: FC Road → Koregaon Park (with wrong turn)
- **Expected**: OFF_ROUTE or NEAR_ROUTE detection
- **Purpose**: Verify system detects when user takes wrong turn

### 4. Vehicle Stopped 🛑
- **Route**: FC Road area with 2-minute stop
- **Expected**: STOPPED status detection
- **Purpose**: Test temporal deviation for traffic/signal stops

### 5. Opposite Direction Travel 🔄
- **Route**: FC Road going WEST instead of EAST
- **Expected**: AWAY, OFF_ROUTE
- **Purpose**: Verify directional deviation detection

### 6. Unseen Route (Camp → Viman Nagar) 🆕
- **Route**: Brand new route not in any training data
- **Expected**: TOWARD_DEST
- **Purpose**: Test generalization to completely new routes

### 7. Cross-City Route (Kothrud → Magarpatta) 🌆
- **Route**: ~12km cross-city journey
- **Expected**: TOWARD_DEST, ON_TIME
- **Purpose**: Test long cross-city navigation

## 📍 Pune Coordinates Used

```python
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
}
```

## 📊 Expected Output

```
======================================================================
              PATH DEVIATION DETECTION - E2E TEST SUITE               
======================================================================

ℹ Server: http://localhost:8000
ℹ Date: 2026-01-20 02:10:51
✓ Server is healthy: {'status': 'healthy', 'version': '1.0.0'}

--- Test: Normal On-Route Driving ---
  ...
  Point 48/48: NORMAL [ON_ROUTE, ON_TIME, AWAY] Progress: 99.9%
✓ Journey completed successfully

======================================================================
                         TEST RESULTS SUMMARY
======================================================================

  [PASS] Normal On-Route Driving
  [PASS] Long Distance Route (Shivajinagar to Hinjewadi)
  [PASS] Route Deviation (Wrong Turn)
  [PASS] Vehicle Stopped (Traffic/Signal)
  [PASS] Opposite Direction Travel
  [PASS] Unseen Route (Camp to Viman Nagar)
  [PASS] Cross-City Route (Kothrud to Magarpatta)

======================================================================
Total: 7/7 tests passed

🎉 ALL TESTS PASSED! 🎉
```

## 🔍 Deviation Detection Types

### Spatial Deviation
| Status | Description | Threshold |
|--------|-------------|-----------|
| `ON_ROUTE` | Within acceptable distance | < 50m |
| `NEAR_ROUTE` | Slightly off but recoverable | 50-100m |
| `OFF_ROUTE` | Significantly deviated | > 100m |

### Temporal Deviation
| Status | Description |
|--------|-------------|
| `ON_TIME` | Within expected time window |
| `SLIGHTLY_DELAYED` | Minor delay detected |
| `DELAYED` | Moderate delay |
| `SEVERELY_DELAYED` | Major delay |
| `STOPPED` | Vehicle stationary |

### Directional Deviation
| Status | Description | Bearing Diff |
|--------|-------------|--------------|
| `TOWARD_DEST` | Moving towards destination | < 45° |
| `PERPENDICULAR` | Moving sideways | 45-135° |
| `AWAY` | Moving away from destination | > 135° |

### Severity Levels
| Severity | Conditions |
|----------|------------|
| `normal` | All green - ON_ROUTE, ON_TIME, TOWARD_DEST |
| `minor` | NEAR_ROUTE or slight delays |
| `moderate` | OFF_ROUTE but heading towards destination |
| `concerning` | STOPPED for extended period |
| `major` | OFF_ROUTE + AWAY from destination |

## 🛠️ Customizing Tests

### Add New Test Scenario

```python
# Define waypoints
NEW_ROUTE_POINTS = [
    (lat1, lng1),  # Start
    (lat2, lng2),  # Waypoint
    (lat3, lng3),  # End
]

# Generate GPS trace
gps_trace = generate_gps_trace(
    NEW_ROUTE_POINTS,
    points_per_segment=4,
    base_speed=40.0,
    speed_variance=5.0
)

# Run test
result = await run_test_scenario(
    name="My New Test",
    description="Test description",
    origin=(lat1, lng1),
    destination=(lat3, lng3),
    gps_trace=gps_trace,
    expected_deviations=["ON_ROUTE", "TOWARD_DEST"],
    client=client
)
```

### Modify GPS Trace Parameters

```python
# For slow city driving
gps_trace = generate_gps_trace(
    waypoints,
    points_per_segment=5,    # More points
    base_speed=25.0,         # Slower speed (km/h)
    speed_variance=5.0       # Less variance
)

# For highway driving
gps_trace = generate_gps_trace(
    waypoints,
    points_per_segment=3,    # Fewer points (faster)
    base_speed=80.0,         # Highway speed
    speed_variance=15.0      # More variance
)
```

## 📈 API Endpoints Tested

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/journey/start` | POST | Start new journey |
| `/api/journey/{id}/gps` | POST | Submit GPS point |
| `/api/journey/{id}` | GET | Get journey status |
| `/api/journey/{id}/complete` | PUT | Complete journey |
| `/health` | GET | Server health check |

## 🐛 Troubleshooting

### Server not reachable
```
✗ Server not reachable: [Errno 111] Connection refused
```
**Solution**: Start the server with `uvicorn app.main:app --reload`

### No routes found
```
HTTPStatusError: 400 Bad Request - No routes found
```
**Solution**: Check Mapbox API key in `.env` file

### Timeout errors
```
ReadTimeout: timed out
```
**Solution**: Increase timeout in the test script or check server performance

## 📝 Test Results Log

Test results are also logged to `backend/logs/app.log` with detailed information about:
- Route probabilities
- Spatial deviation distances
- Temporal deviation times
- Directional bearing calculations
- Overall severity determination

---

**Author**: Path Deviation Detection System  
**Last Updated**: January 20, 2026  
**Version**: 1.0.0
