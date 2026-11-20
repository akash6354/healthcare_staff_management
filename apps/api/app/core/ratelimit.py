"""Fixed-window rate limits in Redis (auth, OTP, public QR, uploads, exports)."""

from functools import lru_cache

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.errors import AppError


@lru_cache
def redis_client() -> "redis.Redis":
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        get_settings().redis_url, decode_responses=True
    )
    return client


async def hit(bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """Count one hit; raise 429 when `limit` is exceeded inside the window."""
    name = f"rl:{bucket}:{key}"
    client = redis_client()
    async with client.pipeline(transaction=True) as pipe:
        pipe.incr(name)
        pipe.expire(name, window_seconds, nx=True)
        count, _ = await pipe.execute()
    if int(count) > limit:
        ttl = await client.ttl(name)
        raise AppError("RATE_LIMITED", 429, retry_after_seconds=max(int(ttl), 1))
