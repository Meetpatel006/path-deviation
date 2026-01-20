"""
Test configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database import init_db
from app.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_db():
    """Initialize test database"""
    # Use a test database
    original_db = settings.DATABASE_PATH
    settings.DATABASE_PATH = "test_path_deviation.db"
    
    # Initialize database
    await init_db()
    
    yield
    
    # Cleanup
    settings.DATABASE_PATH = original_db
    if os.path.exists("test_path_deviation.db"):
        os.remove("test_path_deviation.db")
    if os.path.exists("test_path_deviation.db-shm"):
        os.remove("test_path_deviation.db-shm")
    if os.path.exists("test_path_deviation.db-wal"):
        os.remove("test_path_deviation.db-wal")


@pytest.fixture
def client(test_db):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_journey_request():
    """Sample journey start request"""
    return {
        "origin": {"lat": 18.5246, "lng": 73.8786},
        "destination": {"lat": 18.9582, "lng": 72.8321},
        "travel_mode": "driving"
    }


@pytest.fixture
def sample_gps_point():
    """Sample GPS point"""
    return {
        "lat": 18.5250,
        "lng": 73.8780,
        "timestamp": "2026-01-20T12:00:00Z",
        "speed": 60.0,
        "bearing": 270.0,
        "accuracy": 10.0
    }
