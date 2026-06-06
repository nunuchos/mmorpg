from collections.abc import AsyncGenerator
import redis.asyncio as aioredis
from redis.asyncio import Redis
from app.core.config import settings

_pool: Redis | None = None

def get_redis_pool() -> Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,  # returns str, not bytes
            max_connections=50,
        )
    return _pool

async def get_redis() -> AsyncGenerator[Redis, None]:
    yield get_redis_pool()

async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None