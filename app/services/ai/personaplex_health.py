"""PersonaPlex health check with TTL-based caching.

Avoids hammering the PersonaPlex server on every WebSocket connection.
Result is cached for ``settings.personaplex_health_cache_ttl`` seconds.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_health_cache: dict[str, tuple[bool, float]] = {}


async def check_personaplex_health(*, force: bool = False) -> bool:
    """Check whether the PersonaPlex server is reachable and healthy.

    Args:
        force: Bypass the TTL cache and query the server directly.

    Returns:
        ``True`` if the server responded with 200 within the timeout.
    """
    if not settings.personaplex_enabled:
        return False

    cache_key = f"{settings.personaplex_host}:{settings.personaplex_port}"
    now = time.monotonic()

    if not force and cache_key in _health_cache:
        ok, checked_at = _health_cache[cache_key]
        if now - checked_at < settings.personaplex_health_cache_ttl:
            return ok

    url = f"http://{settings.personaplex_host}:{settings.personaplex_port}/health"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(url)
            healthy = resp.status_code == 200
    except Exception as exc:
        logger.warning(f"PersonaPlex health check failed: {exc}")
        healthy = False

    _health_cache[cache_key] = (healthy, now)
    if healthy:
        logger.debug("PersonaPlex health check: OK")
    else:
        logger.warning("PersonaPlex health check: UNHEALTHY")
    return healthy


def invalidate_health_cache() -> None:
    """Force the next health check to query the server."""
    _health_cache.clear()
