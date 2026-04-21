"""Per-Census-version facet snapshot cache (24h TTL by default)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import diskcache

from cxg_census_mcp.config import get_settings

CACHE_VERSION = 1


class FacetCache:
    def __init__(self, directory: str, ttl: int) -> None:
        self._cache = diskcache.Cache(directory)
        self._ttl = ttl
        self.hits = 0
        self.misses = 0

    def _key(self, census_version: str, organism: str, facet: str) -> str:
        return f"v{CACHE_VERSION}:{census_version}:{organism}:{facet}"

    def get(self, census_version: str, organism: str, facet: str) -> Any:
        key = self._key(census_version, organism, facet)
        v = self._cache.get(key, default=None)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def set(self, census_version: str, organism: str, facet: str, value: Any) -> None:
        self._cache.set(self._key(census_version, organism, facet), value, expire=self._ttl)

    def clear(self) -> None:
        self._cache.clear()


@lru_cache(maxsize=1)
def get_facet_cache() -> FacetCache:
    s = get_settings()
    return FacetCache(str(s.cache_dir / "facets"), ttl=s.facet_cache_ttl)
