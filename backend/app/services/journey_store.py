"""Redis-backed journey data storage."""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List

from redis.asyncio import Redis as RedisPy
from upstash_redis.asyncio import Redis as UpstashRedis

from app.config import settings
from app.models.schemas import Route, GPSPoint, LocationPoint
from app.services.redis_client import get_redis
from app.utils.logger import logger


JOURNEY_PREFIX = "journey"


class JourneyStore:
    """
    Redis-backed journey data storage
    """

    async def create_journey(
        self,
        origin: LocationPoint,
        destination: LocationPoint,
        travel_mode: str,
        routes: List[Route]
    ) -> str:
        """
        Create a new journey and store metadata/routes in Redis.

        Args:
            origin: Starting location
            destination: Ending location
            travel_mode: 'driving' or 'walking'
            routes: List of route alternatives

        Returns:
            journey_id (UUID string)
        """
        journey_id = str(uuid.uuid4())
        start_time = datetime.now()

        meta = {
            "id": journey_id,
            "origin": {"lat": origin.lat, "lng": origin.lng},
            "destination": {"lat": destination.lat, "lng": destination.lng},
            "travel_mode": travel_mode,
            "start_time": start_time.isoformat(),
            "status": "active"
        }

        await self._save_journey_meta(journey_id, meta)
        await self._save_routes(journey_id, routes)

        logger.info(
            f"Created journey {journey_id} with {len(routes)} routes "
            f"({travel_mode} mode)"
        )

        return journey_id

    async def save_journey_state(self, journey_id: str, state: Dict[str, Any]) -> None:
        """
        Save journey tracking state to Redis.

        Args:
            journey_id: Journey UUID
            state: Tracking state dictionary
        """
        redis = await get_redis()
        if redis is None:
            return

        key = self._journey_state_key(journey_id)
        serializable_state = self._serialize_state(state)

        try:
            await redis.set(key, json.dumps(serializable_state), ex=settings.REDIS_JOURNEY_TTL_SECONDS)
            logger.debug(f"Saved journey state to Redis: {journey_id}")
        except Exception as e:
            logger.error(f"Failed to save journey state to Redis: {e}", exc_info=True)

    async def get_journey_state(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """
        Get journey tracking state from Redis.

        Args:
            journey_id: Journey UUID

        Returns:
            Journey state dict or None
        """
        redis = await get_redis()
        if redis is None:
            return None

        key = self._journey_state_key(journey_id)
        try:
            data = await redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get journey state from Redis: {e}", exc_info=True)

        return None

    async def delete_journey_state(self, journey_id: str) -> None:
        """
        Delete journey state from Redis.

        Args:
            journey_id: Journey UUID
        """
        redis = await get_redis()
        if redis is None:
            return

        key = self._journey_state_key(journey_id)
        try:
            await redis.delete(key)
            logger.debug(f"Deleted journey state to Redis: {journey_id}")
        except Exception as e:
            logger.error(f"Failed to delete journey state to Redis: {e}", exc_info=True)

    async def journey_exists(self, journey_id: str) -> bool:
        """
        Check if journey exists in Redis.

        Args:
            journey_id: Journey UUID

        Returns:
            True if journey exists, else False
        """
        redis = await get_redis()
        if redis is None:
            return False

        key = self._journey_meta_key(journey_id)
        try:
            return bool(await redis.exists(key))
        except Exception as e:
            logger.error(f"Failed to check journey existence in Redis: {e}", exc_info=True)
            return False

    async def get_journey_meta(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """
        Get journey metadata from Redis.

        Args:
            journey_id: Journey UUID

        Returns:
            Metadata dict or None
        """
        redis = await get_redis()
        if redis is None:
            return None

        key = self._journey_meta_key(journey_id)
        try:
            data = await redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get journey meta from Redis: {e}", exc_info=True)
            return None

    async def update_journey_status(
        self,
        journey_id: str,
        status: str,
        end_time: Optional[datetime] = None
    ) -> None:
        """
        Update journey status in Redis.

        Args:
            journey_id: Journey UUID
            status: New status ('active', 'completed', 'abandoned')
            end_time: Optional end time
        """
        redis = await get_redis()
        if redis is None:
            return

        key = self._journey_meta_key(journey_id)
        try:
            meta_raw = await redis.get(key)
            if not meta_raw:
                return
            meta = json.loads(meta_raw)
            meta["status"] = status
            if end_time is not None:
                meta["end_time"] = end_time.isoformat()
            await redis.set(key, json.dumps(meta), ex=settings.REDIS_JOURNEY_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Failed to update journey status in Redis: {e}", exc_info=True)

    async def get_routes(self, journey_id: str) -> List[Route]:
        """
        Get all routes for a journey from Redis.

        Args:
            journey_id: Journey UUID

        Returns:
            List of Route objects
        """
        redis = await get_redis()
        if redis is None:
            return []

        key = self._journey_routes_key(journey_id)
        try:
            data = await redis.get(key)
            if not data:
                return []
            routes_data = json.loads(data)
            routes = []
            for route_data in routes_data:
                routes.append(Route(**route_data))
            return routes
        except Exception as e:
            logger.error(f"Failed to get routes from Redis: {e}", exc_info=True)
            return []

    async def add_gps_point(self, journey_id: str, gps_point: GPSPoint) -> None:
        """
        Store GPS point in Redis list and geo index.

        Args:
            journey_id: Journey UUID
            gps_point: GPS point data
        """
        redis = await get_redis()
        if redis is None:
            return

        list_key = self._journey_gps_list_key(journey_id)
        geo_key = self._journey_geo_key(journey_id)
        seq_key = self._journey_gps_seq_key(journey_id)
        hash_key = self._journey_gps_hash_key(journey_id)

        try:
            seq = await redis.incr(seq_key)
            member = str(seq)
            point_dict = gps_point.model_dump() if hasattr(gps_point, "model_dump") else gps_point.dict()
            point_dict["timestamp"] = gps_point.timestamp.isoformat()
            point_json = json.dumps(point_dict)

            if isinstance(redis, RedisPy):
                pipe = redis.pipeline()
                pipe.geoadd(geo_key, {member: (gps_point.lng, gps_point.lat)})
                pipe.hset(hash_key, member, point_json)
                pipe.lpush(list_key, point_json)
                pipe.ltrim(list_key, 0, settings.REDIS_GPS_LIST_LIMIT - 1)
                pipe.expire(geo_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                pipe.expire(hash_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                pipe.expire(list_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                pipe.expire(seq_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                await pipe.execute()
            else:
                await redis.geoadd(geo_key, [gps_point.lng, gps_point.lat, member])
                await redis.hset(hash_key, member, point_json)
                await redis.lpush(list_key, point_json)
                await redis.ltrim(list_key, 0, settings.REDIS_GPS_LIST_LIMIT - 1)
                await redis.expire(geo_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                await redis.expire(hash_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                await redis.expire(list_key, settings.REDIS_JOURNEY_TTL_SECONDS)
                await redis.expire(seq_key, settings.REDIS_JOURNEY_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Failed to store GPS point in Redis: {e}", exc_info=True)

    async def get_recent_gps_points(self, journey_id: str, limit: int = 10) -> List[GPSPoint]:
        """
        Get most recent GPS points for a journey.

        Args:
            journey_id: Journey UUID
            limit: Maximum number of points to return

        Returns:
            List of GPSPoint objects
        """
        redis = await get_redis()
        if redis is None:
            return []

        list_key = self._journey_gps_list_key(journey_id)
        try:
            items = await redis.lrange(list_key, 0, max(0, limit - 1))
            gps_points: List[GPSPoint] = []
            for item in reversed(items):
                data = json.loads(item)
                gps_points.append(
                    GPSPoint(
                        lat=data["lat"],
                        lng=data["lng"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        speed=data.get("speed"),
                        bearing=data.get("bearing"),
                        accuracy=data.get("accuracy")
                    )
                )
            return gps_points
        except Exception as e:
            logger.error(f"Failed to get GPS points from Redis: {e}", exc_info=True)
            return []

    async def add_deviation_event(self, journey_id: str, event: Dict[str, Any]) -> None:
        """
        Store deviation event in Redis list.

        Args:
            journey_id: Journey UUID
            event: Deviation event data
        """
        redis = await get_redis()
        if redis is None:
            return

        key = self._journey_deviation_key(journey_id)
        try:
            payload = json.dumps(event)
            if isinstance(redis, RedisPy):
                pipe = redis.pipeline()
                pipe.lpush(key, payload)
                pipe.ltrim(key, 0, settings.REDIS_DEVIATION_LIST_LIMIT - 1)
                pipe.expire(key, settings.REDIS_JOURNEY_TTL_SECONDS)
                await pipe.execute()
            else:
                await redis.lpush(key, payload)
                await redis.ltrim(key, 0, settings.REDIS_DEVIATION_LIST_LIMIT - 1)
                await redis.expire(key, settings.REDIS_JOURNEY_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Failed to store deviation event in Redis: {e}", exc_info=True)

    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize journey tracking state to JSON-friendly dict.

        Args:
            state: Tracking state dict

        Returns:
            Serializable dict
        """
        last_deviation = state.get("last_deviation")
        serialized_last_deviation = None
        if last_deviation:
            serialized_last_deviation = {
                "spatial": last_deviation.get("spatial"),
                "temporal": last_deviation.get("temporal"),
                "directional": last_deviation.get("directional"),
                "severity": last_deviation.get("severity"),
                "timestamp": (
                    last_deviation.get("timestamp").isoformat()
                    if isinstance(last_deviation.get("timestamp"), datetime)
                    else last_deviation.get("timestamp")
                )
            }

        routes = []
        for route in state.get("routes", []):
            if hasattr(route, "model_dump"):
                routes.append(route.model_dump())
            else:
                routes.append(route.dict())

        return {
            "routes": routes,
            "travel_mode": state.get("travel_mode"),
            "origin": state.get("origin"),
            "destination": state.get("destination"),
            "start_time": state.get("start_time").isoformat() if state.get("start_time") else None,
            "total_points_received": state.get("total_points_received", 0),
            "batches_processed": state.get("batches_processed", 0),
            "last_deviation": serialized_last_deviation
        }

    async def _save_journey_meta(self, journey_id: str, meta: Dict[str, Any]) -> None:
        redis = await get_redis()
        if redis is None:
            return
        key = self._journey_meta_key(journey_id)
        try:
            await redis.set(key, json.dumps(meta), ex=settings.REDIS_JOURNEY_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Failed to save journey meta to Redis: {e}", exc_info=True)

    async def _save_routes(self, journey_id: str, routes: List[Route]) -> None:
        redis = await get_redis()
        if redis is None:
            return
        key = self._journey_routes_key(journey_id)
        try:
            routes_payload = []
            for route in routes:
                if hasattr(route, "model_dump"):
                    routes_payload.append(route.model_dump())
                else:
                    routes_payload.append(route.dict())
            await redis.set(key, json.dumps(routes_payload), ex=settings.REDIS_JOURNEY_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Failed to save routes to Redis: {e}", exc_info=True)

    def _journey_state_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:state"

    def _journey_meta_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:meta"

    def _journey_routes_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:routes"

    def _journey_gps_list_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:gps"

    def _journey_gps_hash_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:gps:hash"

    def _journey_gps_seq_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:gps:seq"

    def _journey_geo_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:geo"

    def _journey_deviation_key(self, journey_id: str) -> str:
        return f"{JOURNEY_PREFIX}:{journey_id}:deviations"


journey_store = JourneyStore()
