"""
Database initialization and connection management
Supports both SQLite (local dev) and PostgreSQL (production)
"""
import aiosqlite
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Union, Any, Optional
from pathlib import Path

from app.config import settings
from app.utils.logger import logger


# Global connection pool for PostgreSQL
_pg_pool: Optional[asyncpg.Pool] = None


def is_postgres() -> bool:
    """Check if we should use PostgreSQL"""
    return settings.DATABASE_URL is not None and settings.DATABASE_URL.startswith("postgresql")


async def get_pg_pool() -> asyncpg.Pool:
    """Get or create PostgreSQL connection pool"""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60,
            server_settings={
                'jit': 'off'  # Disable JIT for faster connection
            }
        )
        logger.info("PostgreSQL connection pool created")
    return _pg_pool


async def close_pg_pool():
    """Close PostgreSQL connection pool"""
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("PostgreSQL connection pool closed")


def convert_query_for_postgres(query: str, params: tuple) -> str:
    """
    Convert SQL query with ? placeholders to PostgreSQL $1, $2, etc.
    
    Args:
        query: SQL query with ? placeholders
        params: Query parameters tuple
    
    Returns:
        Query string with $1, $2, etc. placeholders
    """
    pg_query = query
    for i in range(1, len(params) + 1):
        pg_query = pg_query.replace('?', f'${i}', 1)
    return pg_query


async def init_db() -> None:
    """
    Initialize database with schema
    Uses PostgreSQL in production (Render) or SQLite locally
    """
    if is_postgres():
        await _init_postgres()
    else:
        await _init_sqlite()


async def _init_postgres() -> None:
    """Initialize PostgreSQL database schema"""
    try:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            # Create journeys table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS journeys (
                    id TEXT PRIMARY KEY,
                    origin_lat DOUBLE PRECISION NOT NULL,
                    origin_lng DOUBLE PRECISION NOT NULL,
                    destination_lat DOUBLE PRECISION NOT NULL,
                    destination_lng DOUBLE PRECISION NOT NULL,
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
                    id SERIAL PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    route_index INTEGER NOT NULL,
                    geometry TEXT NOT NULL,
                    distance_meters DOUBLE PRECISION NOT NULL,
                    duration_seconds DOUBLE PRECISION NOT NULL,
                    summary TEXT,
                    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE,
                    UNIQUE(journey_id, route_index)
                )
            """)
            
            # Create GPS points table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gps_points (
                    id SERIAL PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    lat DOUBLE PRECISION NOT NULL,
                    lng DOUBLE PRECISION NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    speed DOUBLE PRECISION,
                    bearing DOUBLE PRECISION,
                    accuracy DOUBLE PRECISION,
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
                    id SERIAL PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('normal', 'minor', 'moderate', 'concerning', 'major')),
                    spatial_status TEXT CHECK(spatial_status IN ('ON_ROUTE', 'NEAR_ROUTE', 'OFF_ROUTE')),
                    temporal_status TEXT CHECK(temporal_status IN ('ON_TIME', 'DELAYED', 'SEVERELY_DELAYED', 'STOPPED')),
                    directional_status TEXT CHECK(directional_status IN ('TOWARD_DEST', 'PERPENDICULAR', 'AWAY')),
                    distance_from_route DOUBLE PRECISION,
                    time_deviation DOUBLE PRECISION,
                    route_probabilities TEXT,
                    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
                )
            """)
            
            # Create index on deviation events
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_deviation_journey_timestamp 
                ON deviation_events(journey_id, timestamp)
            """)
            
        logger.info("PostgreSQL database initialized successfully")
            
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL database: {e}", exc_info=True)
        raise


async def _init_sqlite() -> None:
    """Initialize SQLite database schema"""
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
            await conn.execute("PRAGMA busy_timeout=5000;")  # 5 second timeout
            
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
            logger.info(f"SQLite database initialized successfully at {settings.DATABASE_PATH}")
        else:
            logger.info(f"SQLite database schema verified at {settings.DATABASE_PATH}")
            
    except Exception as e:
        logger.error(f"Error initializing SQLite database: {e}", exc_info=True)
        raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[Union[aiosqlite.Connection, asyncpg.Connection], None]:
    """
    Async context manager for database connections
    Automatically uses PostgreSQL (production) or SQLite (local)
    
    Yields:
        Database connection (PostgreSQL or SQLite)
    """
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            try:
                yield conn
            except Exception as e:
                logger.error(f"PostgreSQL error: {e}")
                raise
    else:
        async with aiosqlite.connect(
            settings.DATABASE_PATH,
            timeout=30.0  # 30 second timeout for locks
        ) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                yield conn
            except Exception as e:
                await conn.rollback()
                logger.error(f"SQLite error: {e}")
                raise


async def execute_query(query: str, params: tuple = ()) -> list:
    """
    Execute a SELECT query and return results
    Works with both PostgreSQL and SQLite
    
    Args:
        query: SQL query string (use $1, $2 for PostgreSQL or ? for SQLite)
        params: Query parameters
    
    Returns:
        List of rows as dictionaries
    """
    try:
        # Convert query parameters if using PostgreSQL
        if is_postgres():
            # Convert ? placeholders to $1, $2, etc. for PostgreSQL (preserve order)
            pg_query = query
            for i in range(1, len(params) + 1):
                pg_query = pg_query.replace('?', f'${i}', 1)
            
            async with get_db() as conn:
                rows = await conn.fetch(pg_query, *params)
                return [dict(row) for row in rows]
        else:
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
    Works with both PostgreSQL and SQLite
    
    Args:
        query: SQL query string
        params: Query parameters
    
    Returns:
        Number of affected rows
    """
    try:
        if is_postgres():
            # Convert ? placeholders to $1, $2, etc. for PostgreSQL (preserve order)
            pg_query = query
            for i in range(1, len(params) + 1):
                pg_query = pg_query.replace('?', f'${i}', 1)
            
            async with get_db() as conn:
                result = await conn.execute(pg_query, *params)
                # Extract row count from result string like "INSERT 0 5"
                return int(result.split()[-1]) if result else 0
        else:
            async with get_db() as conn:
                cursor = await conn.execute(query, params)
                await conn.commit()
                return cursor.rowcount
    except Exception as e:
        logger.error(f"Error executing update: {e}")
        raise
