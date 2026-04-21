"""Disk + LRU store of QueryPlan JSON keyed by ``call_id`` (for export_snippet)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cxg_census_mcp.caches.filter_lru import get_filter_lru
from cxg_census_mcp.caches.plan_cache import get_plan_cache
from cxg_census_mcp.utils.stable_hash import stable_hash


def make_call_id(plan_hash: str, response_kind: str, census_version: str) -> str:
    return stable_hash(plan_hash, response_kind, census_version, length=20)


class PlanStore:
    def put(self, *, call_id: str, plan_json: dict[str, Any]) -> None:
        get_plan_cache().set(call_id, plan_json)
        get_filter_lru().set(call_id, plan_json)

    def get(self, call_id: str) -> dict[str, Any] | None:
        hot = get_filter_lru().get(call_id)
        if hot is not None:
            return hot
        cold = get_plan_cache().get(call_id)
        if cold is not None:
            get_filter_lru().set(call_id, cold)
        return cold

    def vacuum(self) -> int:
        """Drop expired entries from the on-disk plan cache.

        Returns the number of entries reclaimed. ``diskcache`` already evicts
        on read, so this is a manual sweep used by maintenance scripts.
        """
        cache = get_plan_cache()._cache
        return cache.expire()

    def stats(self) -> dict[str, int]:
        pc = get_plan_cache()
        return {"hits": pc.hits, "misses": pc.misses, "size": len(pc._cache)}


@lru_cache(maxsize=1)
def get_plan_store() -> PlanStore:
    return PlanStore()
