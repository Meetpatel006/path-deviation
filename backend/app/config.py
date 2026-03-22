"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Mapbox API
    MAPBOX_API_KEY: str
    
    # Database
    DATABASE_PATH: str = "path_deviation.db"  # For SQLite (local dev)
    DATABASE_URL: Optional[str] = None  # For PostgreSQL (production), e.g., postgresql://user:pass@host:5432/dbname
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: str = "logs/app.log"
    
    # GPS Batching Settings
    GPS_BATCH_SIZE: int = 18  # 15-20 points
    GPS_BATCH_TIMEOUT: int = 40  # seconds
    GPS_OVERLAP_POINTS: int = 5
    
    # Buffer Zones (meters)
    BUFFER_WALKING: int = 20
    BUFFER_CITY: int = 50
    BUFFER_HIGHWAY: int = 75
    
    # Route Tracking
    ROUTE_LOCK_THRESHOLD: float = 0.7  # 70% probability
    FORCE_LOCK_BATCHES: int = 6  # Force lock after N batches
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Optional Upstash Redis (REST) settings
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None

    # Redis (redis-py) settings
    REDIS_URL: Optional[str] = None
    REDIS_GPS_LIST_LIMIT: int = 200
    REDIS_DEVIATION_LIST_LIMIT: int = 200
    REDIS_JOURNEY_TTL_SECONDS: int = 86400  # 24 hours

    # Safety zone tracking
    SAFETY_ZONES_URL: str = (
        "https://smart-tourist-safety-app-backend-1.onrender.com"
        "/api/geofence/all-zones-styled"
    )
    SAFETY_ZONE_CACHE_TTL_SECONDS: int = 300
    SAFETY_STAYING_MINUTES: int = 1
    SAFETY_NOTIFICATION_COOLDOWN_HOURS: int = 24
    SAFETY_DEFAULT_POINT_RADIUS_METERS: int = 100
    SAFETY_USERS_MAX_RESULTS: int = 1000
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra environment variables (e.g., UPSTASH_* from CI or hosting)
        extra = "ignore"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
