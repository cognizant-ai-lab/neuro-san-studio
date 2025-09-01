"""Redis-backed caching utilities for Flask endpoints."""
from __future__ import annotations

import hashlib
import json
import os
from functools import wraps
from typing import Callable, Any

from . import extensions


def redis_cache(
    prefix: str, ttl: int = 300, key_func: Callable[..., str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Cache the return value of ``fn`` in Redis using ``prefix``.

    A unique key is constructed from the function arguments or via
    ``key_func`` when provided.  Cached values are stored as JSON.
    ``extensions.cache_stats`` is updated with hit/miss counts.  When Redis
    is unavailable the wrapped function executes normally.

    The cache TTL can be tuned via environment variables.  Set
    ``CACHE_TTL`` for a global default or ``CACHE_TTL_<PREFIX>`` to
    override the TTL for a specific prefix.  For example,
    ``CACHE_TTL_VECTOR_SEARCH=600`` sets a 10 minute TTL for the
    "vector_search" cache.
    """

    env_ttl = int(
        os.getenv(f"CACHE_TTL_{prefix.upper()}", os.getenv("CACHE_TTL", ttl))
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = extensions.redis_client
            stats = extensions.cache_stats
            if client is None:
                return fn(*args, **kwargs)
            key_input = (
                key_func(*args, **kwargs)
                if key_func
                else json.dumps([args, kwargs], sort_keys=True)
            )
            key = f"{prefix}:{hashlib.sha256(key_input.encode()).hexdigest()}"
            cached = client.get(key)
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode("utf-8")
                stats["hits"] += 1
                return json.loads(cached)
            result = fn(*args, **kwargs)
            client.setex(key, env_ttl, json.dumps(result))
            stats["misses"] += 1
            return result

        return wrapper

    return decorator


def invalidate_prefix(prefix: str) -> None:
    """Remove all cached entries beginning with ``prefix``."""
    client = extensions.redis_client
    if client is None:  # pragma: no cover - redis may be absent
        return
    pattern = f"{prefix}:*"
    for key in client.scan_iter(pattern):
        client.delete(key)


__all__ = ["redis_cache", "invalidate_prefix"]
