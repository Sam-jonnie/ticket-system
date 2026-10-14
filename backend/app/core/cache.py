import json
from typing import Any

import redis

from app.core.config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def cache_get(key: str) -> Any | None:
    """Returns the cached value, or None on a miss OR if Redis is unreachable."""
    try:
        raw = redis_client.get(key)
        return json.loads(raw) if raw is not None else None
    except redis.RedisError:
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(value))
    except redis.RedisError:
        pass  # caching is an optimization; never fail a request because of it