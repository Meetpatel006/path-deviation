"""
Database initialization and connection management
"""
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from app.config import settings
from app.utils.logger import logger


async def init_db() -> None:
    """
    Initialize database with schema and enable WAL mode for better concurrency
    """
    db_path = Path(settings.DATABASE_PATH)
    db_exists = db_path.exists()
    
    try:
        async with aiosqlite.connect(settings.DATABASE_PATH) as conn:
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA cache_size=10000;")
            await conn.execute("PRAGMA temp_store=MEMORY;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            
            # Create journeys table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS journeys (
                    id TEXT PRIMARY KEY,
                    origin_lat REAL NOT NULL,
                    origin_lng REAL NOT NULL,
                    destination_lat REAL NOT NULL,
                    destination_lng REAL NOT NULL,
                    travel_mode TEXT NOT NULL CHECK(travel_mode IN ('driving', 'walking')),
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL CHECK(status IN ('active', 'completed', 'abandoned')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create routes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    journey_id TEXT NOT NULL,
                    route_index INTEGER NOT NULL,
                    geometry TEXT NOT NULL,
                    distance_meters REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    summary TEXT,
                    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE,
                    UNIQUE(journey_id, route_index)
                )
            """)
            
            # Create GPS points table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gps_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    journey_id TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    speed REAL,
                    bearing REAL,
                    accuracy REAL,
                    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
                )
            """)
            
            # Create index on GPS points for faster queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gps_journey_timestamp 
                ON gps_points(journey_id, timestamp)
            """)
            
            # Create deviation events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS deviation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    journey_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('normal', 'minor', 'moderate', 'concerning', 'major')),
                    spatial_status TEXT CHECK(spatial_status IN ('ON_ROUTE', 'NEAR_ROUTE', 'OFF_ROUTE')),
                    temporal_status TEXT CHECK(temporal_status IN ('ON_TIME', 'DELAYED', 'SEVERELY_DELAYED', 'STOPPED')),
                    directional_status TEXT CHECK(directional_status IN ('TOWARD_DEST', 'PERPENDICULAR', 'AWAY')),
                    distance_from_route REAL,
                    time_deviation REAL,
                    route_probabilities TEXT,
                    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
                )
            """)
            
            # Create index on deviation events
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_deviation_journey_timestamp 
                ON deviation_events(journey_id, timestamp)
            """)
            
            await conn.commit()
            
        if not db_exists:
            logger.info(f"Database initialized successfully at {settings.DATABASE_PATH}")
        else:
            logger.info(f"Database schema verified at {settings.DATABASE_PATH}")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager for database connections
    
    Yields:
        aiosqlite connection with row factory enabled
    """
    async with aiosqlite.connect(settings.DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row  # Access columns by name
        try:
            yield conn
        except Exception as e:
            await conn.rollback()
            logger.error(f"Database error: {e}")
            raise


async def execute_query(query: str, params: tuple = ()) -> list:
    """
    Execute a SELECT query and return results
    
    Args:
        query: SQL query string
        params: Query parameters
    
    Returns:
        List of rows as dictionaries
    """
    try:
        async with get_db() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise


async def execute_update(query: str, params: tuple = ()) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query
    
    Args:
        query: SQL query string
        params: Query parameters
    
    Returns:
        Number of affected rows
    """
    try:
        async with get_db() as conn:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Error executing update: {e}")
        raise
