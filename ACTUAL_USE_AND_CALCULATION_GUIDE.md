# Actual Use and Calculation Guide

This file explains how the system is used in real operation and the exact calculations used in code.

## 1) Actual Use (How it is used end-to-end)

## Journey tracking flow
1. Client calls `POST /api/journey/start` with origin, destination, travel mode.
2. Backend fetches up to 3 routes from Mapbox Directions.
3. Journey metadata and routes are stored in Redis.
4. Client connects to `WS /ws/journey/{journey_id}` for real-time updates.
5. Client streams GPS points via `POST /api/journey/{journey_id}/gps`.
6. Each GPS point is:
   - saved to Redis
   - broadcast instantly as `gps_update`
   - queued into GPS buffer
7. When buffer triggers, backend runs:
   - map matching (or fallback)
   - route probability update
   - deviation detection
   - event persistence
   - WebSocket broadcasts (`deviation_update`, `batch_processed`)
8. Client ends trip using `PUT /api/journey/{journey_id}/complete`.

## Safety tracking flow
1. Client sends location to `POST /api/safety/location`.
2. Backend loads zone definitions (cached), computes in/out + distance-to-boundary.
3. It emits events: `approaching`, `entering`, `staying`, `leaving`.
4. Latest user locations are available via `GET /api/safety/users/latest`.

## 2) Core Calculations

## 2.1 Distance between GPS points (Haversine)
File: `backend/app/utils/geometry.py`

Inputs: `(lat1, lng1)`, `(lat2, lng2)` in degrees  
Output: meters

Formula (implemented):
- Convert degrees to radians
- `dlat = lat2 - lat1`
- `dlon = lon2 - lon1`
- `a = sin(dlat/2)^2 + cos(lat1)*cos(lat2)*sin(dlon/2)^2`
- `c = 2 * asin(sqrt(a))`
- `distance = 6371000 * c`

## 2.2 Point to route segment distance
File: `backend/app/utils/geometry.py`

Used for: "how far from route am I?"

Method:
1. Convert local lat/lng deltas to approximate meters.
2. Project point onto line segment with clamped `t` in `[0,1]`.
3. Compute Haversine distance to projected point.

## 2.3 Nearest point on polyline route
File: `backend/app/utils/geometry.py`

Method:
1. Iterate over every segment in route geometry.
2. Compute point-to-segment distance.
3. Keep minimum distance and segment index.

Returns: `(nearest_point, min_distance_meters, segment_index)`.

## 2.4 Progress along route
File: `backend/app/utils/geometry.py`

Method:
1. Find nearest point on route for current GPS.
2. Sum segment lengths from route start to nearest segment.
3. Add partial segment distance to nearest point.

Output: traveled meters along route.

## 2.5 Spatial deviation classification
File: `backend/app/services/deviation_detector.py`

Dynamic buffer by speed:
- Walking: speed `< 6` -> buffer `20m`
- City: speed `< 60` -> buffer `50m`
- Highway: speed `>= 60` -> buffer `75m`

Let `d = min distance to any route`.

Status rules:
- `ON_ROUTE` if `d <= buffer`
- `NEAR_ROUTE` if `buffer < d <= 2*buffer`
- `OFF_ROUTE` if `d > 2*buffer`

## 2.6 Temporal deviation classification
File: `backend/app/services/deviation_detector.py`

Inputs:
- journey start time
- current time
- progress meters
- expected route total distance + duration
- current speed
- stopped duration

Calculations:
- `progress_pct = (progress_meters / route.distance_meters) * 100`
- `expected_time = route.duration_seconds * (progress_pct / 100)`
- `actual_time = (current_time - journey_start_time).seconds`
- `time_deviation = actual_time - expected_time`

Status rules:
- `STOPPED` if `stopped_duration > 600s` OR `current_speed < 1`
- else `ON_TIME` if `time_deviation < 300s`
- else `DELAYED` if `< 900s`
- else `SEVERELY_DELAYED`

## 2.7 Directional deviation classification
File: `backend/app/services/deviation_detector.py`

Calculations:
1. `expected_bearing` = bearing(current -> destination)
2. `actual_bearing` = bearing(recent_point[-2] -> recent_point[-1])
3. `bearing_diff` = absolute circular difference in `[0,180]`

Status rules:
- `TOWARD_DEST` if `bearing_diff < 45`
- `PERPENDICULAR` if `45 <= bearing_diff < 135`
- `AWAY` if `bearing_diff >= 135`

## 2.8 Overall severity
File: `backend/app/services/deviation_detector.py`

Rules:
- `normal`: spatial `ON_ROUTE` and temporal in `ON_TIME|DELAYED`
- `minor`: spatial `NEAR_ROUTE` and directional `TOWARD_DEST`
- `moderate`: spatial `OFF_ROUTE` and directional `TOWARD_DEST`
- `concerning`: temporal `STOPPED`
- `major`: spatial `OFF_ROUTE` and directional in `PERPENDICULAR|AWAY`
- fallback: `minor`

## 2.9 Route probability tracking
File: `backend/app/services/route_tracker.py`

For each route, score components:
- Distance score: `max(0, 1 - distance_m / 200)` (weight 50%)
- Bearing score: `max(0, 1 - bearing_diff / 90)` or `0.5` if no bearing (weight 30%)
- History score: previous probability (weight 20%)

Total score:
- `score = 0.5*distance_score + 0.3*bearing_score + 0.2*history_score`

Convert scores to probabilities using softmax:
- `p_i = exp(score_i - max_score) / sum(exp(score_j - max_score))`

Locking-related settings:
- lock threshold: `0.7`
- force-lock batch count: `6`

## 2.10 GPS buffering and batch trigger
File: `backend/app/services/gps_buffer.py`

Settings:
- batch size: `18` points
- timeout: `40` seconds
- overlap: `5` points

Trigger condition:
- process when `buffer_size >= 18` OR `time_since_last_batch >= 40s`.

After batch start:
- keep last 5 points in buffer for continuity.

## 2.11 Map matching fallback logic
File: `backend/app/services/map_matching.py`

If matching succeeds:
- use matched coordinates.

If matching fails or insufficient points:
- fallback to raw GPS coordinates.

## 2.12 Safety-zone distance and events
Files:
- `backend/app/services/safety_zone_provider.py`
- `backend/app/services/safety_zone_engine.py`

Key calculations:
- Polygon inside check: ray-casting.
- Polygon boundary distance: min point-to-segment distance across polygon edges.
- Circle/point zone boundary distance:
  - distance to center minus radius (clamped to `>=0`).

Approach thresholds:
- `1000m`, `500m`, `100m` (closer levels)

Events:
- entering: outside -> inside
- leaving: inside -> outside
- staying: still inside for at least configured minutes (default `5`)
- approaching: outside and crossed to a closer threshold

Cooldown:
- repeat notification blocked for configured hours (default `24`).

## 3) Important Practical Notes

1. Current runtime is Redis-first for journey tracking/state.
2. Geocoding endpoints exist in backend code but are not currently mounted in `main.py`.
3. Speed field is documented as km/h in backend schemas and deviation logic thresholds are tuned for km/h.
4. If your GPS source produces m/s, convert before sending if you want threshold behavior to match intended tuning.

