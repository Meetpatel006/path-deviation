"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Tuple, Optional, Dict
from datetime import datetime


class LocationPoint(BaseModel):
    """Geographic coordinate point"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lat": 18.5246,
                "lng": 73.8786
            }
        }


class GPSPoint(BaseModel):
    """GPS tracking point with optional metadata"""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    timestamp: datetime
    speed: Optional[float] = Field(None, ge=0, description="Speed in km/h")
    bearing: Optional[float] = Field(None, ge=0, lt=360, description="Bearing in degrees")
    accuracy: Optional[float] = Field(None, ge=0, description="Accuracy in meters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lat": 18.5250,
                "lng": 73.8780,
                "timestamp": "2026-01-20T12:00:00Z",
                "speed": 60.0,
                "bearing": 45.0,
                "accuracy": 10.0
            }
        }


class Route(BaseModel):
    """Route alternative with geometry and metadata"""
    route_id: str
    route_index: int = Field(..., ge=0, le=2, description="Route alternative index (0-2)")
    geometry: List[Tuple[float, float]] = Field(..., description="List of (lng, lat) coordinates")
    distance_meters: float = Field(..., gt=0)
    duration_seconds: float = Field(..., gt=0)
    summary: Optional[str] = None
    
    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v):
        if len(v) < 2:
            raise ValueError("Route geometry must contain at least 2 points")
        for coord in v:
            if len(coord) != 2:
                raise ValueError("Each coordinate must be (lng, lat) tuple")
            lng, lat = coord
            if not (-180 <= lng <= 180):
                raise ValueError(f"Invalid longitude: {lng}")
            if not (-90 <= lat <= 90):
                raise ValueError(f"Invalid latitude: {lat}")
        return v


class JourneyStartRequest(BaseModel):
    """Request to start a new journey"""
    origin: LocationPoint
    destination: LocationPoint
    travel_mode: str = Field(..., pattern="^(driving|walking)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "origin": {"lat": 18.5246, "lng": 73.8786},
                "destination": {"lat": 18.9582, "lng": 72.8321},
                "travel_mode": "driving"
            }
        }


class JourneyStartResponse(BaseModel):
    """Response after starting a journey"""
    journey_id: str
    routes: List[Route]
    start_time: datetime
    message: str = "Journey started successfully"
    
    class Config:
        json_schema_extra = {
            "example": {
                "journey_id": "550e8400-e29b-41d4-a716-446655440000",
                "routes": [],
                "start_time": "2026-01-20T12:00:00Z",
                "message": "Journey started successfully"
            }
        }


class DeviationStatus(BaseModel):
    """Current deviation status"""
    spatial: str = Field(..., pattern="^(ON_ROUTE|NEAR_ROUTE|OFF_ROUTE)$")
    temporal: str = Field(..., pattern="^(ON_TIME|DELAYED|SEVERELY_DELAYED|STOPPED)$")
    directional: str = Field(..., pattern="^(TOWARD_DEST|PERPENDICULAR|AWAY)$")
    severity: str = Field(..., pattern="^(normal|minor|moderate|concerning|major)$")


class JourneyState(BaseModel):
    """Current state of an active journey"""
    journey_id: str
    current_status: str
    route_probabilities: Dict[str, float]
    progress_percentage: float = Field(..., ge=0, le=100)
    time_deviation: float = Field(..., description="Time deviation in seconds")
    last_gps: Optional[GPSPoint] = None
    deviation_status: DeviationStatus
    
    class Config:
        json_schema_extra = {
            "example": {
                "journey_id": "550e8400-e29b-41d4-a716-446655440000",
                "current_status": "active",
                "route_probabilities": {"route_0": 0.7, "route_1": 0.2, "route_2": 0.1},
                "progress_percentage": 45.5,
                "time_deviation": 120.0,
                "last_gps": None,
                "deviation_status": {
                    "spatial": "ON_ROUTE",
                    "temporal": "ON_TIME",
                    "directional": "TOWARD_DEST",
                    "severity": "normal"
                }
            }
        }


class GPSPointResponse(BaseModel):
    """Response after submitting a GPS point"""
    status: str
    journey_id: str
    message: str = "GPS point received"
    batch_processed: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "journey_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "GPS point received",
                "batch_processed": False
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid coordinates",
                "detail": "Latitude must be between -90 and 90"
            }
        }


class SafetyLocationUpdateRequest(BaseModel):
    """Incoming location update for safety zone tracking."""

    user_id: str = Field(..., alias="userId", min_length=1, max_length=120)
    tourist_name: Optional[str] = Field(default=None, alias="touristName", max_length=150)
    mobile_number: Optional[str] = Field(default=None, alias="mobileNumber", max_length=30)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime
    safety_score: float = Field(default=0.0, alias="safetyScore", ge=0.0, le=100.0)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "userId": "tourist-123",
                "latitude": 22.5608,
                "longitude": 72.9201,
                "timestamp": "2026-02-08T16:25:00Z",
                "safetyScore": 85.5
            }
        }


class SafetyEvent(BaseModel):
    """Safety event generated from zone transition logic."""

    zone_key: str = Field(..., alias="zoneKey")
    zone_id: str = Field(..., alias="zoneId")
    zone_type: str = Field(..., alias="zoneType")
    zone_name: str = Field(..., alias="zoneName")
    state: str
    threshold_meters: Optional[int] = Field(None, alias="thresholdMeters")
    message: str
    occurred_at: datetime = Field(..., alias="occurredAt")

    class Config:
        populate_by_name = True


class SafetyLocationUpdateResponse(BaseModel):
    """Response for processed safety location update."""

    status: str
    user_id: str = Field(..., alias="userId")
    location_stored_at: datetime = Field(..., alias="locationStoredAt")
    events: List[SafetyEvent] = []

    class Config:
        populate_by_name = True


class LatestUserLocation(BaseModel):
    """Latest known location for a user."""

    user_id: str = Field(..., alias="userId")
    tourist_name: Optional[str] = Field(default=None, alias="touristName")
    mobile_number: Optional[str] = Field(default=None, alias="mobileNumber")
    location: Dict[str, float]
    timestamp: datetime
    active_zone_count: int = Field(0, alias="activeZoneCount")
    safety_score: float = Field(0.0, alias="safetyScore")

    class Config:
        populate_by_name = True


class LatestUserLocationsResponse(BaseModel):
    """Response containing latest known user locations."""

    users: List[LatestUserLocation]
