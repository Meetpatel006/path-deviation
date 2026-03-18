"""Storage abstraction for safety tracking state and latest user locations."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.config import settings
from app.services.redis_client import get_redis
from app.utils.logger import logger

SAFETY_PREFIX = "safety"
USERS_SET_KEY = f"{SAFETY_PREFIX}:users:active"


class SafetyStore:
    """Redis-backed store with in-memory fallback."""

    def __init__(self) -> None:
        self._memory_zone_state: Dict[str, Dict[str, Any]] = {}
        self._memory_latest: Dict[str, Dict[str, Any]] = {}

    def _state_key(self, user_id: str) -> str:
        return f"{SAFETY_PREFIX}:user:{user_id}:zone_state"

    def _latest_key(self, user_id: str) -> str:
        return f"{SAFETY_PREFIX}:user:{user_id}:latest"

    def _normalize_user_id(self, value: Any) -> str:
        """Normalize Redis/member values to a plain user ID string."""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.decode("utf-8", errors="ignore")
        return str(value)

    async def get_zone_state(self, user_id: str) -> Dict[str, Any]:
        """Get per-zone state map for a user."""
        redis = await get_redis()
        if redis is None:
            return self._memory_zone_state.get(user_id, {}).copy()

        try:
            raw = await redis.get(self._state_key(user_id))
            if not raw:
                return {}
            return json.loads(raw)
        except Exception as exc:
            logger.error(f"Failed to load safety zone state: {exc}", exc_info=True)
            return self._memory_zone_state.get(user_id, {}).copy()

    async def save_zone_state(self, user_id: str, state: Dict[str, Any]) -> None:
        """Persist per-zone state for a user."""
        redis = await get_redis()
        if redis is None:
            self._memory_zone_state[user_id] = state
            return

        ttl = settings.REDIS_JOURNEY_TTL_SECONDS
        try:
            await redis.set(self._state_key(user_id), json.dumps(state), ex=ttl)
            await redis.sadd(USERS_SET_KEY, user_id)
            await redis.expire(USERS_SET_KEY, ttl)
        except Exception as exc:
            logger.error(f"Failed to persist safety zone state: {exc}", exc_info=True)
            self._memory_zone_state[user_id] = state

    async def save_latest_location(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
        timestamp: datetime,
        active_zone_count: int,
        safety_score: float = 0.0,
    ) -> None:
        """Persist latest known location for a user."""
        payload = {
            "userId": user_id,
            "location": {"lat": latitude, "lng": longitude},
            "timestamp": timestamp.isoformat(),
            "activeZoneCount": int(active_zone_count),
            "safetyScore": float(safety_score),
        }

        redis = await get_redis()
        if redis is None:
            self._memory_latest[user_id] = payload
            return

        ttl = settings.REDIS_JOURNEY_TTL_SECONDS
        try:
            await redis.set(self._latest_key(user_id), json.dumps(payload), ex=ttl)
            await redis.sadd(USERS_SET_KEY, user_id)
            await redis.expire(USERS_SET_KEY, ttl)
        except Exception as exc:
            logger.error(f"Failed to persist latest safety location: {exc}", exc_info=True)
            self._memory_latest[user_id] = payload

    async def get_latest_locations(self, minutes: int, limit: int) -> List[Dict[str, Any]]:
        """Get latest known locations for recently active users."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)
        users: List[Dict[str, Any]] = []

        redis = await get_redis()
        if redis is None:
            for payload in self._memory_latest.values():
                ts = self._parse_dt(payload.get("timestamp"))
                if ts and ts >= cutoff:
                    users.append(payload)
            users.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
            return users[:limit]

        try:
            user_ids_raw = await redis.smembers(USERS_SET_KEY)
            if isinstance(user_ids_raw, set):
                user_ids = list(user_ids_raw)
            else:
                user_ids = list(user_ids_raw or [])
        except Exception as exc:
            logger.error(f"Failed to fetch active safety users: {exc}", exc_info=True)
            for payload in self._memory_latest.values():
                ts = self._parse_dt(payload.get("timestamp"))
                if ts and ts >= cutoff:
                    users.append(payload)
            users.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
            return users[:limit]

        for user_id in user_ids:
            try:
                normalized_user_id = self._normalize_user_id(user_id)
                raw = await redis.get(self._latest_key(normalized_user_id))
                if not raw:
                    continue
                payload = json.loads(raw)
                ts = self._parse_dt(payload.get("timestamp"))
                if ts and ts >= cutoff:
                    users.append(payload)
            except Exception as exc:
                logger.error(f"Failed loading safety latest location: {exc}", exc_info=True)

        users.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        if users:
            return users[:limit]

        # Final fallback when Redis has no entries but in-process memory does.
        for payload in self._memory_latest.values():
            ts = self._parse_dt(payload.get("timestamp"))
            if ts and ts >= cutoff:
                users.append(payload)
        users.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return users[:limit]

    def _parse_dt(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None


safety_store = SafetyStore()

