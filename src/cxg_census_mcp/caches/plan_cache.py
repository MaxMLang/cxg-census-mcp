"""Disk cache of plan JSON by ``call_id`` (TTL from settings)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import diskcache

from cxg_census_mcp.config import get_settings

CACHE_VERSION = 1


class PlanCache:
    def __init__(self, directory: str, ttl: int) -> None:
        self._cache = diskcache.Cache(directory)
        self._ttl = ttl
        self.hits = 0
        self.misses = 0

    def _key(self, call_id: str) -> str:
        return f"v{CACHE_VERSION}:{call_id}"

    def get(self, call_id: str) -> Any:
        v = self._cache.get(self._key(call_id), default=None)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def set(self, call_id: str, plan_json: dict[str, Any]) -> None:
        self._cache.set(self._key(call_id), plan_json, expire=self._ttl)

    def clear(self) -> None:
        self._cache.clear()


@lru_cache(maxsize=1)
def get_plan_cache() -> PlanCache:
    s = get_settings()
    return PlanCache(str(s.cache_dir / "plans"), ttl=s.plan_cache_ttl)
