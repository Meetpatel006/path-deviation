"""Upstash Redis REST client wrapper.

This module now reads configuration from `app.config.settings` so values
from the project's `.env` (loaded via Pydantic `BaseSettings`) are available
without requiring environment variables to be set in the OS.
"""
from typing import Optional

from upstash_redis.asyncio import Redis

from app.utils.logger import logger
from app.config import settings


_redis_client: Optional[Redis] = None


async def get_redis() -> Optional[Redis]:
    """Get or initialize the Upstash Redis client.

    Returns:
        Redis client instance or None if not configured
    """
    global _redis_client
    url = settings.UPSTASH_REDIS_REST_URL
    token = settings.UPSTASH_REDIS_REST_TOKEN

    if not url or not token:
        logger.warning("Upstash Redis not configured (missing UPSTASH_REDIS_REST_URL/TOKEN)")
        return None

    if _redis_client is None:
        _redis_client = Redis(url=url, token=token)
        logger.info("Connected to Upstash Redis")

    return _redis_client


async def close_redis() -> None:
    """Close the Upstash Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Upstash Redis connection closed")
