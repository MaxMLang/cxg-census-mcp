"""Payload for ``get_server_limits`` (caps + cache knobs + counters)."""

from __future__ import annotations

from pydantic import BaseModel


class ServerLimits(BaseModel):
    max_tier1_cells: int
    max_tier1_runtime_ms: int
    max_expression_cells: int
    max_expression_genes: int
    max_expression_groups: int
    max_expansion_terms: int
    max_preview_rows: int
    preview_default_rows: int
    max_http_per_minute: int
    progress_min_ms: int
    plan_cache_ttl_seconds: int
    last_call_lru_size: int
