"""Disk cache of OLS JSON responses + hit/miss counters."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import diskcache

from cxg_census_mcp.config import get_settings
from cxg_census_mcp.utils.stable_hash import stable_hash

CACHE_VERSION = 1
# Sentinel string survives pickle/unpickle in diskcache; identity sentinels do not.
_NEG_TOKEN = "__census_mcp_ols_negative__"


class OLSCache:
    def __init__(self, directory: str, ttl: int) -> None:
        self._cache = diskcache.Cache(directory)
        self._ttl = ttl
        self.hits = 0
        self.misses = 0

    def _key(self, ontology: str | None, op: str, args: dict[str, Any]) -> str:
        return f"v{CACHE_VERSION}:{ontology or '_'}:{op}:{stable_hash(args)}"

    def get(self, ontology: str | None, op: str, args: dict[str, Any]) -> Any:
        key = self._key(ontology, op, args)
        value = self._cache.get(key, default=None)
        if value is None or value == _NEG_TOKEN:
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, ontology: str | None, op: str, args: dict[str, Any], value: Any) -> None:
        key = self._key(ontology, op, args)
        self._cache.set(key, value, expire=self._ttl)

    def set_negative(
        self, ontology: str | None, op: str, args: dict[str, Any], ttl: int = 300
    ) -> None:
        """Cache misses briefly to debounce hot retries."""
        key = self._key(ontology, op, args)
        self._cache.set(key, _NEG_TOKEN, expire=ttl)

    def is_negative(self, ontology: str | None, op: str, args: dict[str, Any]) -> bool:
        key = self._key(ontology, op, args)
        return self._cache.get(key, default=None) == _NEG_TOKEN

    def clear(self) -> None:
        self._cache.clear()


@lru_cache(maxsize=1)
def get_ols_cache() -> OLSCache:
    settings = get_settings()
    return OLSCache(str(settings.cache_dir / "ols"), ttl=settings.ols_cache_ttl)
