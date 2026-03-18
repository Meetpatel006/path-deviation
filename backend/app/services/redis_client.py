"""Redis client wrapper supporting redis-py and Upstash REST."""
from typing import Optional, Union
import time

from redis.asyncio import Redis as RedisPy
from upstash_redis.asyncio import Redis as UpstashRedis

from app.utils.logger import logger
from app.config import settings


_redis_client: Optional[Union[RedisPy, UpstashRedis]] = None
_redis_disabled_until: float = 0.0


def _redis_in_cooldown() -> bool:
    return time.monotonic() < _redis_disabled_until


async def mark_redis_unavailable(reason: str, cooldown_seconds: int = 120) -> None:
    """Temporarily disable Redis usage after connectivity errors."""
    global _redis_disabled_until
    _redis_disabled_until = time.monotonic() + max(5, cooldown_seconds)
    logger.warning(
        "Redis temporarily disabled for %ss due to: %s",
        cooldown_seconds,
        reason,
    )
    await close_redis()


async def get_redis() -> Optional[Union[RedisPy, UpstashRedis]]:
    """Get or initialize the Redis client.

    Returns:
        Redis client instance or None if not configured
    """
    global _redis_client
    redis_url = settings.REDIS_URL
    upstash_url = settings.UPSTASH_REDIS_REST_URL
    upstash_token = settings.UPSTASH_REDIS_REST_TOKEN

    if _redis_in_cooldown():
        return None

    if not redis_url and not upstash_url:
        logger.warning("Redis not configured (missing REDIS_URL or UPSTASH_REDIS_REST_URL)")
        return None

    if _redis_client is None:
        if redis_url:
            _redis_client = RedisPy.from_url(redis_url, decode_responses=True)
            logger.info("Connected to Redis (redis-py)")
        else:
            if not upstash_token:
                logger.warning("Upstash Redis not configured (missing UPSTASH_REDIS_REST_TOKEN)")
                return None
            if not isinstance(upstash_url, str) or not upstash_url.startswith(("http://", "https://")):
                logger.warning("Invalid UPSTASH_REDIS_REST_URL; expected http(s) URL")
                return None
            _redis_client = UpstashRedis(url=upstash_url, token=upstash_token)
            logger.info("Connected to Upstash Redis (REST)")

    return _redis_client


async def close_redis() -> None:
    """Close the Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")
