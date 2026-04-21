"""Per-Census-version facet snapshot cache (24h TTL by default)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cxg_census_mcp.caches._sqlite_kv import SqliteKV
from cxg_census_mcp.config import get_settings

# v2 = sqlite+json backend (was diskcache+pickle in v1).
CACHE_VERSION = 2


class FacetCache:
    def __init__(self, directory: str, ttl: int) -> None:
        self._cache = SqliteKV(directory, default_ttl=ttl)
        self._ttl = ttl
        self.hits = 0
        self.misses = 0

    def _key(self, census_version: str, organism: str, facet: str) -> str:
        return f"v{CACHE_VERSION}:{census_version}:{organism}:{facet}"

    def get(self, census_version: str, organism: str, facet: str) -> Any:
        key = self._key(census_version, organism, facet)
        v = self._cache.get(key)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def set(self, census_version: str, organism: str, facet: str, value: Any) -> None:
        self._cache.set(self._key(census_version, organism, facet), value, ttl=self._ttl)

    def clear(self) -> None:
        self._cache.clear()


@lru_cache(maxsize=1)
def get_facet_cache() -> FacetCache:
    s = get_settings()
    return FacetCache(str(s.cache_dir / "facets"), ttl=s.facet_cache_ttl)
