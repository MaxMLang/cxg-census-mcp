"""Process-local counters; dump as Prometheus text (no prometheus_client dep)."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TypedDict


class CacheStats(TypedDict):
    hits: int
    misses: int


class PlanCacheStats(TypedDict):
    hits: int
    misses: int
    size: int


class MetricsSnapshot(TypedDict):
    tool_calls: dict[str, int]
    tool_errors: dict[str, int]
    cap_rejections: dict[str, int]
    cancellations: int
    ols_cache: CacheStats
    facet_cache: CacheStats
    plan_cache: PlanCacheStats


_LOCK = threading.Lock()


@dataclass
class Counters:
    cap_rejections: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tool_calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tool_errors: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    cancellations: int = 0


_C = Counters()


def inc_cap_rejection(kind: str) -> None:
    with _LOCK:
        _C.cap_rejections[kind] += 1


def inc_tool_call(name: str) -> None:
    with _LOCK:
        _C.tool_calls[name] += 1


def inc_tool_error(name: str, code: str) -> None:
    with _LOCK:
        _C.tool_errors[(name, code)] += 1


def inc_cancellation() -> None:
    with _LOCK:
        _C.cancellations += 1


def snapshot() -> MetricsSnapshot:
    """Snapshot all counters and (live) cache hit/miss + plan-store stats."""
    from cxg_census_mcp.caches.facet_cache import get_facet_cache
    from cxg_census_mcp.caches.ols_cache import get_ols_cache
    from cxg_census_mcp.planner.plan_store import get_plan_store

    with _LOCK:
        cap = dict(_C.cap_rejections)
        calls = dict(_C.tool_calls)
        errs = {f"{n}|{c}": v for (n, c), v in _C.tool_errors.items()}
        cancellations = _C.cancellations

    return MetricsSnapshot(
        tool_calls=calls,
        tool_errors=errs,
        cap_rejections=cap,
        cancellations=cancellations,
        ols_cache=CacheStats(hits=get_ols_cache().hits, misses=get_ols_cache().misses),
        facet_cache=CacheStats(hits=get_facet_cache().hits, misses=get_facet_cache().misses),
        plan_cache=PlanCacheStats(**get_plan_store().stats()),  # type: ignore[typeddict-item]
    )


def render_prometheus() -> str:
    """Serialize :func:`snapshot` to Prometheus text exposition format."""
    snap = snapshot()
    lines: list[str] = []

    def _counter(metric: str, value: int, **labels: str) -> None:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            lines.append(f"{metric}{{{label_str}}} {value}")
        else:
            lines.append(f"{metric} {value}")

    lines.append("# HELP census_mcp_tool_calls_total Number of tool invocations.")
    lines.append("# TYPE census_mcp_tool_calls_total counter")
    for name, v in snap["tool_calls"].items():
        _counter("census_mcp_tool_calls_total", v, tool=name)

    lines.append("# HELP census_mcp_tool_errors_total Tool errors by code.")
    lines.append("# TYPE census_mcp_tool_errors_total counter")
    for k, v in snap["tool_errors"].items():
        tool, code = k.split("|", 1)
        _counter("census_mcp_tool_errors_total", v, tool=tool, code=code)

    lines.append("# HELP census_mcp_cap_rejections_total Requests refused by caps.")
    lines.append("# TYPE census_mcp_cap_rejections_total counter")
    for kind, v in snap["cap_rejections"].items():
        _counter("census_mcp_cap_rejections_total", v, kind=kind)

    lines.append("# HELP census_mcp_cancellations_total Cancelled requests.")
    lines.append("# TYPE census_mcp_cancellations_total counter")
    _counter("census_mcp_cancellations_total", snap["cancellations"])

    for cache_name in ("ols_cache", "facet_cache"):
        c: CacheStats = snap[cache_name]
        lines.append(f"# HELP census_mcp_{cache_name}_hits_total Cache hits for {cache_name}.")
        lines.append(f"# TYPE census_mcp_{cache_name}_hits_total counter")
        _counter(f"census_mcp_{cache_name}_hits_total", c["hits"])
        lines.append(f"# HELP census_mcp_{cache_name}_misses_total Cache misses for {cache_name}.")
        lines.append(f"# TYPE census_mcp_{cache_name}_misses_total counter")
        _counter(f"census_mcp_{cache_name}_misses_total", c["misses"])

    plan = snap["plan_cache"]
    lines.append("# HELP census_mcp_plan_cache_size Plan-cache entry count.")
    lines.append("# TYPE census_mcp_plan_cache_size gauge")
    _counter("census_mcp_plan_cache_size", plan["size"])

    return "\n".join(lines) + "\n"


def reset_for_tests() -> None:
    with _LOCK:
        _C.cap_rejections.clear()
        _C.tool_calls.clear()
        _C.tool_errors.clear()
        _C.cancellations = 0
