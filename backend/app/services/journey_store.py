"""
Redis-backed journey state storage using Upstash REST
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.redis_client import get_redis
from app.utils.logger import logger


JOURNEY_PREFIX = "journey:"
JOURNEY_TTL_SECONDS = 86400  # 24 hours


class JourneyStore:
    """
    Redis-backed journey state storage
    """
    
    async def save_journey_state(self, journey_id: str, state: Dict[str, Any]) -> None:
        """
        Save journey tracking state to Redis
        
        Args:
            journey_id: Journey UUID
            state: Tracking state dictionary
        """
        redis = await get_redis()
        if redis is None:
            return
        
        key = f"{JOURNEY_PREFIX}{journey_id}"
        serializable_state = self._serialize_state(state)
        
        try:
            await redis.set(key, json.dumps(serializable_state), ex=JOURNEY_TTL_SECONDS)
            logger.debug(f"Saved journey state to Redis: {journey_id}")
        except Exception as e:
            logger.error(f"Failed to save journey state to Redis: {e}", exc_info=True)
    
    async def get_journey_state(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """
        Get journey tracking state from Redis
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            Journey state dict or None
        """
        redis = await get_redis()
        if redis is None:
            return None
        
        key = f"{JOURNEY_PREFIX}{journey_id}"
        try:
            data = await redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get journey state from Redis: {e}", exc_info=True)
        
        return None
    
    async def delete_journey_state(self, journey_id: str) -> None:
        """
        Delete journey state from Redis
        
        Args:
            journey_id: Journey UUID
        """
        redis = await get_redis()
        if redis is None:
            return
        
        key = f"{JOURNEY_PREFIX}{journey_id}"
        try:
            await redis.delete(key)
            logger.debug(f"Deleted journey state from Redis: {journey_id}")
        except Exception as e:
            logger.error(f"Failed to delete journey state from Redis: {e}", exc_info=True)
    
    async def journey_exists(self, journey_id: str) -> bool:
        """
        Check if journey exists in Redis
        
        Args:
            journey_id: Journey UUID
        
        Returns:
            True if journey exists, else False
        """
        redis = await get_redis()
        if redis is None:
            return False
        
        key = f"{JOURNEY_PREFIX}{journey_id}"
        try:
            return bool(await redis.exists(key))
        except Exception as e:
            logger.error(f"Failed to check journey existence in Redis: {e}", exc_info=True)
            return False
    
    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize journey tracking state to JSON-friendly dict
        
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


journey_store = JourneyStore()
