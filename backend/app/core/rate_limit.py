from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Counters live in Redis (not process memory), so limits stay correct
# across restarts and across multiple API instances.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["100/minute"],  # applies to every route unless overridden
    enabled=settings.rate_limit_enabled,
)