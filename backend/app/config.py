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
    DATABASE_PATH: str = "path_deviation.db"
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
