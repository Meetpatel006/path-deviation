# GPS Path Deviation Detection System - Complete Project Specification

## Project Overview

A real-time GPS tracking system that detects when users deviate from planned routes using rule-based algorithms (NO machine learning). The system uses map services (Mapbox/Google Maps) for routing and displays deviations on an interactive web map.

### Core Functionality
- Accept origin and destination from users
- Fetch multiple route alternatives from map services
- Track user's GPS location in real-time
- Detect spatial, temporal, and directional deviations
- Display routes and deviation status on interactive map
- Provide real-time alerts when deviation occurs

### Technology Stack
**Backend:** Python + FastAPI + SQLite + httpx + Shapely + Geopy
**Frontend:** JavaScript + Mapbox GL JS + WebSocket
**Map Services:** Mapbox Directions API + Map Matching API (or Google Maps Directions API)

---

## Important Context & Constraints

### Route Data Format
The system works with route data matching **Google Directions API JSON structure**:

```json
{
  "routes": [
    {
      "bounds": {
        "northeast": {"lat": 19.1234, "lng": 73.5678},
        "southwest": {"lat": 18.9876, "lng": 73.1234}
      },
      "legs": [
        {
          "distance": {"text": "150 km", "value": 150000},
          "duration": {"text": "3 hours", "value": 10800},
          "start_location": {"lat": 18.9876, "lng": 73.1234},
          "end_location": {"lat": 19.1234, "lng": 73.5678},
          "steps": [
            {
              "distance": {"value": 1200},
              "duration": {"value": 120},
              "start_location": {"lat": 18.9876, "lng": 73.1234},
              "end_location": {"lat": 18.9950, "lng": 73.1300},
              "polyline": {"points": "encoded_polyline_string"}
            }
          ]
        }
      ],
      "overview_polyline": {"points": "encoded_polyline_string"},
      "summary": "NH 48",
      "warnings": [],
      "waypoint_order": []
    }
  ],
  "status": "OK"
}
```

### Key Design Decisions

1. **NO Machine Learning** - Use rule-based algorithms only
2. **Map Matching Batching Strategy** (based on research):
   - GPS collection: Every 2-3 seconds
   - Batch size: 15-20 GPS points
   - API call frequency: Every 30-40 seconds
   - Include last 5 points from previous batch for continuity

3. **Dynamic Buffer Zones** (speed-based):
   - Walking (< 6 km/h): 20 meters
   - City driving (< 60 km/h): 50 meters
   - Highway (> 60 km/h): 75 meters

4. **Deviation Severity Levels** (combination of spatial + temporal + directional):
   - **Level 0 - Normal**: On route, on time
   - **Level 1 - Minor**: Near route (within 2x buffer), still heading to destination
   - **Level 2 - Moderate**: Off route but heading toward destination
   - **Level 3 - Concerning**: Stopped too long (>10 min)
   - **Level 4 - Major**: Off route and wrong direction

5. **Route Probability Tracking**: Use weighted scoring (distance: 50%, bearing: 30%, history: 20%)

6. **Travel Modes**: Support walking and driving (auto-detect or user-selected)

---

## Reference Documentation

### Essential Reading
1. **Mapbox Directions API**: https://docs.mapbox.com/api/navigation/directions/
2. **Mapbox Map Matching API**: https://docs.mapbox.com/api/navigation/map-matching/
3. **Google Directions API**: https://developers.google.com/maps/documentation/directions/overview
4. **Haversine Distance**: https://en.wikipedia.org/wiki/Haversine_formula
5. **Point-to-Line Distance**: Perpendicular distance calculation for spatial deviation
6. **Polyline Encoding/Decoding**: https://developers.google.com/maps/documentation/utilities/polylinealgorithm

### Python Libraries Documentation
- **FastAPI**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/
- **Shapely**: https://shapely.readthedocs.io/ (geometry operations)
- **Geopy**: https://geopy.readthedocs.io/ (distance, bearing calculations)
- **httpx**: https://www.python-httpx.org/ (async HTTP)
- **SQLite**: https://docs.python.org/3/library/sqlite3.html

### Frontend Libraries
- **Mapbox GL JS**: https://docs.mapbox.com/mapbox-gl-js/
- **WebSocket Client**: Native browser WebSocket API

---

## Database Schema (SQLite)

```sql
-- Journeys table
CREATE TABLE journeys (
    id TEXT PRIMARY KEY,
    origin_lat REAL NOT NULL,
    origin_lng REAL NOT NULL,
    destination_lat REAL NOT NULL,
    destination_lng REAL NOT NULL,
    travel_mode TEXT NOT NULL, -- 'driving' or 'walking'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL, -- 'active', 'completed', 'abandoned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Routes table (stores multiple alternative routes)
CREATE TABLE routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id TEXT NOT NULL,
    route_index INTEGER NOT NULL, -- 0, 1, 2 (for route alternatives)
    geometry TEXT NOT NULL, -- JSON array of [lng, lat] coordinates
    distance_meters REAL NOT NULL,
    duration_seconds REAL NOT NULL,
    summary TEXT,
    FOREIGN KEY (journey_id) REFERENCES journeys(id)
);

-- GPS points table
CREATE TABLE gps_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    speed REAL, -- km/h
    bearing REAL, -- degrees
    accuracy REAL, -- meters
    FOREIGN KEY (journey_id) REFERENCES journeys(id)
);

-- Deviation events table
CREATE TABLE deviation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    severity TEXT NOT NULL, -- 'minor', 'moderate', 'major'
    spatial_status TEXT, -- 'ON_ROUTE', 'NEAR_ROUTE', 'OFF_ROUTE'
    temporal_status TEXT, -- 'ON_TIME', 'DELAYED', 'STOPPED'
    directional_status TEXT, -- 'TOWARD_DEST', 'PERPENDICULAR', 'AWAY'
    distance_from_route REAL, -- meters
    time_deviation REAL, -- seconds
    route_probabilities TEXT, -- JSON of probabilities
    FOREIGN KEY (journey_id) REFERENCES journeys(id)
);
```

---

## PHASE 1: Backend Core Setup & Route Management

### Objective
Set up FastAPI project with data models, database, and Mapbox/Google Directions API integration. Implement route fetching and storage.

### Prerequisites
- Python 3.9+
- Mapbox API key (or Google Maps API key)
- Basic understanding of async Python and FastAPI

### Detailed Requirements

#### 1.1 Project Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Configuration (API keys, etc.)
│   ├── database.py          # Database connection & models
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py       # Pydantic models for request/response
│   │   └── db_models.py     # SQLite table definitions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── route_service.py      # Mapbox/Google API integration
│   │   └── journey_service.py    # Journey management
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   └── utils/
│       ├── __init__.py
│       └── geometry.py      # Geometry helper functions
├── requirements.txt
└── .env                     # API keys (not committed)
```

#### 1.2 Data Models (Pydantic Schemas)

**File: app/models/schemas.py**

Define these Pydantic models:

```python
class LocationPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)

class GPSPoint(BaseModel):
    lat: float
    lng: float
    timestamp: datetime
    speed: Optional[float] = None  # km/h
    bearing: Optional[float] = None  # degrees
    accuracy: Optional[float] = None  # meters

class RouteGeometry(BaseModel):
    coordinates: List[Tuple[float, float]]  # [(lng, lat), ...]

class Route(BaseModel):
    route_id: str
    route_index: int  # 0, 1, 2
    geometry: List[Tuple[float, float]]  # [(lng, lat), ...]
    distance_meters: float
    duration_seconds: float
    summary: Optional[str] = None

class JourneyStartRequest(BaseModel):
    origin: LocationPoint
    destination: LocationPoint
    travel_mode: str = Field(..., regex="^(driving|walking)$")

class JourneyStartResponse(BaseModel):
    journey_id: str
    routes: List[Route]
    start_time: datetime

class DeviationStatus(BaseModel):
    spatial: str  # ON_ROUTE, NEAR_ROUTE, OFF_ROUTE
    temporal: str  # ON_TIME, DELAYED, STOPPED
    directional: str  # TOWARD_DEST, PERPENDICULAR, AWAY
    severity: str  # normal, minor, moderate, major

class JourneyState(BaseModel):
    journey_id: str
    current_state: str
    route_probabilities: Dict[str, float]
    progress_percentage: float
    time_deviation: float  # seconds
    last_gps: Optional[GPSPoint]
    deviation_status: DeviationStatus
```

#### 1.3 Route Service Implementation

**File: app/services/route_service.py**

Implement these functions:

```python
class RouteService:
    async def fetch_routes_from_mapbox(
        origin: LocationPoint,
        destination: LocationPoint,
        travel_mode: str
    ) -> List[Route]:
        """
        Call Mapbox Directions API with alternatives=true
        Parse response and return up to 3 routes
        Handle errors gracefully
        """
        pass

    def parse_mapbox_route(route_data: dict, index: int) -> Route:
        """
        Convert Mapbox route JSON to Route model
        Decode polyline to coordinates
        Extract duration, distance, summary
        """
        pass

    # OR if using Google Maps:
    async def fetch_routes_from_google(
        origin: LocationPoint,
        destination: LocationPoint,
        travel_mode: str
    ) -> List[Route]:
        """
        Call Google Directions API with alternatives=true
        Parse response structure (routes[].legs[].steps[])
        Return Route objects
        """
        pass
```

**Key Implementation Details:**
- Use `httpx.AsyncClient()` for async HTTP requests
- Request `alternatives=true` to get up to 3 routes
- For Mapbox: Use `geometries=geojson` or decode polyline6
- For Google: Decode polyline5 from `overview_polyline.points`
- Add proper error handling for API failures
- Log API requests/responses for debugging

#### 1.4 Database Setup

**File: app/database.py**

```python
import sqlite3
from contextlib import contextmanager

DATABASE_PATH = "path_deviation.db"

def init_db():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Execute CREATE TABLE statements from schema above
    # ...
    
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
    finally:
        conn.close()
```

#### 1.5 API Endpoints

**File: app/api/routes.py**

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/journey", tags=["journey"])

@router.post("/start", response_model=JourneyStartResponse)
async def start_journey(request: JourneyStartRequest):
    """
    1. Generate unique journey_id (UUID)
    2. Fetch routes from Mapbox/Google
    3. Store journey in database
    4. Store routes in database
    5. Return journey_id and routes
    """
    pass

@router.get("/{journey_id}", response_model=JourneyState)
async def get_journey_status(journey_id: str):
    """
    Retrieve current journey state from database
    Calculate current metrics
    Return journey state
    """
    pass
```

### Testing Checklist for Phase 1

- [ ] POST `/api/journey/start` returns 3 route alternatives
- [ ] Routes are stored in database correctly
- [ ] Route geometry can be decoded and validated
- [ ] Error handling works for invalid coordinates
- [ ] Error handling works for API failures
- [ ] Database transactions work correctly
- [ ] Journey can be retrieved by ID

### Success Criteria
- Backend server runs without errors
- Can start a journey and receive 3 routes
- Routes are persisted in SQLite
- All Pydantic validation works
- API documentation is accessible at `/docs`

---

## PHASE 2: Deviation Detection Logic

### Objective
Implement core algorithms for detecting spatial, temporal, and directional deviations. This is the "brain" of the system.

### Prerequisites
- Phase 1 completed
- Understanding of haversine distance formula
- Understanding of point-to-line distance calculations

### Detailed Requirements

#### 2.1 Geometry Utilities

**File: app/utils/geometry.py**

Implement these critical functions:

```python
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from typing import List, Tuple

def haversine_distance(
    point1: Tuple[float, float],  # (lat, lng)
    point2: Tuple[float, float]
) -> float:
    """
    Calculate great-circle distance between two points in meters
    Uses Haversine formula
    Returns distance in meters
    """
    pass

def calculate_bearing(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    """
    Calculate initial bearing from point1 to point2
    Returns bearing in degrees (0-360)
    """
    pass

def find_nearest_point_on_line(
    point: Tuple[float, float],
    line: List[Tuple[float, float]]
) -> Tuple[Tuple[float, float], float, int]:
    """
    Find nearest point on a polyline to given point
    
    Args:
        point: (lat, lng)
        line: List of (lat, lng) forming polyline
    
    Returns:
        (nearest_point, distance_meters, segment_index)
    """
    # For each segment in polyline:
    #   1. Calculate perpendicular distance from point to segment
    #   2. Find closest point on segment
    # Return minimum distance point
    pass

def point_to_segment_distance(
    point: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float]
) -> Tuple[Tuple[float, float], float]:
    """
    Calculate perpendicular distance from point to line segment
    Returns (closest_point_on_segment, distance_meters)
    """
    pass

def calculate_progress_along_route(
    start_point: Tuple[float, float],
    current_point: Tuple[float, float],
    route_geometry: List[Tuple[float, float]]
) -> float:
    """
    Calculate how far along the route the user has traveled
    Returns distance in meters from start
    """
    pass
```

**Implementation Notes:**
- Use Shapely library for complex geometry operations if needed
- Test with known coordinates (e.g., distance Mumbai to Pune should be ~150km)
- Handle edge cases (empty routes, single-point routes)

#### 2.2 Deviation Detector Service

**File: app/services/deviation_detector.py**

```python
class DeviationDetector:
    
    def __init__(self, routes: List[Route]):
        self.routes = routes
    
    def check_spatial_deviation(
        self,
        gps_point: GPSPoint,
        speed: float  # km/h
    ) -> Tuple[str, float, str]:
        """
        Determine if user is spatially off-route
        
        Returns:
            (status, min_distance, closest_route_id)
            status: 'ON_ROUTE', 'NEAR_ROUTE', 'OFF_ROUTE'
        """
        # 1. Determine dynamic buffer based on speed
        if speed < 6:  # walking
            buffer = 20
        elif speed < 60:  # city
            buffer = 50
        else:  # highway
            buffer = 75
        
        # 2. Check distance to each route
        min_distance = float('inf')
        closest_route = None
        
        for route in self.routes:
            nearest_point, distance, _ = find_nearest_point_on_line(
                (gps_point.lat, gps_point.lng),
                route.geometry
            )
            if distance < min_distance:
                min_distance = distance
                closest_route = route.route_id
        
        # 3. Classify
        if min_distance <= buffer:
            status = "ON_ROUTE"
        elif min_distance <= 2 * buffer:
            status = "NEAR_ROUTE"
        else:
            status = "OFF_ROUTE"
        
        return status, min_distance, closest_route
    
    def check_temporal_deviation(
        self,
        journey_start_time: datetime,
        current_time: datetime,
        progress_meters: float,
        expected_route: Route,
        current_speed: float
    ) -> Tuple[str, float]:
        """
        Determine if user is temporally delayed
        
        Returns:
            (status, time_deviation_seconds)
            status: 'ON_TIME', 'DELAYED', 'SEVERELY_DELAYED', 'STOPPED'
        """
        # 1. Calculate expected time at current progress
        progress_pct = (progress_meters / expected_route.distance_meters) * 100
        expected_time = expected_route.duration_seconds * (progress_pct / 100)
        
        # 2. Calculate actual time elapsed
        actual_time = (current_time - journey_start_time).total_seconds()
        
        # 3. Calculate deviation
        time_deviation = actual_time - expected_time
        
        # 4. Check if stationary
        if current_speed < 1:  # less than 1 km/h
            # Check how long they've been stopped
            # (requires tracking consecutive low-speed points)
            # For now, return STOPPED if speed is very low
            return "STOPPED", time_deviation
        
        # 5. Classify
        if time_deviation < 300:  # 5 minutes
            return "ON_TIME", time_deviation
        elif time_deviation < 900:  # 15 minutes
            return "DELAYED", time_deviation
        else:
            return "SEVERELY_DELAYED", time_deviation
    
    def check_directional_deviation(
        self,
        current_point: GPSPoint,
        destination: Tuple[float, float],
        expected_route: Route,
        recent_points: List[GPSPoint]
    ) -> str:
        """
        Determine if user is heading in correct direction
        
        Returns:
            status: 'TOWARD_DEST', 'PERPENDICULAR', 'AWAY'
        """
        # 1. Calculate bearing to destination
        expected_bearing = calculate_bearing(
            (current_point.lat, current_point.lng),
            destination
        )
        
        # 2. Calculate actual bearing from recent movement
        if len(recent_points) >= 2:
            actual_bearing = calculate_bearing(
                (recent_points[-2].lat, recent_points[-2].lng),
                (recent_points[-1].lat, recent_points[-1].lng)
            )
        else:
            # Not enough data, assume aligned
            return "TOWARD_DEST"
        
        # 3. Calculate bearing difference
        bearing_diff = abs(expected_bearing - actual_bearing)
        if bearing_diff > 180:
            bearing_diff = 360 - bearing_diff
        
        # 4. Classify
        if bearing_diff < 45:
            return "TOWARD_DEST"
        elif bearing_diff < 135:
            return "PERPENDICULAR"
        else:
            return "AWAY"
    
    def determine_severity(
        self,
        spatial: str,
        temporal: str,
        directional: str
    ) -> str:
        """
        Combine all deviation types into overall severity
        
        Returns:
            severity: 'normal', 'minor', 'moderate', 'major'
        """
        # Level 0 - Normal
        if spatial == "ON_ROUTE" and temporal in ["ON_TIME", "DELAYED"]:
            return "normal"
        
        # Level 1 - Minor
        if spatial == "NEAR_ROUTE" and directional == "TOWARD_DEST":
            return "minor"
        
        # Level 2 - Moderate
        if spatial == "OFF_ROUTE" and directional == "TOWARD_DEST":
            return "moderate"
        
        # Level 3 - Concerning
        if temporal == "STOPPED":
            return "concerning"
        
        # Level 4 - Major
        if spatial == "OFF_ROUTE" and directional == "AWAY":
            return "major"
        
        # Default
        return "minor"
```

#### 2.3 Route Probability Tracker

**File: app/services/route_tracker.py**

```python
import numpy as np

class RouteTracker:
    
    def __init__(self, routes: List[Route]):
        self.routes = routes
        self.probabilities = {
            route.route_id: 1.0 / len(routes) 
            for route in routes
        }
    
    def update_probabilities(
        self,
        gps_point: GPSPoint,
        previous_probs: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Update route probabilities based on GPS point
        Uses weighted scoring: distance (50%) + bearing (30%) + history (20%)
        """
        scores = []
        
        for route in self.routes:
            # Distance score
            nearest_point, distance, _ = find_nearest_point_on_line(
                (gps_point.lat, gps_point.lng),
                route.geometry
            )
            distance_score = max(0, 1 - (distance / 200))  # 200m threshold
            
            # Bearing score
            if gps_point.bearing is not None:
                route_bearing = self._get_route_bearing_at_point(
                    route, nearest_point
                )
                bearing_diff = abs(gps_point.bearing - route_bearing)
                if bearing_diff > 180:
                    bearing_diff = 360 - bearing_diff
                bearing_score = max(0, 1 - (bearing_diff / 90))
            else:
                bearing_score = 0.5  # neutral if no bearing data
            
            # History score
            history_score = previous_probs.get(route.route_id, 0.33)
            
            # Weighted combination
            total_score = (
                0.5 * distance_score +
                0.3 * bearing_score +
                0.2 * history_score
            )
            scores.append(total_score)
        
        # Softmax normalization
        probabilities = self._softmax(scores)
        
        return {
            route.route_id: prob
            for route, prob in zip(self.routes, probabilities)
        }
    
    def get_most_likely_route(self) -> Route:
        """Return route with highest probability"""
        max_prob_route_id = max(
            self.probabilities,
            key=self.probabilities.get
        )
        return next(r for r in self.routes if r.route_id == max_prob_route_id)
    
    def is_route_locked(self) -> bool:
        """Check if probability is high enough to lock to a route"""
        return max(self.probabilities.values()) > 0.7
    
    @staticmethod
    def _softmax(scores: List[float]) -> List[float]:
        """Softmax normalization"""
        exp_scores = np.exp(np.array(scores) - np.max(scores))
        return exp_scores / exp_scores.sum()
    
    def _get_route_bearing_at_point(
        self,
        route: Route,
        point: Tuple[float, float]
    ) -> float:
        """Calculate route bearing at nearest point"""
        # Find segment containing nearest point
        # Calculate bearing of that segment
        # Implementation details...
        pass
```

### Testing Checklist for Phase 2

- [ ] Haversine distance matches known values (Mumbai-Pune ~150km)
- [ ] Point-to-line distance works correctly
- [ ] Spatial deviation correctly classifies ON_ROUTE vs OFF_ROUTE
- [ ] Dynamic buffer adjusts based on speed
- [ ] Temporal deviation calculates time difference correctly
- [ ] Directional deviation detects wrong-way travel
- [ ] Severity combination logic works for all cases
- [ ] Route probabilities sum to 1.0
- [ ] Route locking happens at 70% threshold

### Success Criteria
- All geometry functions return accurate results
- Deviation detection works with test GPS traces
- Route probability tracking identifies correct route
- Edge cases handled (no bearing data, single route, etc.)

---

## PHASE 3: Map Matching Integration & GPS Buffering

### Objective
Integrate Mapbox Map Matching API, implement GPS buffering strategy, and create the real-time processing pipeline.

### Prerequisites
- Phase 1 and 2 completed
- Understanding of batching strategy (15-20 points every 30-40 seconds)
- Mapbox Map Matching API documentation reviewed

### Detailed Requirements

#### 3.1 GPS Buffer Service

**File: app/services/gps_buffer.py**

```python
from collections import deque
from datetime import datetime, timedelta

class GPSBuffer:
    
    def __init__(
        self,
        batch_size: int = 18,  # 15-20 points
        max_time_seconds: int = 40,  # 30-40 seconds
        overlap_points: int = 5  # Points to overlap with previous batch
    ):
        self.batch_size = batch_size
        self.max_time_seconds = max_time_seconds
        self.overlap_points = overlap_points
        
        self.buffer: deque[GPSPoint] = deque(maxlen=batch_size + overlap_points)
        self.last_batch_time: Optional[datetime] = None
        self.previous_batch: List[GPSPoint] = []
    
    def add_point(self, gps_point: GPSPoint) -> bool:
        """
        Add GPS point to buffer
        Returns True if batch is ready for processing
        """
        self.buffer.append(gps_point)
        
        # Check if batch is ready
        return self.should_process_batch()
    
    def should_process_batch(self) -> bool:
        """
        Determine if buffer should be processed now
        Based on: point count OR time elapsed
        """
        # Check point count
        if len(self.buffer) >= self.batch_size:
            return True
        
        # Check time elapsed
        if self.last_batch_time is not None:
            oldest_point = self.buffer[0]
            time_diff = (datetime.now() - self.last_batch_time).total_seconds()
            if time_diff >= self.max_time_seconds:
                return True
        
        return False
    
    def get_batch_for_matching(self) -> List[GPSPoint]:
        """
        Get current batch including overlap from previous batch
        """
        # Combine last N points from previous batch with current buffer
        batch = self.previous_batch[-self.overlap_points:] + list(self.buffer)
        
        # Update for next iteration
        self.previous_batch = list(self.buffer)
        self.last_batch_time = datetime.now()
        
        return batch
    
    def clear_buffer(self):
        """Clear buffer after processing (keeps overlap points)"""
        # Keep last overlap_points in buffer
        overlap = list(self.buffer)[-self.overlap_points:]
        self.buffer.clear()
        for point in overlap:
            self.buffer.append(point)
```

#### 3.2 Map Matching Service

**File: app/services/map_matching.py**

```python
import httpx
from typing import List, Tuple, Optional

class MapMatchingService:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mapbox.com/matching/v5/mapbox"
    
    async def match_gps_trace(
        self,
        gps_points: List[GPSPoint],
        travel_mode: str = "driving"
    ) -> Tuple[List[Tuple[float, float]], float]:
        """
        Call Mapbox Map Matching API
        
        Args:
            gps_points: List of GPS coordinates
            travel_mode: 'driving' or 'walking'
        
        Returns:
            (matched_coordinates, confidence_score)
        """
        # 1. Format coordinates for Mapbox
        # Format: "lng,lat;lng,lat;lng,lat"
        coordinates_str = ";".join([
            f"{point.lng},{point.lat}" 
            for point in gps_points
        ])
        
        # 2. Build URL
        profile = "driving" if travel_mode == "driving" else "walking"
        url = f"{self.base_url}/{profile}/{coordinates_str}"
        
        # 3. Set parameters
        params = {
            "access_token": self.api_key,
            "geometries": "geojson",
            "tidy": "true",  # Remove GPS noise
            "annotations": "distance,duration",
            "overview": "full"
        }
        
        # 4. Make async request
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
        
        # 5. Parse response
        if data.get("code") != "Ok":
            raise ValueError(f"Map matching failed: {data.get('message')}")
        
        matchings = data.get("matchings", [])
        if not matchings:
            raise ValueError("No matchings returned")
        
        # Get best match (first one)
        best_match = matchings[0]
        
        # Extract geometry
        geometry = best_match["geometry"]["coordinates"]  # [[lng,lat], ...]
        
        # Extract confidence (0-1)
        confidence = best_match.get("confidence", 0.0)
        
        # Convert to (lat, lng) tuples
        matched_coords = [(lat, lng) for lng, lat in geometry]
        
        return matched_coords, confidence
    
    async def match_gps_trace_google(
        self,
        gps_points: List[GPSPoint],
        travel_mode: str = "driving"
    ) -> Tuple[List[Tuple[float, float]], float]:
        """
        Alternative: Use Google Roads API for map matching
        (Snap to Roads API)
        """
        # Implementation for Google Maps alternative
        pass
```

#### 3.3 Unified Processing Pipeline

**File: app/services/tracking_service.py**

```python
class TrackingService:
    
    def __init__(self, journey_id: str):
        self.journey_id = journey_id
        
        # Load journey and routes from database
        self.journey = self._load_journey()
        self.routes = self._load_routes()
        
        # Initialize components
        self.gps_buffer = GPSBuffer()
        self.map_matcher = MapMatchingService(api_key=MAPBOX_API_KEY)
        self.deviation_detector = DeviationDetector(self.routes)
        self.route_tracker = RouteTracker(self.routes)
        
        # State
        self.recent_gps_points: deque[GPSPoint] = deque(maxlen=10)
        self.stationary_start: Optional[datetime] = None
    
    async def process_gps_point(
        self,
        gps_point: GPSPoint
    ) -> Optional[Dict]:
        """
        Main processing function called for each GPS point
        
        Returns deviation status if batch was processed, else None
        """
        # 1. Store GPS point in database
        self._store_gps_point(gps_point)
        
        # 2. Add to recent points (for bearing calculation)
        self.recent_gps_points.append(gps_point)
        
        # 3. Add to buffer
        batch_ready = self.gps_buffer.add_point(gps_point)
        
        if not batch_ready:
            # Not ready to process yet
            return None
        
        # 4. Get batch for map matching
        batch = self.gps_buffer.get_batch_for_matching()
        
        # 5. Call Map Matching API
        try:
            matched_coords, confidence = await self.map_matcher.match_gps_trace(
                batch,
                self.journey["travel_mode"]
            )
        except Exception as e:
            # Map matching failed, use raw GPS
            print(f"Map matching error: {e}")
            matched_coords = [(p.lat, p.lng) for p in batch]
            confidence = 0.0
        
        # 6. Use latest matched point for deviation detection
        current_matched = matched_coords[-1]
        
        # 7. Check spatial deviation
        spatial_status, min_distance, closest_route = \
            self.deviation_detector.check_spatial_deviation(
                gps_point,
                gps_point.speed or 0
            )
        
        # 8. Update route probabilities
        new_probs = self.route_tracker.update_probabilities(
            gps_point,
            self.route_tracker.probabilities
        )
        self.route_tracker.probabilities = new_probs
        
        # 9. Get most likely route
        likely_route = self.route_tracker.get_most_likely_route()
        
        # 10. Calculate progress along route
        progress_meters = calculate_progress_along_route(
            (self.journey["origin_lat"], self.journey["origin_lng"]),
            current_matched,
            likely_route.geometry
        )
        
        # 11. Check temporal deviation
        temporal_status, time_deviation = \
            self.deviation_detector.check_temporal_deviation(
                self.journey["start_time"],
                gps_point.timestamp,
                progress_meters,
                likely_route,
                gps_point.speed or 0
            )
        
        # 12. Check directional deviation
        directional_status = self.deviation_detector.check_directional_deviation(
            gps_point,
            (self.journey["destination_lat"], self.journey["destination_lng"]),
            likely_route,
            list(self.recent_gps_points)
        )
        
        # 13. Determine overall severity
        severity = self.deviation_detector.determine_severity(
            spatial_status,
            temporal_status,
            directional_status
        )
        
        # 14. Store deviation event if not normal
        if severity != "normal":
            self._store_deviation_event(
                gps_point.timestamp,
                severity,
                spatial_status,
                temporal_status,
                directional_status,
                min_distance,
                time_deviation,
                new_probs
            )
        
        # 15. Clear buffer
        self.gps_buffer.clear_buffer()
        
        # 16. Return status for real-time update
        return {
            "journey_id": self.journey_id,
            "timestamp": gps_point.timestamp.isoformat(),
            "spatial_status": spatial_status,
            "temporal_status": temporal_status,
            "directional_status": directional_status,
            "severity": severity,
            "route_probabilities": new_probs,
            "progress_percentage": (progress_meters / likely_route.distance_meters) * 100,
            "time_deviation": time_deviation,
            "map_matching_confidence": confidence
        }
```

#### 3.4 API Endpoint for GPS Updates

**File: app/api/routes.py** (add to existing)

```python
@router.post("/{journey_id}/gps")
async def submit_gps_point(
    journey_id: str,
    gps_point: GPSPoint,
    background_tasks: BackgroundTasks
):
    """
    Accept GPS point and process asynchronously
    Returns immediate acknowledgment
    Processing happens in background
    """
    # Get or create tracking service for this journey
    tracker = get_tracker(journey_id)
    
    # Process in background
    result = await tracker.process_gps_point(gps_point)
    
    # If result (batch processed), send via WebSocket
    if result:
        await send_websocket_update(journey_id, result)
    
    return {"status": "received", "journey_id": journey_id}
```

### Testing Checklist for Phase 3

- [ ] GPS buffer correctly batches 15-20 points
- [ ] Buffer triggers on time threshold (40 seconds)
- [ ] Map Matching API returns matched coordinates
- [ ] Confidence score is extracted correctly
- [ ] Overlapping points work correctly
- [ ] Processing pipeline runs without errors
- [ ] Deviation status calculated for each batch
- [ ] Results stored in database
- [ ] API handles concurrent GPS updates

### Success Criteria
- GPS points are batched efficiently
- Map Matching API integration works
- Real-time processing completes in < 2 seconds
- Deviation detection runs on matched coordinates
- All metrics calculated correctly

---

## PHASE 4: WebSocket & Real-Time Communication

### Objective
Implement WebSocket server for real-time updates to frontend, handle multiple concurrent journeys, and ensure efficient message broadcasting.

### Prerequisites
- Phase 1, 2, and 3 completed
- Understanding of WebSocket protocol
- FastAPI WebSocket support

### Detailed Requirements

#### 4.1 WebSocket Manager

**File: app/services/websocket_manager.py**

```python
from fastapi import WebSocket
from typing import Dict, Set
import json

class ConnectionManager:
    
    def __init__(self):
        # journey_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, journey_id: str):
        """Accept WebSocket connection for a journey"""
        await websocket.accept()
        
        if journey_id not in self.active_connections:
            self.active_connections[journey_id] = set()
        
        self.active_connections[journey_id].add(websocket)
        print(f"Client connected to journey {journey_id}")
    
    def disconnect(self, websocket: WebSocket, journey_id: str):
        """Remove WebSocket connection"""
        if journey_id in self.active_connections:
            self.active_connections[journey_id].discard(websocket)
            
            # Clean up empty journey sets
            if not self.active_connections[journey_id]:
                del self.active_connections[journey_id]
        
        print(f"Client disconnected from journey {journey_id}")
    
    async def send_personal_message(
        self,
        message: dict,
        websocket: WebSocket
    ):
        """Send message to specific WebSocket"""
        await websocket.send_text(json.dumps(message))
    
    async def broadcast_to_journey(
        self,
        message: dict,
        journey_id: str
    ):
        """Send message to all connections for a journey"""
        if journey_id not in self.active_connections:
            return
        
        # Send to all connected clients for this journey
        for connection in self.active_connections[journey_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to client: {e}")
                # Connection likely closed, will be cleaned up on disconnect

# Global instance
websocket_manager = ConnectionManager()
```

#### 4.2 WebSocket Endpoint

**File: app/api/websocket.py**

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import websocket_manager

router = APIRouter()

@router.websocket("/ws/{journey_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    journey_id: str
):
    """
    WebSocket endpoint for real-time journey updates
    
    Client connects at: ws://localhost:8000/ws/{journey_id}
    Receives JSON messages with deviation updates
    """
    await websocket_manager.connect(websocket, journey_id)
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            # Receive messages from client (if any)
            data = await websocket.receive_text()
            
            # Echo back (optional, for testing)
            await websocket_manager.send_personal_message(
                {"type": "ack", "message": "Message received"},
                websocket
            )
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, journey_id)
        print(f"WebSocket disconnected for journey {journey_id}")
```

#### 4.3 Integration with Tracking Service

**File: app/services/tracking_service.py** (modify existing)

```python
# Add to TrackingService class

async def process_gps_point(self, gps_point: GPSPoint) -> Optional[Dict]:
    """
    ... (existing code) ...
    """
    
    # After calculating deviation status
    result = {
        "journey_id": self.journey_id,
        "timestamp": gps_point.timestamp.isoformat(),
        "spatial_status": spatial_status,
        "temporal_status": temporal_status,
        "directional_status": directional_status,
        "severity": severity,
        "route_probabilities": new_probs,
        "progress_percentage": (progress_meters / likely_route.distance_meters) * 100,
        "time_deviation": time_deviation,
        "current_position": {
            "lat": gps_point.lat,
            "lng": gps_point.lng
        }
    }
    
    # Send update via WebSocket
    from app.services.websocket_manager import websocket_manager
    await websocket_manager.broadcast_to_journey(
        {
            "type": "deviation_update",
            "data": result
        },
        self.journey_id
    )
    
    return result
```

#### 4.4 Message Types

Define standard message formats:

```python
# Message Types sent from Backend to Frontend

# 1. Deviation Update (most common)
{
    "type": "deviation_update",
    "data": {
        "journey_id": "uuid",
        "timestamp": "ISO-8601",
        "spatial_status": "ON_ROUTE" | "NEAR_ROUTE" | "OFF_ROUTE",
        "temporal_status": "ON_TIME" | "DELAYED" | "SEVERELY_DELAYED" | "STOPPED",
        "directional_status": "TOWARD_DEST" | "PERPENDICULAR" | "AWAY",
        "severity": "normal" | "minor" | "moderate" | "major",
        "route_probabilities": {"route_0": 0.7, "route_1": 0.2, "route_2": 0.1},
        "progress_percentage": 45.5,
        "time_deviation": 180,  # seconds
        "current_position": {"lat": 19.123, "lng": 73.456}
    }
}

# 2. Alert (when deviation severity changes)
{
    "type": "alert",
    "severity": "moderate",
    "message": "You are off the suggested route but heading toward destination"
}

# 3. Journey Status
{
    "type": "status",
    "journey_id": "uuid",
    "state": "ACTIVE" | "COMPLETED" | "PAUSED"
}

# 4. Arrival
{
    "type": "arrival",
    "journey_id": "uuid",
    "arrival_time": "ISO-8601",
    "total_distance": 150000,  # meters
    "total_duration": 10800  # seconds
}
```

### Testing Checklist for Phase 4

- [ ] WebSocket connection establishes successfully
- [ ] Multiple clients can connect to same journey
- [ ] Messages broadcast to all connected clients
- [ ] Disconnection handled gracefully
- [ ] No memory leaks with connection cleanup
- [ ] Messages sent in correct JSON format
- [ ] WebSocket survives brief network interruptions
- [ ] Concurrent journeys don't interfere with each other

### Success Criteria
- WebSocket connections stable for long durations
- Real-time updates received within 1 second of processing
- Multiple browser tabs can monitor same journey
- Clean disconnect when browser closes
- No server crashes from WebSocket errors

---

## PHASE 5: Frontend - Interactive Map & Visualization

### Objective
Build interactive web interface using Mapbox GL JS to display routes, track user position, and visualize deviations in real-time.

### Prerequisites
- Phase 1-4 completed and backend running
- Basic HTML/CSS/JavaScript knowledge
- Mapbox GL JS documentation reviewed

### Detailed Requirements

#### 5.1 Project Structure

```
frontend/
├── index.html
├── css/
│   └── style.css
├── js/
│   ├── main.js
│   ├── map.js
│   ├── websocket.js
│   └── simulator.js
└── assets/
    └── icons/
```

#### 5.2 HTML Structure

**File: index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPS Path Deviation Tracker</title>
    
    <!-- Mapbox GL JS -->
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div id="app">
        <!-- Control Panel -->
        <div id="control-panel">
            <h2>Journey Controls</h2>
            
            <!-- Journey Setup -->
            <div id="journey-setup">
                <input type="text" id="origin-input" placeholder="Origin (lat, lng)">
                <input type="text" id="destination-input" placeholder="Destination (lat, lng)">
                
                <select id="travel-mode">
                    <option value="driving">Driving</option>
                    <option value="walking">Walking</option>
                </select>
                
                <button id="start-journey-btn">Start Journey</button>
            </div>
            
            <!-- Journey Status -->
            <div id="journey-status" style="display: none;">
                <h3>Journey: <span id="journey-id"></span></h3>
                <p>Progress: <span id="progress">0%</span></p>
                <p>Status: <span id="status">On Route</span></p>
                <p>Severity: <span id="severity" class="severity-normal">Normal</span></p>
                
                <h4>Route Probabilities</h4>
                <div id="route-probs">
                    <div class="prob-bar">
                        <label>Route 1</label>
                        <div class="bar"><div id="prob-0" style="width: 33%"></div></div>
                    </div>
                    <div class="prob-bar">
                        <label>Route 2</label>
                        <div class="bar"><div id="prob-1" style="width: 33%"></div></div>
                    </div>
                    <div class="prob-bar">
                        <label>Route 3</label>
                        <div class="bar"><div id="prob-2" style="width: 33%"></div></div>
                    </div>
                </div>
                
                <h4>GPS Simulator</h4>
                <input type="file" id="gps-file" accept=".json">
                <button id="simulate-btn">Start Simulation</button>
                <button id="pause-btn">Pause</button>
                <input type="range" id="speed-slider" min="1" max="10" value="1">
                <label>Speed: <span id="speed-value">1x</span></label>
            </div>
        </div>
        
        <!-- Map Container -->
        <div id="map"></div>
        
        <!-- Alert Box -->
        <div id="alert-box" style="display: none;"></div>
    </div>
    
    <script src="js/websocket.js"></script>
    <script src="js/map.js"></script>
    <script src="js/simulator.js"></script>
    <script src="js/main.js"></script>
</body>
</html>
```

#### 5.3 Map Initialization & Route Display

**File: js/map.js**

```javascript
// Map configuration
mapboxgl.accessToken = 'YOUR_MAPBOX_TOKEN';

class MapManager {
    constructor(containerId) {
        // Initialize map
        this.map = new mapboxgl.Map({
            container: containerId,
            style: 'mapbox://styles/mapbox/streets-v12',
            center: [73.0, 19.0], // Default: Mumbai area
            zoom: 10
        });
        
        this.routes = [];
        this.userMarker = null;
        this.actualPathCoordinates = [];
        
        this.map.on('load', () => {
            this.initializeLayers();
        });
    }
    
    initializeLayers() {
        // Add source for routes
        this.map.addSource('routes', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });
        
        // Add layer for routes (3 different colors)
        this.map.addLayer({
            id: 'routes-layer',
            type: 'line',
            source: 'routes',
            paint: {
                'line-color': [
                    'match',
                    ['get', 'route_index'],
                    0, '#3b82f6',  // Route 1: Blue
                    1, '#10b981',  // Route 2: Green
                    2, '#f59e0b',  // Route 3: Orange
                    '#6b7280'      // Default: Gray
                ],
                'line-width': 4,
                'line-opacity': 0.7
            }
        });
        
        // Add source for buffer zones
        this.map.addSource('buffers', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });
        
        // Add layer for buffers (semi-transparent)
        this.map.addLayer({
            id: 'buffers-layer',
            type: 'fill',
            source: 'buffers',
            paint: {
                'fill-color': '#3b82f6',
                'fill-opacity': 0.1
            }
        });
        
        // Add source for actual path taken
        this.map.addSource('actual-path', {
            type: 'geojson',
            data: {
                type: 'Feature',
                geometry: {
                    type: 'LineString',
                    coordinates: []
                },
                properties: {
                    severity: 'normal'
                }
            }
        });
        
        // Add layer for actual path (color-coded by severity)
        this.map.addLayer({
            id: 'actual-path-layer',
            type: 'line',
            source: 'actual-path',
            paint: {
                'line-color': [
                    'match',
                    ['get', 'severity'],
                    'normal', '#10b981',    // Green
                    'minor', '#fbbf24',     // Yellow
                    'moderate', '#f97316',  // Orange
                    'major', '#ef4444',     // Red
                    '#6b7280'               // Default: Gray
                ],
                'line-width': 6
            }
        });
    }
    
    displayRoutes(routes) {
        // Convert routes to GeoJSON features
        const features = routes.map((route, index) => ({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: route.geometry  // [[lng, lat], ...]
            },
            properties: {
                route_index: index,
                route_id: route.route_id,
                distance: route.distance_meters,
                duration: route.duration_seconds
            }
        }));
        
        // Update source
        this.map.getSource('routes').setData({
            type: 'FeatureCollection',
            features: features
        });
        
        // Fit map to show all routes
        const bounds = new mapboxgl.LngLatBounds();
        routes.forEach(route => {
            route.geometry.forEach(coord => {
                bounds.extend(coord);
            });
        });
        this.map.fitBounds(bounds, { padding: 50 });
        
        this.routes = routes;
    }
    
    updateUserPosition(lat, lng, severity = 'normal') {
        // Create or update user marker
        if (!this.userMarker) {
            const el = document.createElement('div');
            el.className = 'user-marker';
            el.style.backgroundColor = this.getSeverityColor(severity);
            
            this.userMarker = new mapboxgl.Marker(el)
                .setLngLat([lng, lat])
                .addTo(this.map);
        } else {
            this.userMarker.setLngLat([lng, lat]);
            this.userMarker.getElement().style.backgroundColor = 
                this.getSeverityColor(severity);
        }
        
        // Add to actual path
        this.actualPathCoordinates.push([lng, lat]);
        
        // Update actual path line
        this.map.getSource('actual-path').setData({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: this.actualPathCoordinates
            },
            properties: {
                severity: severity
            }
        });
    }
    
    getSeverityColor(severity) {
        const colors = {
            'normal': '#10b981',
            'minor': '#fbbf24',
            'moderate': '#f97316',
            'major': '#ef4444'
        };
        return colors[severity] || '#6b7280';
    }
    
    clearActualPath() {
        this.actualPathCoordinates = [];
        this.map.getSource('actual-path').setData({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: []
            }
        });
    }
}
```

#### 5.4 WebSocket Client

**File: js/websocket.js**

```javascript
class WebSocketClient {
    constructor(journeyId) {
        this.journeyId = journeyId;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.handlers = {};
    }
    
    connect() {
        const wsUrl = `ws://localhost:8000/ws/${this.journeyId}`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.emit('connected');
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            console.log('Received:', message);
            
            // Handle different message types
            if (message.type && this.handlers[message.type]) {
                this.handlers[message.type](message.data);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.emit('error', error);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket closed');
            this.emit('disconnected');
            
            // Attempt reconnect
            setTimeout(() => this.connect(), this.reconnectInterval);
        };
    }
    
    on(eventType, handler) {
        this.handlers[eventType] = handler;
    }
    
    emit(eventType, data) {
        if (this.handlers[eventType]) {
            this.handlers[eventType](data);
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
```

#### 5.5 GPS Simulator

**File: js/simulator.js**

```javascript
class GPSSimulator {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.journeyId = null;
        this.gpsData = [];
        this.currentIndex = 0;
        this.isPlaying = false;
        this.speed = 1;
        this.intervalId = null;
    }
    
    loadGPSData(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    this.gpsData = JSON.parse(e.target.result);
                    this.currentIndex = 0;
                    resolve();
                } catch (error) {
                    reject(error);
                }
            };
            reader.readAsText(file);
        });
    }
    
    generateScenario(scenario = 'perfect') {
        // Generate synthetic GPS traces for testing
        // scenario: 'perfect', 'deviation', 'shortcut', 'stopped'
        
        // Implementation: Create GPS points along/off route
        // For now, placeholder
        this.gpsData = [];
    }
    
    async start(journeyId) {
        this.journeyId = journeyId;
        this.isPlaying = true;
        this.play();
    }
    
    play() {
        if (!this.isPlaying || this.currentIndex >= this.gpsData.length) {
            this.stop();
            return;
        }
        
        // Send current GPS point
        this.sendGPSPoint(this.gpsData[this.currentIndex]);
        
        this.currentIndex++;
        
        // Schedule next point
        const baseInterval = 3000; // 3 seconds
        const interval = baseInterval / this.speed;
        
        this.intervalId = setTimeout(() => this.play(), interval);
    }
    
    pause() {
        this.isPlaying = false;
        if (this.intervalId) {
            clearTimeout(this.intervalId);
        }
    }
    
    stop() {
        this.pause();
        this.currentIndex = 0;
    }
    
    setSpeed(speed) {
        this.speed = speed;
    }
    
    async sendGPSPoint(gpsPoint) {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/journey/${this.journeyId}/gps`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(gpsPoint)
                }
            );
            
            if (!response.ok) {
                console.error('Failed to send GPS point');
            }
        } catch (error) {
            console.error('Error sending GPS point:', error);
        }
    }
}
```

#### 5.6 Main Application Logic

**File: js/main.js**

```javascript
const API_BASE_URL = 'http://localhost:8000';

let mapManager;
let wsClient;
let simulator;
let currentJourneyId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    mapManager = new MapManager('map');
    simulator = new GPSSimulator(API_BASE_URL);
    
    setupEventListeners();
});

function setupEventListeners() {
    // Start journey button
    document.getElementById('start-journey-btn').addEventListener('click', startJourney);
    
    // Simulation controls
    document.getElementById('simulate-btn').addEventListener('click', startSimulation);
    document.getElementById('pause-btn').addEventListener('click', pauseSimulation);
    document.getElementById('speed-slider').addEventListener('input', updateSpeed);
    document.getElementById('gps-file').addEventListener('change', loadGPSFile);
}

async function startJourney() {
    const originInput = document.getElementById('origin-input').value;
    const destinationInput = document.getElementById('destination-input').value;
    const travelMode = document.getElementById('travel-mode').value;
    
    // Parse coordinates
    const [originLat, originLng] = originInput.split(',').map(s => parseFloat(s.trim()));
    const [destLat, destLng] = destinationInput.split(',').map(s => parseFloat(s.trim()));
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/journey/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin: { lat: originLat, lng: originLng },
                destination: { lat: destLat, lng: destLng },
                travel_mode: travelMode
            })
        });
        
        const data = await response.json();
        currentJourneyId = data.journey_id;
        
        // Display routes on map
        mapManager.displayRoutes(data.routes);
        
        // Show journey status panel
        document.getElementById('journey-setup').style.display = 'none';
        document.getElementById('journey-status').style.display = 'block';
        document.getElementById('journey-id').textContent = currentJourneyId;
        
        // Connect WebSocket
        connectWebSocket(currentJourneyId);
        
    } catch (error) {
        console.error('Error starting journey:', error);
        alert('Failed to start journey');
    }
}

function connectWebSocket(journeyId) {
    wsClient = new WebSocketClient(journeyId);
    
    wsClient.on('deviation_update', (data) => {
        updateJourneyStatus(data);
    });
    
    wsClient.on('alert', (data) => {
        showAlert(data.message, data.severity);
    });
    
    wsClient.connect();
}

function updateJourneyStatus(data) {
    // Update UI
    document.getElementById('progress').textContent = 
        `${data.progress_percentage.toFixed(1)}%`;
    
    document.getElementById('status').textContent = 
        `${data.spatial_status} / ${data.temporal_status}`;
    
    const severityElement = document.getElementById('severity');
    severityElement.textContent = data.severity;
    severityElement.className = `severity-${data.severity}`;
    
    // Update route probabilities
    Object.entries(data.route_probabilities).forEach(([routeId, prob]) => {
        const index = routeId.split('_')[1];
        const probBar = document.getElementById(`prob-${index}`);
        if (probBar) {
            probBar.style.width = `${prob * 100}%`;
        }
    });
    
    // Update map
    mapManager.updateUserPosition(
        data.current_position.lat,
        data.current_position.lng,
        data.severity
    );
}

function showAlert(message, severity) {
    const alertBox = document.getElementById('alert-box');
    alertBox.textContent = message;
    alertBox.className = `alert alert-${severity}`;
    alertBox.style.display = 'block';
    
    setTimeout(() => {
        alertBox.style.display = 'none';
    }, 5000);
}

async function loadGPSFile(event) {
    const file = event.target.files[0];
    if (file) {
        await simulator.loadGPSData(file);
        alert('GPS data loaded');
    }
}

function startSimulation() {
    if (currentJourneyId && simulator.gpsData.length > 0) {
        simulator.start(currentJourneyId);
    } else {
        alert('Please start a journey and load GPS data first');
    }
}

function pauseSimulation() {
    simulator.pause();
}

function updateSpeed(event) {
    const speed = parseInt(event.target.value);
    simulator.setSpeed(speed);
    document.getElementById('speed-value').textContent = `${speed}x`;
}
```

#### 5.7 Styling

**File: css/style.css**

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

#app {
    display: flex;
    height: 100vh;
}

#control-panel {
    width: 350px;
    padding: 20px;
    background: #f8f9fa;
    overflow-y: auto;
    box-shadow: 2px 0 5px rgba(0,0,0,0.1);
}

#map {
    flex: 1;
}

.user-marker {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 3px solid white;
    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
}

.severity-normal { color: #10b981; }
.severity-minor { color: #fbbf24; }
.severity-moderate { color: #f97316; }
.severity-major { color: #ef4444; }

.prob-bar {
    margin: 10px 0;
}

.prob-bar .bar {
    width: 100%;
    height: 20px;
    background: #e5e7eb;
    border-radius: 10px;
    overflow: hidden;
}

.prob-bar .bar div {
    height: 100%;
    background: #3b82f6;
    transition: width 0.3s;
}

.alert {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 5px;
    color: white;
    font-weight: bold;
    z-index: 1000;
}

.alert-minor { background: #fbbf24; }
.alert-moderate { background: #f97316; }
.alert-major { background: #ef4444; }

input, select, button {
    width: 100%;
    padding: 10px;
    margin: 5px 0;
    border: 1px solid #d1d5db;
    border-radius: 5px;
}

button {
    background: #3b82f6;
    color: white;
    cursor: pointer;
    border: none;
}

button:hover {
    background: #2563eb;
}
```

### Testing Checklist for Phase 5

- [ ] Map loads correctly with proper center and zoom
- [ ] Routes display in different colors
- [ ] User marker updates position in real-time
- [ ] Actual path line draws correctly
- [ ] Severity colors change appropriately
- [ ] Route probability bars update smoothly
- [ ] WebSocket connection established
- [ ] Real-time updates received and displayed
- [ ] GPS simulator loads and plays data
- [ ] Speed control works correctly
- [ ] Alerts display and auto-hide

### Success Criteria
- Smooth, responsive map interface
- Real-time position updates with < 1 second delay
- Clear visual distinction between routes and deviation states
- User-friendly controls for simulation
- No console errors during operation
- Works in Chrome, Firefox, Safari

---

## GPS Trace Format for Testing

**File: sample_gps_trace.json**

```json
[
  {
    "lat": 19.0760,
    "lng": 72.8777,
    "timestamp": "2025-01-20T10:00:00Z",
    "speed": 0,
    "bearing": null,
    "accuracy": 10
  },
  {
    "lat": 19.0765,
    "lng": 72.8780,
    "timestamp": "2025-01-20T10:00:03Z",
    "speed": 15,
    "bearing": 45,
    "accuracy": 8
  }
  // ... more points
]
```

---

## Testing Long Routes

### Recommended Test Routes

1. **Mumbai to Pune** (~150km, 3-4 hours)
   - Origin: 19.0760, 72.8777 (Mumbai)
   - Destination: 18.5204, 73.8567 (Pune)
   - Multiple highway options
   - Good for testing all scenarios

2. **Delhi to Agra** (~230km, 4-5 hours)
   - Origin: 28.7041, 77.1025 (Delhi)
   - Destination: 27.1767, 78.0081 (Agra)
   - Yamuna Expressway + NH19

### Test Scenarios to Generate

1. **Perfect Route Following**: GPS points exactly on Route 1
2. **Route Switching**: Start Route 1, switch to Route 2 halfway
3. **Minor Deviation**: Points 30-60m off route (GPS drift)
4. **Shortcut**: Leave all routes, cut through to destination
5. **Getting Lost**: Go completely off-route, wrong direction
6. **Traffic Stop**: Stationary for 15 minutes mid-route
7. **Slow Movement**: Speed 50% slower than expected

---

## Deployment Checklist

### Backend Deployment
- [ ] Set environment variables (API keys, database path)
- [ ] Run database migrations
- [ ] Test all API endpoints
- [ ] Configure CORS for frontend domain
- [ ] Set up logging
- [ ] Deploy to server (Heroku, DigitalOcean, etc.)

### Frontend Deployment
- [ ] Update API_BASE_URL to production URL
- [ ] Update WebSocket URL (ws:// -> wss:// for HTTPS)
- [ ] Add Mapbox access token
- [ ] Minify JavaScript
- [ ] Deploy to hosting (Netlify, Vercel, etc.)

### Final Integration Test
- [ ] Start journey from frontend
- [ ] Simulate GPS trace
- [ ] Verify real-time updates
- [ ] Test all deviation scenarios
- [ ] Check database entries
- [ ] Verify WebSocket stability

---

## Common Issues & Solutions

### Issue: Map Matching API failures
**Solution**: Implement retry logic, fall back to raw GPS if API unavailable

### Issue: WebSocket disconnects
**Solution**: Auto-reconnect logic, buffer messages during disconnect

### Issue: High GPS noise in urban areas
**Solution**: Increase buffer size, use higher Map Matching confidence threshold

### Issue: Slow database queries
**Solution**: Add indexes on journey_id, timestamp columns

### Issue: Frontend not receiving updates
**Solution**: Check CORS, WebSocket URL, network tab in browser dev tools

---

## References Summary

- **Mapbox Directions API**: https://docs.mapbox.com/api/navigation/directions/
- **Mapbox Map Matching API**: https://docs.mapbox.com/api/navigation/map-matching/
- **Google Directions API**: https://developers.google.com/maps/documentation/directions/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Mapbox GL JS Guide**: https://docs.mapbox.com/mapbox-gl-js/guides/
- **WebSocket MDN**: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- **Haversine Formula**: https://en.wikipedia.org/wiki/Haversine_formula
- **Shapely Documentation**: https://shapely.readthedocs.io/

---

## Project Completion Criteria

✅ **Backend**
- All 5 phases implemented
- Database schema created
- All services working
- WebSocket server running
- API documented

✅ **Frontend**
- Map displays routes correctly
- Real-time tracking works
- GPS simulator functional
- UI responsive and intuitive

✅ **Integration**
- Backend + Frontend communicate via WebSocket
- Deviation detection accurate
- Long route testing successful
- All test scenarios pass

✅ **Documentation**
- Code commented
- README with setup instructions
- API documentation
- Deployment guide

---

**END OF SPECIFICATION**