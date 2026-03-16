"""Safety zone event engine: approaching, entering, staying, leaving."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.services.safety_store import safety_store
from app.services.safety_zone_provider import safety_zone_provider
from app.utils.geometry import haversine_distance, point_to_segment_distance

APPROACH_THRESHOLDS_METERS = [1000, 500, 100]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Ray casting point-in-polygon test in lat/lng space."""
    lat, lng = point
    inside = False
    for idx in range(len(polygon) - 1):
        lat1, lng1 = polygon[idx]
        lat2, lng2 = polygon[idx + 1]
        crosses = (lng1 > lng) != (lng2 > lng)
        if not crosses:
            continue
        try:
            lat_at_lng = ((lat2 - lat1) * (lng - lng1) / (lng2 - lng1)) + lat1
        except ZeroDivisionError:
            continue
        if lat < lat_at_lng:
            inside = not inside
    return inside


def _polygon_boundary_distance_meters(
    point: Tuple[float, float], polygon: List[Tuple[float, float]]
) -> float:
    min_distance = float("inf")
    for idx in range(len(polygon) - 1):
        _, distance = point_to_segment_distance(point, polygon[idx], polygon[idx + 1])
        if distance < min_distance:
            min_distance = distance
    return 0.0 if min_distance == float("inf") else min_distance


def _distance_to_zone_boundary(
    latitude: float, longitude: float, zone: Dict[str, Any]
) -> Tuple[float, bool]:
    """Return (distance_to_boundary_m, is_inside)."""
    point = (latitude, longitude)
    shape = zone.get("shape")
    center = zone.get("center")
    radius_m = float(zone.get("radius_m") or 0)
    polygon = zone.get("polygon")

    if shape == "polygon" and polygon:
        inside = _point_in_polygon(point, polygon)
        distance = _polygon_boundary_distance_meters(point, polygon)
        return distance, inside

    if center:
        distance_to_center = haversine_distance(point, center)
        effective_radius = max(0.0, radius_m)
        inside = distance_to_center <= effective_radius
        boundary_distance = max(0.0, distance_to_center - effective_radius)
        return boundary_distance, inside

    # Fallback for malformed zone
    return float("inf"), False


def _approach_threshold(distance_to_boundary_m: float) -> Optional[int]:
    for threshold in sorted(APPROACH_THRESHOLDS_METERS):
        if distance_to_boundary_m <= threshold:
            return threshold
    return None


def _notification_allowed(
    zone_state: Dict[str, Any],
    notification_key: str,
    now: datetime,
) -> bool:
    cooldown = timedelta(hours=max(1, settings.SAFETY_NOTIFICATION_COOLDOWN_HOURS))
    registry = zone_state.get("lastNotifications") or {}
    last_raw = registry.get(notification_key)
    if not isinstance(last_raw, str):
        return True
    try:
        last_dt = _as_utc(datetime.fromisoformat(last_raw.replace("Z", "+00:00")))
    except Exception:
        return True
    return (now - last_dt) >= cooldown


def _mark_notification(zone_state: Dict[str, Any], notification_key: str, now: datetime) -> None:
    registry = zone_state.get("lastNotifications") or {}
    registry[notification_key] = now.isoformat()
    zone_state["lastNotifications"] = registry


def _message_for(zone: Dict[str, Any], event_state: str) -> str:
    zone_type = zone.get("zone_type")
    name = zone.get("name") or "Unknown Zone"
    title = zone.get("title") or name
    description = zone.get("description") or name

    if zone_type == "geofence":
        if event_state == "approaching":
            return f"You are going towards {name} that created by your guide."
        if event_state == "entering":
            return f"You are entering zone {name} created by your guide."
        if event_state == "staying":
            return f"You are currently within the zone {name} created by your guide. Stay aware of your surroundings."
        return f"You are leaving zone {name}."

    if zone_type == "risk_grid":
        if event_state == "approaching":
            return f"You are near an incident region and {title}."
        if event_state == "entering":
            return f"You are entering an incident region and {title}. Please stay alert."
        if event_state == "staying":
            return f"You are still within an incident region and {title}. Remain vigilant."
        return f"You are leaving the incident region {title}. Continue to stay alert."

    # danger_zone
    if event_state == "approaching":
        return f"You are approaching a danger zone: {description}."
    if event_state == "entering":
        return f"You are entering a danger zone: {description}. Please be cautious."
    if event_state == "staying":
        return f"You are still within a danger zone: {description}. Leave as soon as possible."
    return f"You are leaving the danger zone: {description}. Stay cautious."


class SafetyZoneEngine:
    """Main processor for location updates and zone event generation."""

    async def process_location_update(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
        timestamp: datetime,
    ) -> List[Dict[str, Any]]:
        now = _as_utc(timestamp)
        zones = await safety_zone_provider.get_zones()
        state_map = await safety_store.get_zone_state(user_id)
        events: List[Dict[str, Any]] = []

        staying_window = timedelta(minutes=max(1, settings.SAFETY_STAYING_MINUTES))

        for zone in zones:
            zone_key = zone["zone_key"]
            zone_state = state_map.get(zone_key) or {
                "inside": False,
                "enteredAt": None,
                "lastSeenAt": None,
                "lastApproachThreshold": None,
                "lastNotifications": {},
            }

            distance_m, is_inside = _distance_to_zone_boundary(latitude, longitude, zone)
            was_inside = bool(zone_state.get("inside"))

            # Entering
            if not was_inside and is_inside:
                notify_key = "entering"
                if _notification_allowed(zone_state, notify_key, now):
                    events.append(
                        self._make_event(zone, "entering", now, threshold_meters=None)
                    )
                    _mark_notification(zone_state, notify_key, now)
                zone_state["enteredAt"] = now.isoformat()
                zone_state["lastApproachThreshold"] = None

            # Leaving
            elif was_inside and not is_inside:
                notify_key = "leaving"
                if _notification_allowed(zone_state, notify_key, now):
                    events.append(
                        self._make_event(zone, "leaving", now, threshold_meters=None)
                    )
                    _mark_notification(zone_state, notify_key, now)
                zone_state["enteredAt"] = None
                zone_state["lastApproachThreshold"] = None

            # Staying
            elif is_inside:
                entered_at_raw = zone_state.get("enteredAt")
                entered_at = None
                if isinstance(entered_at_raw, str):
                    try:
                        entered_at = _as_utc(
                            datetime.fromisoformat(entered_at_raw.replace("Z", "+00:00"))
                        )
                    except Exception:
                        entered_at = None
                if entered_at is None:
                    entered_at = now
                    zone_state["enteredAt"] = entered_at.isoformat()

                if (now - entered_at) >= staying_window:
                    notify_key = "staying"
                    if _notification_allowed(zone_state, notify_key, now):
                        events.append(
                            self._make_event(zone, "staying", now, threshold_meters=None)
                        )
                        _mark_notification(zone_state, notify_key, now)

                zone_state["lastApproachThreshold"] = None

            # Approaching (outside only)
            else:
                threshold = _approach_threshold(distance_m)
                last_threshold = zone_state.get("lastApproachThreshold")
                closer_than_last = (
                    threshold is not None
                    and (
                        last_threshold is None
                        or int(threshold) < int(last_threshold)
                    )
                )

                if threshold is None:
                    zone_state["lastApproachThreshold"] = None
                elif closer_than_last:
                    notify_key = f"approaching:{threshold}"
                    if _notification_allowed(zone_state, notify_key, now):
                        events.append(
                            self._make_event(zone, "approaching", now, threshold_meters=threshold)
                        )
                        _mark_notification(zone_state, notify_key, now)
                    zone_state["lastApproachThreshold"] = int(threshold)

            zone_state["inside"] = bool(is_inside)
            zone_state["lastSeenAt"] = now.isoformat()
            state_map[zone_key] = zone_state

        active_zone_count = sum(1 for row in state_map.values() if row.get("inside"))
        await safety_store.save_zone_state(user_id, state_map)
        await safety_store.save_latest_location(
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=now,
            active_zone_count=active_zone_count,
        )
        return events

    def _make_event(
        self,
        zone: Dict[str, Any],
        state: str,
        now: datetime,
        threshold_meters: Optional[int],
    ) -> Dict[str, Any]:
        return {
            "zoneKey": zone["zone_key"],
            "zoneId": zone["zone_id"],
            "zoneType": zone["zone_type"],
            "zoneName": zone.get("name") or "Unknown Zone",
            "state": state,
            "thresholdMeters": threshold_meters,
            "message": _message_for(zone, state),
            "occurredAt": now,
        }


safety_zone_engine = SafetyZoneEngine()

