"""Helpers shared across tool implementations: envelope construction, timing."""

from __future__ import annotations

import time
from typing import Any

from cxg_census_mcp import __version__
from cxg_census_mcp.caches.facet_cache import get_facet_cache
from cxg_census_mcp.caches.ols_cache import get_ols_cache
from cxg_census_mcp.caches.plan_cache import get_plan_cache
from cxg_census_mcp.models.provenance import (
    QueryProvenance,
    ResponseEnvelope,
    ResponseMeta,
)


def cache_counters() -> tuple[dict[str, int], dict[str, int]]:
    ols = get_ols_cache()
    fc = get_facet_cache()
    pc = get_plan_cache()
    hits = {"ols": ols.hits, "facets": fc.hits, "plans": pc.hits}
    misses = {"ols": ols.misses, "facets": fc.misses, "plans": pc.misses}
    return hits, misses


class TimedScope:
    def __init__(self) -> None:
        self.started = time.monotonic()

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.started) * 1000


def build_envelope(
    *,
    data: Any,
    provenance: QueryProvenance,
    call_id: str,
    timer: TimedScope,
    warnings: list[str] | None = None,
    defaults_applied: dict[str, Any] | None = None,
) -> ResponseEnvelope:
    hits, misses = cache_counters()
    return ResponseEnvelope(
        data=data,
        query_provenance=provenance,
        call_id=call_id,
        meta=ResponseMeta(
            elapsed_ms=timer.elapsed_ms(),
            cache_hits=hits,
            cache_misses=misses,
            server_version=__version__,
        ),
        warnings=warnings or [],
        defaults_applied=defaults_applied or {},
    )
