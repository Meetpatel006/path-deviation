"""API endpoints for safety zone tracking."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.models.schemas import (
    LatestUserLocation,
    LatestUserLocationsResponse,
    SafetyEvent,
    SafetyLocationUpdateRequest,
    SafetyLocationUpdateResponse,
)
from app.services.safety_store import safety_store
from app.services.safety_zone_engine import safety_zone_engine
from app.utils.logger import logger

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.post(
    "/location",
    response_model=SafetyLocationUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def process_location_update(
    payload: SafetyLocationUpdateRequest,
) -> SafetyLocationUpdateResponse:
    """
    Process latest user location and compute zone events.
    """
    try:
        timestamp = payload.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        events_raw = await safety_zone_engine.process_location_update(
            user_id=payload.user_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            timestamp=timestamp,
        )

        # Save latest location with safety score
        await safety_store.save_latest_location(
            user_id=payload.user_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            timestamp=timestamp,
            active_zone_count=len(events_raw),
            safety_score=payload.safety_score,
            tourist_name=payload.tourist_name,
            mobile_number=payload.mobile_number,
            role=payload.role,
            group_id=payload.group_id,
            emergency_contact=payload.emergency_contact,
            day_wise_itinerary=payload.day_wise_itinerary,
        )

        events = [SafetyEvent(**row) for row in events_raw]
        return SafetyLocationUpdateResponse(
            status="success",
            userId=payload.user_id,
            locationStoredAt=datetime.now(tz=timezone.utc),
            events=events,
        )
    except Exception as exc:
        logger.error(f"Failed processing safety location update: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process safety location update",
        )


@router.get(
    "/users/latest",
    response_model=LatestUserLocationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_latest_user_locations(
    minutes: int = Query(default=120, ge=1, le=24 * 60),
    limit: int = Query(default=500, ge=1, le=settings.SAFETY_USERS_MAX_RESULTS),
) -> LatestUserLocationsResponse:
    """
    Fetch latest known locations for recently active users.
    """
    try:
        rows = await safety_store.get_latest_locations(minutes=minutes, limit=limit)
        users: List[LatestUserLocation] = [LatestUserLocation(**row) for row in rows]
        return LatestUserLocationsResponse(users=users)
    except Exception as exc:
        logger.error(f"Failed fetching latest safety user locations: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch latest user locations",
        )

