# AGENTS.md - GPS Path Deviation Detection System

Guidelines for agentic coding assistants working in this repository.

## Project Overview

Full-stack GPS tracking application that detects route deviations in real-time.
- **Backend**: Python 3.x with FastAPI
- **Frontend**: Vanilla JavaScript with Mapbox GL JS
- **Database**: SQLite with WAL mode
- **Architecture**: REST API + WebSocket for real-time communication

## Build, Lint, and Test Commands

### Backend (Python)

```bash
# Working directory for backend commands
cd backend

# Install dependencies
pip install -r requirements.txt

# Run development server
python -m app.main
# Or with uvicorn directly:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run single test
pytest tests/test_api.py::test_health_check -v

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run tests verbosely
pytest -v -s

# Code formatting (Black)
black app/ tests/

# Linting (Flake8)
flake8 app/ tests/ --max-line-length=100

# Type checking (MyPy)
mypy app/
```

### Frontend (JavaScript)

```bash
# No build step - vanilla JavaScript
# Serve with any HTTP server, e.g.:
python -m http.server 8080 --directory frontend

# Or use the backend server which can serve static files
```

### Environment Setup

Create `backend/.env` file with:
```
MAPBOX_API_KEY=your_actual_mapbox_api_key_here
DATABASE_PATH=path_deviation.db
LOG_LEVEL=INFO
```

## Code Style Guidelines

### Python Backend

#### Import Order
1. Standard library imports
2. Third-party imports (FastAPI, Pydantic, etc.)
3. Local application imports (app.*)

```python
# Standard library
from typing import List, Tuple, Optional
from datetime import datetime

# Third-party
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Local
from app.models.schemas import GPSPoint
from app.utils.logger import logger
```

#### Formatting Standards
- **Line Length**: 100 characters maximum (enforced by Flake8)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Use double quotes for strings
- **Formatter**: Black (run before committing)
- **Docstrings**: Google-style docstrings for all public functions/classes

```python
def haversine_distance(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    """
    Calculate great-circle distance between two GPS points using Haversine formula
    
    Args:
        point1: (lat, lng) in decimal degrees
        point2: (lat, lng) in decimal degrees
    
    Returns:
        Distance in meters
    
    Example:
        >>> pune = (18.5246, 73.8786)
        >>> dist = haversine_distance(pune, mumbai)
    """
```

#### Type Annotations
- **Always** use type hints for function parameters and return types
- Use `typing` module types: `List`, `Dict`, `Tuple`, `Optional`
- Pydantic models for API request/response schemas

```python
def check_spatial_deviation(
    self,
    gps_point: GPSPoint,
    speed: float
) -> Tuple[str, float, str]:
    # Implementation
```

#### Naming Conventions
- **Files**: lowercase with underscores (`deviation_detector.py`)
- **Classes**: PascalCase (`DeviationDetector`, `RouteTracker`)
- **Functions/Variables**: snake_case (`calculate_bearing`, `min_distance`)
- **Constants**: UPPERCASE (`BUFFER_WALKING`, `MAPBOX_API_KEY`)
- **Private**: Single underscore prefix (`_internal_helper`)

#### Error Handling
- Use `try-except` blocks for external API calls and I/O operations
- Log errors with appropriate severity (`logger.error()`, `logger.warning()`)
- Raise `HTTPException` for API errors with appropriate status codes
- Use `ValueError` for validation errors

```python
try:
    routes = await route_service.fetch_routes(origin, destination, mode)
    if not routes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No routes found between the given locations"
        )
except ValueError as e:
    logger.error(f"Validation error: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

#### Logging Standards
- Use structured logging from `app.utils.logger`
- Log levels: `DEBUG` (details), `INFO` (operations), `WARNING` (issues), `ERROR` (failures)
- Include context in log messages

```python
logger.info(f"Journey {journey_id} started successfully with {len(routes)} route(s)")
logger.debug(f"Spatial deviation: speed={speed:.1f}km/h, buffer={buffer}m")
logger.error(f"Failed to initialize database: {e}", exc_info=True)
```

### Frontend JavaScript

#### Style
- **Indentation**: 4 spaces
- **Quotes**: Single quotes for strings
- **Semicolons**: Always use semicolons
- **Comments**: Use `//` for single-line, `/* */` for multi-line

#### Naming
- **Variables/Functions**: camelCase (`currentJourney`, `initApp`)
- **Constants**: UPPERCASE (`CONFIG`, `API_BASE_URL`)
- **Classes**: PascalCase (if used)

#### Module Pattern
```javascript
// Use IIFE or object namespacing
const mapManager = {
    map: null,
    
    init() {
        // Implementation
    }
};
```

#### Error Handling
```javascript
try {
    const response = await fetch(url, options);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
} catch (error) {
    console.error('[API] Error:', error);
    showError('Failed to communicate with server');
}
```

## Architecture Patterns

### Service Layer Pattern
- **API Layer** (`app/api/`): HTTP endpoints, request validation
- **Service Layer** (`app/services/`): Business logic, external API integration
- **Data Layer** (`app/database.py`): Database operations

Never mix concerns - API handlers should delegate to services, services should use database utilities.

### Database Context Manager
Always use `with` statements for database connections:

```python
from app.database import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    # Execute queries
    conn.commit()
```

### Async/Await
- API endpoints are `async def`
- Use `await` for external API calls (httpx)
- Database operations are synchronous (sqlite3)

## Testing Guidelines

- **Location**: `backend/tests/`
- **Fixtures**: Define shared fixtures in `conftest.py`
- **Naming**: Test functions start with `test_`
- **Structure**: Arrange-Act-Assert pattern

```python
def test_haversine_distance():
    # Arrange
    pune = (18.5246, 73.8786)
    mumbai = (18.9582, 72.8321)
    
    # Act
    distance = haversine_distance(pune, mumbai)
    
    # Assert
    assert 148000 < distance < 149000  # ~148.4 km
```

## Key Files Reference

- `backend/app/main.py:150` - FastAPI application entry point
- `backend/app/models/schemas.py:171` - Pydantic request/response models
- `backend/app/services/deviation_detector.py:284` - Core deviation detection algorithm
- `backend/app/utils/geometry.py:357` - GPS calculation utilities
- `backend/app/database.py:174` - Database schema and helpers
- `frontend/js/app.js:65` - Frontend application orchestrator

## Common Tasks

### Adding a new API endpoint
1. Define Pydantic schemas in `app/models/schemas.py`
2. Create service logic in `app/services/`
3. Add route handler in `app/api/routes.py`
4. Write tests in `tests/test_api.py`

### Adding a new service
1. Create file in `app/services/`
2. Use class-based design with `__init__` for dependencies
3. Add logging for key operations
4. Handle errors gracefully
5. Write unit tests

### Database changes
1. Modify schema in `app/database.py:init_db()`
2. Add migration logic if needed
3. Update relevant service methods
4. Test with fresh database

## Important Notes

- **No build process**: Frontend is vanilla JS, served directly
- **Database**: SQLite file at `backend/path_deviation.db` (gitignored)
- **Mapbox API**: Required for route fetching and map matching
- **Real-time**: WebSocket at `/ws/{journey_id}` for live updates
- **GPS Buffering**: Collects 18 points or 40 seconds before processing
- **Route Alternatives**: System tracks 3 routes with probability scoring
