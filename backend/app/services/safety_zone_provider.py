"""Fetch and normalize safety zones from the remote zone API."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.utils.logger import logger


def _normalize_lat_lng_pair(pair: List[float]) -> Optional[Tuple[float, float]]:
    """Normalize a coordinate pair to (lat, lng)."""
    if not isinstance(pair, list) or len(pair) < 2:
        return None

    first = float(pair[0])
    second = float(pair[1])

    if -90 <= first <= 90 and -180 <= second <= 180:
        return (first, second)
    if -90 <= second <= 90 and -180 <= first <= 180:
        return (second, first)
    return None


class SafetyZoneProvider:
    """Provider with short-lived in-memory cache for zone data."""

    def __init__(self) -> None:
        self._cache: List[Dict[str, Any]] = []
        self._cache_expires_at = datetime.fromtimestamp(0, tz=timezone.utc)
        self._lock = asyncio.Lock()

    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get normalized zones from cache or remote API."""
        now = datetime.now(tz=timezone.utc)
        if self._cache and now < self._cache_expires_at:
            return self._cache

        async with self._lock:
            now = datetime.now(tz=timezone.utc)
            if self._cache and now < self._cache_expires_at:
                return self._cache

            try:
                zones = await self._fetch_and_normalize()
                ttl_seconds = max(30, settings.SAFETY_ZONE_CACHE_TTL_SECONDS)
                self._cache = zones
                self._cache_expires_at = now + timedelta(seconds=ttl_seconds)
                logger.info(f"Safety zones refreshed: {len(zones)} total zone(s)")
                return zones
            except Exception as exc:
                if self._cache:
                    logger.warning(
                        "Using stale safety zone cache due to refresh error: "
                        f"{exc}"
                    )
                    return self._cache
                raise

    async def _fetch_and_normalize(self) -> List[Dict[str, Any]]:
        """Fetch raw zones and normalize for distance/state logic."""
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(settings.SAFETY_ZONES_URL)
            response.raise_for_status()
            payload = response.json()

        zones: List[Dict[str, Any]] = []
        zones.extend(self._normalize_danger_zones(payload.get("dangerZones", [])))
        zones.extend(self._normalize_risk_grids(payload.get("riskGrids", [])))
        zones.extend(self._normalize_geofences(payload.get("geofences", [])))
        return zones

    def _normalize_danger_zones(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            zone_id = str(row.get("id") or row.get("_id") or "")
            if not zone_id:
                continue

            zone_type = "danger_zone"
            shape = str(row.get("type") or "point").lower()
            name = str(row.get("name") or "Danger Zone")
            description = str(
                row.get("category")
                or row.get("raw", {}).get("Description")
                or name
            )

            center: Optional[Tuple[float, float]] = None
            polygon: Optional[List[Tuple[float, float]]] = None
            radius_m = float(row.get("radiusKm") or 0) * 1000

            coords = row.get("coords")
            if shape == "polygon" and isinstance(coords, list) and coords:
                polygon = self._normalize_polygon(coords)
                if polygon:
                    center = polygon[0]
            elif isinstance(coords, list):
                center = _normalize_lat_lng_pair(coords)

            if shape == "point" and radius_m <= 0:
                radius_m = float(settings.SAFETY_DEFAULT_POINT_RADIUS_METERS)

            if not center and not polygon:
                continue

            out.append(
                {
                    "zone_key": f"{zone_type}:{zone_id}",
                    "zone_id": zone_id,
                    "zone_type": zone_type,
                    "shape": shape,
                    "name": name,
                    "title": name,
                    "description": description,
                    "center": center,
                    "radius_m": radius_m,
                    "polygon": polygon,
                    "raw": row,
                }
            )
        return out

    def _normalize_risk_grids(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            zone_id = str(row.get("gridId") or row.get("_id") or "")
            if not zone_id:
                continue

            location = row.get("location") or {}
            coordinates = location.get("coordinates") or []
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                continue

            # Risk grids are GeoJSON in source API: [lng, lat]
            lng = float(coordinates[0])
            lat = float(coordinates[1])
            center = (lat, lng)

            title = str(row.get("gridName") or "Unknown Zone")
            radius_m = float(row.get("radius") or 1000)

            out.append(
                {
                    "zone_key": f"risk_grid:{zone_id}",
                    "zone_id": zone_id,
                    "zone_type": "risk_grid",
                    "shape": "circle",
                    "name": title,
                    "title": title,
                    "description": title,
                    "center": center,
                    "radius_m": radius_m,
                    "polygon": None,
                    "raw": row,
                }
            )
        return out

    def _normalize_geofences(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            zone_id = str(row.get("id") or row.get("_id") or "")
            if not zone_id:
                continue

            shape = str(row.get("type") or "circle").lower()
            name = str(row.get("name") or "Geofence")
            center: Optional[Tuple[float, float]] = None
            polygon: Optional[List[Tuple[float, float]]] = None
            radius_m = float(row.get("radiusKm") or 0) * 1000

            if shape == "polygon":
                polygon_coords = row.get("polygonCoords") or row.get("coords") or []
                polygon = self._normalize_polygon(polygon_coords)
                if polygon:
                    center = polygon[0]
            else:
                center = _normalize_lat_lng_pair(row.get("coords") or [])

            if shape == "point" and radius_m <= 0:
                radius_m = float(settings.SAFETY_DEFAULT_POINT_RADIUS_METERS)

            if not center and not polygon:
                continue

            out.append(
                {
                    "zone_key": f"geofence:{zone_id}",
                    "zone_id": zone_id,
                    "zone_type": "geofence",
                    "shape": shape,
                    "name": name,
                    "title": name,
                    "description": name,
                    "center": center,
                    "radius_m": radius_m,
                    "polygon": polygon,
                    "raw": row,
                }
            )
        return out

    def _normalize_polygon(self, points: List[Any]) -> Optional[List[Tuple[float, float]]]:
        normalized: List[Tuple[float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) < 2:
                continue
            converted = _normalize_lat_lng_pair(point)
            if converted:
                normalized.append(converted)
        if len(normalized) < 3:
            return None
        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])
        return normalized


safety_zone_provider = SafetyZoneProvider()

