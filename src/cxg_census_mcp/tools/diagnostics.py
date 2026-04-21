"""get_server_limits — exposes the cap configuration plus runtime stats."""

from __future__ import annotations

from cxg_census_mcp.config import get_settings
from cxg_census_mcp.metrics import snapshot
from cxg_census_mcp.models.limits import ServerLimits
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope


async def get_server_limits() -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    limits = ServerLimits(
        max_tier1_cells=s.max_tier1_cells,
        max_tier1_runtime_ms=s.max_tier1_runtime_ms,
        max_expression_cells=s.max_expression_cells,
        max_expression_genes=s.max_expression_genes,
        max_expression_groups=s.max_expression_groups,
        max_expansion_terms=s.max_expansion_terms,
        max_preview_rows=s.max_preview_rows,
        preview_default_rows=s.preview_default_rows,
        max_http_per_minute=s.max_http_per_minute,
        progress_min_ms=s.progress_min_ms,
        plan_cache_ttl_seconds=s.plan_cache_ttl,
        last_call_lru_size=s.last_call_lru_size,
    )
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="n/a",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    return build_envelope(
        data={
            "limits": limits.model_dump(),
            "runtime_stats": snapshot(),
        },
        provenance=provenance,
        call_id="server_limits",
        timer=timer,
    )
