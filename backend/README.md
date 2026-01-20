# GPS Path Deviation Detection System - Backend

Real-time GPS tracking system that detects when users deviate from planned routes using rule-based algorithms.

## Features

- **Route Planning**: Fetch multiple route alternatives from Mapbox Directions API
- **Real-time Tracking**: Process GPS points in real-time
- **Deviation Detection**: Detect spatial, temporal, and directional deviations
- **Route Probability**: Track which route the user is most likely following
- **WebSocket Support**: Real-time updates to frontend (Phase 4)
- **Production-Ready**: Comprehensive error handling, logging, and retry logic

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: SQLite with WAL mode
- **HTTP Client**: httpx (async)
- **Geometry**: Shapely, Geopy
- **Map Services**: Mapbox Directions API & Map Matching API
- **Testing**: pytest, pytest-asyncio

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection & setup
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── route_service.py     # Mapbox Directions API
│   │   └── journey_service.py   # Journey management
│   ├── api/
│   │   └── routes.py        # API endpoints
│   └── utils/
│       └── logger.py        # Logging configuration
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   └── test_api.py          # API tests
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Mapbox API key ([Get one here](https://account.mapbox.com/))

### Setup Steps

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Mapbox API key:
   ```
   MAPBOX_API_KEY=your_actual_mapbox_api_key_here
   ```

4. **Initialize database**:
   The database will be automatically initialized on first run.

## Running the Application

### Development Mode

```bash
cd backend
python -m app.main
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Journey Management

#### Start a Journey
```http
POST /api/journey/start
Content-Type: application/json

{
  "origin": {"lat": 18.5246, "lng": 73.8786},
  "destination": {"lat": 18.9582, "lng": 72.8321},
  "travel_mode": "driving"
}
```

Response:
```json
{
  "journey_id": "550e8400-e29b-41d4-a716-446655440000",
  "routes": [...],
  "start_time": "2026-01-20T12:00:00Z",
  "message": "Journey started successfully with 3 route alternative(s)"
}
```

#### Submit GPS Point
```http
POST /api/journey/{journey_id}/gps
Content-Type: application/json

{
  "lat": 18.5250,
  "lng": 73.8780,
  "timestamp": "2026-01-20T12:00:00Z",
  "speed": 60.0,
  "bearing": 270.0,
  "accuracy": 10.0
}
```

#### Get Journey Status
```http
GET /api/journey/{journey_id}
```

#### Complete Journey
```http
PUT /api/journey/{journey_id}/complete
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_api.py -v
```

## Configuration

All configuration is managed through environment variables in `.env`:

```env
# Mapbox API Key (Required)
MAPBOX_API_KEY=your_mapbox_api_key_here

# Database
DATABASE_PATH=path_deviation.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# GPS Batching (Phase 3)
GPS_BATCH_SIZE=18
GPS_BATCH_TIMEOUT=40
GPS_OVERLAP_POINTS=5

# Buffer Zones in meters (Phase 2)
BUFFER_WALKING=20
BUFFER_CITY=50
BUFFER_HIGHWAY=75

# Route Tracking (Phase 2)
ROUTE_LOCK_THRESHOLD=0.7
FORCE_LOCK_BATCHES=6

# Server
HOST=0.0.0.0
PORT=8000
```

## Development Phases

### ✅ Phase 1: Backend Core (COMPLETED)
- [x] Project structure and dependencies
- [x] Configuration and logging
- [x] Database schema (SQLite with WAL mode)
- [x] Pydantic models
- [x] Mapbox Directions API integration
- [x] Journey management service
- [x] API endpoints
- [x] Basic testing

### 🔄 Phase 2: Deviation Detection (IN PROGRESS)
- [ ] Geometry utilities (Haversine, point-to-line distance)
- [ ] Deviation detector service
- [ ] Route probability tracker
- [ ] Comprehensive testing

### 📋 Phase 3: Map Matching & GPS Buffering (PENDING)
- [ ] GPS buffer service
- [ ] Mapbox Map Matching API integration
- [ ] Tracking service pipeline
- [ ] Batch processing logic

### 📋 Phase 4: WebSocket (PENDING)
- [ ] WebSocket manager
- [ ] Real-time updates
- [ ] Connection management

### 📋 Phase 5: Frontend (PENDING)
- [ ] Interactive map with Mapbox GL JS
- [ ] Real-time visualization
- [ ] GPS simulator

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: All levels (with rotation, 10MB max, 5 backups)

Log file location: `logs/app.log`

## Database Schema

### Tables
- **journeys**: Journey metadata (origin, destination, status)
- **routes**: Route alternatives for each journey
- **gps_points**: GPS tracking points
- **deviation_events**: Deviation events detected

See `app/database.py` for complete schema.

## Error Handling

The application includes comprehensive error handling:
- **Retry logic**: Mapbox API calls retry up to 3 times with exponential backoff
- **Validation**: Pydantic validates all requests
- **Logging**: All errors logged with context
- **Graceful degradation**: Continues with raw GPS if Map Matching fails

## Contributing

1. Create feature branch
2. Make changes with tests
3. Run tests: `pytest`
4. Format code: `black app/ tests/`
5. Submit pull request

## License

Proprietary - All rights reserved

## Support

For issues or questions, check the logs in `logs/app.log` or contact the development team.
