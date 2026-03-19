"""
Rate limiter singleton for the CompanyScope API.

Uses slowapi (a FastAPI-compatible wrapper around the `limits` library).

Storage strategy:
  - Production:   Redis (settings.redis_url) — shared across all API instances,
                  so limits are enforced cluster-wide.
  - Development:  In-process memory — no Redis dependency for local runs;
                  counts reset on each server restart.

Import this module's `limiter` in:
  - app.main      — to attach it to app.state and register the 429 handler
  - app.routers.* — to apply @limiter.limit() decorators
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Use Redis in production (shared across instances);
# fall back to in-process memory in development so local runs and tests
# don't require a Redis connection just for rate limiting.
_storage_uri = settings.redis_url if settings.is_production else "memory://"

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
