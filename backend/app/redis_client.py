"""Redis async client for caching, leaderboards, and lobby state."""

import redis.asyncio as redis

from app.config import settings

# Redis connection pool
# socket_connect_timeout/socket_timeout ZORUNLU: uzak ortamda (Railway) Redis'e
# ulaşılamazsa, zaman aşımı OLMADAN `ping()` SONSUZA KADAR DONAR → uygulama
# lifespan'de takılır, hiç "ready" olmaz, sağlık kontrolü "service unavailable"
# verir. Kısa timeout ile bağlantı HIZLI başarısız olur; lifespan hatayı yutar,
# uygulama Redis olmadan da (degraded) ayağa kalkar ve sağlık kontrolü geçer.
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=False,
)


async def get_redis() -> redis.Redis:
    """Get a Redis client instance from the connection pool."""
    return redis.Redis(connection_pool=redis_pool)


async def close_redis():
    """Close the Redis connection pool."""
    await redis_pool.aclose()


# --- Convenience helpers ---

async def redis_get(key: str) -> str | None:
    """Get a value from Redis."""
    client = await get_redis()
    return await client.get(key)


async def redis_set(key: str, value: str, ex: int | None = None) -> None:
    """Set a value in Redis with optional expiration (seconds)."""
    client = await get_redis()
    await client.set(key, value, ex=ex)


async def redis_delete(key: str) -> None:
    """Delete a key from Redis."""
    client = await get_redis()
    await client.delete(key)
