"""Cliente asíncrono de Redis para el Auth Service."""

import redis.asyncio as redis

from .config import settings

pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    """Devuelve un cliente Redis asíncrono respaldado por el pool compartido."""
    return redis.Redis(connection_pool=pool)
