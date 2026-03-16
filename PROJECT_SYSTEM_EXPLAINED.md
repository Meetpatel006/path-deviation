# GPS Path Deviation System - Complete Project Guide

This document explains:
- The project structure
- What each file does
- All API/WebSocket endpoints in detail
- Runtime flow with ASCII diagrams

## 1) High-Level Architecture

```text
+---------------------+         HTTP/WS          +----------------------------+
| Frontend (Vanilla)  | <----------------------> | FastAPI Backend            |
| - map.js            |                          | - api/routes.py            |
| - ui.js             |                          | - api/websocket.py         |
| - websocket-client  |                          | - api/safety_routes.py     |
| - gps-simulator     |                          |                            |
+----------+----------+                          +-------------+--------------+
           |                                                     |
           | Mapbox JS APIs                                      | Mapbox Web APIs
           v                                                     v
+-------------------------+                         +--------------------------+
| Mapbox GL + Geocoding   |                         | Directions + Matching +  |
| (client-side)           |                         | Geocoding (server-side)  |
+-------------------------+                         +--------------------------+
                                                               |
                                                               v
                                                +-----------------------------+
                                                | Redis / Upstash Redis       |
                                                | Journey state, GPS, events  |
                                                +-----------------------------+
```

## 2) Journey Processing Flow

```text
POST /api/journey/start
  -> route_service.fetch_routes()
  -> journey_store.create_journey()
  -> tracking_service.start_journey_tracking()
  -> returns journey_id + route alternatives

POST /api/journey/{id}/gps
  -> journey_store.add_gps_point()  [persist point]
  -> websocket_manager.broadcast_gps_update() [instant UI feedback]
  -> gps_buffer.add_point()
     -> (when batch/timeout hit) tracking_service._process_batch()
         -> map_matching_service.match_trace_with_fallback()
         -> route_tracker.update_probabilities()
         -> deviation_detector.check_*()
         -> journey_store.add_deviation_event()
         -> websocket_manager.broadcast_deviation_update()
         -> websocket_manager.broadcast_batch_processed()
```

## 3) Directory Structure (ASCII Tree)

```text
path deviation/
|-- AGENTS.md
|-- AUTOCOMPLETE_TESTING.md
|-- PROJECT_COMPLETE.md
|-- PROJECT_SYSTEM_EXPLAINED.md
|-- plan.md
|-- .gitignore
|-- routes/
|   `-- route.json
|-- backend/
|   |-- Dockerfile
|   |-- docker-compose.yml
|   |-- README.md
|   |-- requirements.txt
|   |-- app/
|   |   |-- __init__.py
|   |   |-- main.py
|   |   |-- config.py
|   |   |-- database.py
|   |   |-- api/
|   |   |   |-- __init__.py
|   |   |   |-- routes.py
|   |   |   |-- safety_routes.py
|   |   |   `-- websocket.py
|   |   |-- models/
|   |   |   |-- __init__.py
|   |   |   `-- schemas.py
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   |-- deviation_detector.py
|   |   |   |-- geocoding_service.py
|   |   |   |-- gps_buffer.py
|   |   |   |-- journey_service.py
|   |   |   |-- journey_store.py
|   |   |   |-- map_matching.py
|   |   |   |-- redis_client.py
|   |   |   |-- route_service.py
|   |   |   |-- route_tracker.py
|   |   |   |-- safety_store.py
|   |   |   |-- safety_zone_engine.py
|   |   |   |-- safety_zone_provider.py
|   |   |   |-- tracking_service.py
|   |   |   `-- websocket_manager.py
|   |   `-- utils/
|   |       |-- __init__.py
|   |       |-- geometry.py
|   |       `-- logger.py
|   `-- tests/
|       |-- conftest.py
|       |-- test_api.py
|       |-- test_deviation.py
|       |-- test_geometry.py
|       |-- test_geometry_simple.py
|       |-- test_phase1.py
|       |-- test_phase2_e2e.py
|       |-- test_phase3_phase4.py
|       |-- test_postgres_migration.py
|       |-- test_simple.py
|       |-- test_websocket_minimal.py
|       |-- test_websocket_simple.py
|       `-- e2e/
|           |-- README.md
|           |-- test_e2e_ultimate.py
|           |-- test_redis_e2e.py
|           |-- test_route_data_ultimate.py
|           |-- test_stress_ultimate.py
|           `-- test_visualization.html
`-- frontend/
    |-- README.md
    |-- DEBUGGING_GUIDE.md
    |-- websocket-test.html
    |-- index.html
    |-- css/
    |   `-- styles.css
    `-- js/
        |-- app.js
        |-- config.js
        |-- geocoding.js
        |-- gps-simulator.js
        |-- map.js
        |-- real-gps-tracker.js
        |-- ui.js
        `-- websocket-client.js
```

## 4) API and WebSocket Endpoints (Detailed)

## Active REST Endpoints

### 4.1 `GET /`
- Purpose: Root API info.
- Response:
  - `message`, `version`, `docs`, `health`.

### 4.2 `GET /health`
- Purpose: Service health + Redis connectivity check.
- Response fields:
  - `status`: `"healthy"`
  - `version`
  - `database`: currently `"disabled"` (Redis-only mode)
  - `redis`: `"connected" | "disconnected" | "disabled"`

### 4.3 `POST /api/journey/start`
- File: `backend/app/api/routes.py`
- Request body (`JourneyStartRequest`):
  - `origin`: `{ lat, lng }`
  - `destination`: `{ lat, lng }`
  - `travel_mode`: `"driving"` or `"walking"`
- Success (`201`, `JourneyStartResponse`):
  - `journey_id`
  - `routes`: up to 3 route alternatives with geometry, distance, duration
  - `start_time`
  - `message`
- Main internal steps:
  - Fetch Mapbox routes (`route_service`)
  - Create journey in Redis (`journey_store`)
  - Initialize in-memory tracking (`tracking_service`)
- Errors:
  - `400`: invalid input/no routes
  - `500`: unexpected failure

### 4.4 `POST /api/journey/{journey_id}/gps`
- File: `backend/app/api/routes.py`
- Request body (`GPSPoint`):
  - `lat`, `lng`, `timestamp`
  - optional `speed`, `bearing`, `accuracy`
- Success (`200`, `GPSPointResponse`):
  - `status`, `journey_id`, `message`, `batch_processed`
- Main internal steps:
  - Validate journey exists + active status
  - Persist point to Redis + geo index
  - Broadcast `gps_update` over WebSocket
  - Buffer for batch processing (deviation + route probability)
- Errors:
  - `404`: unknown journey
  - `400`: journey not active / bad input
  - `500`: processing failure

### 4.5 `GET /api/journey/{journey_id}`
- File: `backend/app/api/routes.py`
- Purpose: Current journey state snapshot.
- Success (`200`, `JourneyState`):
  - `journey_id`
  - `current_status`
  - `route_probabilities`
  - `progress_percentage`
  - `time_deviation`
  - `last_gps`
  - `deviation_status`:
    - `spatial`: `ON_ROUTE | NEAR_ROUTE | OFF_ROUTE`
    - `temporal`: `ON_TIME | DELAYED | SEVERELY_DELAYED | STOPPED`
    - `directional`: `TOWARD_DEST | PERPENDICULAR | AWAY`
    - `severity`: `normal | minor | moderate | concerning | major`
- Errors:
  - `404`: not found
  - `500`: compute failure

### 4.6 `PUT /api/journey/{journey_id}/complete`
- File: `backend/app/api/routes.py`
- Purpose: Mark journey completed + cleanup tracking buffers/state.
- Success (`200`):
  - `status: "success"`
  - `message`
- Errors:
  - `404`: not found
  - `500`: completion failure

### 4.7 `POST /api/safety/location`
- File: `backend/app/api/safety_routes.py`
- Request (`SafetyLocationUpdateRequest`):
  - `userId`, `latitude`, `longitude`, `timestamp`, `safetyScore`
- Success (`200`, `SafetyLocationUpdateResponse`):
  - `status`, `userId`, `locationStoredAt`, `events[]`
- Event types produced by engine:
  - `approaching`, `entering`, `staying`, `leaving`

### 4.8 `GET /api/safety/users/latest`
- File: `backend/app/api/safety_routes.py`
- Query params:
  - `minutes` (default `120`, min `1`, max `1440`)
  - `limit` (default `500`, max from `SAFETY_USERS_MAX_RESULTS`)
- Success (`200`, `LatestUserLocationsResponse`):
  - `users[]` with latest user position/safety metadata.

## Active WebSocket Endpoints

### 4.9 `WS /ws/journey/{journey_id}?client_id=web_client`
- File: `backend/app/api/websocket.py`
- Purpose: Real-time journey updates.
- Server -> client message types:
  - `connection_ack`
  - `gps_update`
  - `deviation_update`
  - `batch_processed`
  - `ping`
  - `error`
- Client -> server message types:
  - `pong`
  - `subscribe_events` (currently logged only, no filtering yet)

### 4.10 `GET /ws/stats`
- File: `backend/app/api/websocket.py`
- Purpose: WebSocket connection stats (active journeys + client counts).

## Defined But Not Mounted (Important)

These endpoints exist in code but are not currently registered in `main.py`:
- `GET /api/geocoding/search`
- `GET /api/geocoding/autocomplete`

Reason: `geocoding_router` is created in `backend/app/api/routes.py`, but only `routes.router` is included in `backend/app/main.py`.

## 5) Notes About Current Behavior

- Runtime is effectively Redis-only for journey tracking (`main.py` logs "Database disabled").
- `backend/app/database.py` and `backend/app/services/journey_service.py` still exist as SQL-capable legacy/support modules.
- Frontend offers `"cycling"` in `travel-mode`, but backend validation currently allows only `"driving"` or `"walking"`.
- Frontend geocoding is client-side (`frontend/js/geocoding.js`) using Mapbox directly, independent of the backend geocoding endpoints.

## 6) File-by-File Reference (Every File)

## Root Files

| File | What It Is Used For |
|---|---|
| `AGENTS.md` | Repository-specific instructions for coding agents and workflow conventions. |
| `AUTOCOMPLETE_TESTING.md` | Step-by-step guide for testing/troubleshooting frontend autocomplete behavior. |
| `PROJECT_COMPLETE.md` | Project completion summary and quick-start notes. |
| `plan.md` | Large planning/specification document for phased implementation. |
| `.gitignore` | Ignore rules for env files, DB files, logs, caches, build artifacts, IDE files. |

## Route Data

| File | What It Is Used For |
|---|---|
| `routes/route.json` | Real route payload dataset (used by E2E scripts for realistic path simulations). |

## Backend Infra/Meta

| File | What It Is Used For |
|---|---|
| `backend/Dockerfile` | Multi-stage production image build for FastAPI backend. |
| `backend/docker-compose.yml` | Local container orchestration for backend service and persistent volumes. |
| `backend/README.md` | Backend setup, API usage, and configuration notes. |
| `backend/requirements.txt` | Python dependencies for runtime, testing, and development tooling. |

## Backend App Core

| File | What It Is Used For |
|---|---|
| `backend/app/__init__.py` | Package marker for backend app module. |
| `backend/app/main.py` | FastAPI app creation, middleware, exception handlers, router registration, health/root endpoints. |
| `backend/app/config.py` | Pydantic settings loader for env-based configuration (Mapbox, Redis, safety settings, etc.). |
| `backend/app/database.py` | SQLite/PostgreSQL init + query helpers (legacy/optional in current Redis-first runtime). |

## Backend API Layer

| File | What It Is Used For |
|---|---|
| `backend/app/api/__init__.py` | API package marker. |
| `backend/app/api/routes.py` | Journey endpoints (`start`, `gps`, `status`, `complete`) + geocoding endpoints (currently unmounted). |
| `backend/app/api/safety_routes.py` | Safety location ingest + latest safety user locations endpoints. |
| `backend/app/api/websocket.py` | WebSocket endpoint and connection stats endpoint. |

## Backend Models

| File | What It Is Used For |
|---|---|
| `backend/app/models/__init__.py` | Models package marker. |
| `backend/app/models/schemas.py` | All request/response models: journey, GPS, deviation, safety DTOs. |

## Backend Services

| File | What It Is Used For |
|---|---|
| `backend/app/services/__init__.py` | Services package marker. |
| `backend/app/services/redis_client.py` | Redis/Upstash client bootstrap and shutdown helpers. |
| `backend/app/services/journey_store.py` | Redis-backed persistence for journey metadata, routes, GPS points, deviation events, tracking state. |
| `backend/app/services/tracking_service.py` | Core orchestration pipeline for GPS buffering, map matching, route probability, deviation detection, WS broadcasts. |
| `backend/app/services/gps_buffer.py` | Per-journey GPS buffering with size/timeout triggers and overlap logic. |
| `backend/app/services/map_matching.py` | Mapbox map matching integration with fallback to raw points. |
| `backend/app/services/route_service.py` | Mapbox Directions integration to fetch route alternatives. |
| `backend/app/services/route_tracker.py` | Probability model for selecting most likely route (distance + bearing + history weighted scoring). |
| `backend/app/services/deviation_detector.py` | Spatial, temporal, directional deviation checks + overall severity classification. |
| `backend/app/services/websocket_manager.py` | Connection manager and broadcast helpers per journey channel. |
| `backend/app/services/safety_zone_provider.py` | Pulls and normalizes external zone data (danger zones, risk grids, geofences). |
| `backend/app/services/safety_zone_engine.py` | Generates safety events (`approaching`, `entering`, `staying`, `leaving`) from location updates. |
| `backend/app/services/safety_store.py` | Safety state/latest location storage in Redis with in-memory fallback. |
| `backend/app/services/geocoding_service.py` | Server-side Mapbox geocoding/autocomplete service wrapper. |
| `backend/app/services/journey_service.py` | SQL-based journey CRUD/event persistence service (legacy/support path). |

## Backend Utils

| File | What It Is Used For |
|---|---|
| `backend/app/utils/__init__.py` | Utils package marker. |
| `backend/app/utils/logger.py` | Global logger setup with rotating file handler + console handler. |
| `backend/app/utils/geometry.py` | Haversine, bearing, point/segment, nearest-point, progress, interpolation utilities. |

## Backend Tests

| File | What It Is Used For |
|---|---|
| `backend/tests/conftest.py` | Shared pytest fixtures and test client setup. |
| `backend/tests/test_api.py` | Basic endpoint tests (`/`, `/health`, validation and not-found cases). |
| `backend/tests/test_deviation.py` | Detailed unit tests for deviation detector logic and severity matrix. |
| `backend/tests/test_geometry.py` | Unit tests for geometry helpers with expected numeric behavior. |
| `backend/tests/test_geometry_simple.py` | Lightweight/simple geometry test runner. |
| `backend/tests/test_phase1.py` | Async phase-1 validation script against running API. |
| `backend/tests/test_phase2_e2e.py` | Phase-2 end-to-end journey lifecycle and route probability tests. |
| `backend/tests/test_phase3_phase4.py` | Pipeline tests for buffering, map matching, websocket flows, and stats. |
| `backend/tests/test_postgres_migration.py` | DB adapter/migration checks for PostgreSQL/SQLite compatibility. |
| `backend/tests/test_simple.py` | Requests-based simple phase test script. |
| `backend/tests/test_websocket_minimal.py` | Minimal websocket handshake and ack test. |
| `backend/tests/test_websocket_simple.py` | WebSocket functional test using FastAPI TestClient. |

## Backend E2E Tests

| File | What It Is Used For |
|---|---|
| `backend/tests/e2e/README.md` | E2E suite documentation and run guidance. |
| `backend/tests/e2e/test_e2e_ultimate.py` | Comprehensive scenario-based full-system E2E script. |
| `backend/tests/e2e/test_redis_e2e.py` | Redis-only API flow test from start to completion. |
| `backend/tests/e2e/test_route_data_ultimate.py` | E2E using real route data from `routes/route.json`. |
| `backend/tests/e2e/test_stress_ultimate.py` | High-load/chaos/stress testing of concurrent tracking behavior. |
| `backend/tests/e2e/test_visualization.html` | Browser dashboard for visualizing E2E run telemetry. |

## Frontend Core

| File | What It Is Used For |
|---|---|
| `frontend/index.html` | Main UI shell: control panel, status cards, map container, script loading order. |
| `frontend/css/styles.css` | Full frontend styling (layout, badges, controls, alerts, map panels). |
| `frontend/js/config.js` | Frontend constants (API/WS base URLs, Mapbox token, styles, simulation and smoothing settings). |
| `frontend/js/app.js` | App bootstrap, init checks, visibility/unload lifecycle behavior. |
| `frontend/js/ui.js` | UI actions: start/complete journey, status updates, parsing/resolving locations, button handlers. |
| `frontend/js/map.js` | Mapbox manager: map init, route rendering, live marker updates, route highlighting, trail and pick-on-map support. |
| `frontend/js/websocket-client.js` | Browser WebSocket client, reconnect logic, message routing, UI/map update hooks. |
| `frontend/js/gps-simulator.js` | Synthetic GPS generation and scenario-based route deviations for testing. |
| `frontend/js/real-gps-tracker.js` | Browser geolocation tracker that streams real device GPS to backend. |
| `frontend/js/geocoding.js` | Client-side Mapbox geocoding/autocomplete service and dropdown manager. |

## Frontend Docs/Tools

| File | What It Is Used For |
|---|---|
| `frontend/README.md` | Frontend usage and setup guide. |
| `frontend/DEBUGGING_GUIDE.md` | Browser-console-first debugging checklist and issue fixes. |
| `frontend/websocket-test.html` | Standalone WebSocket diagnostics page for manual connection testing. |

