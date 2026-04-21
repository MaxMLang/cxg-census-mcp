"""Tier routing: counts → 0; obs → 1; aggregate expression → 2; over caps → 9."""

from __future__ import annotations

from typing import Literal

from cxg_census_mcp.config import get_settings

ToolKind = Literal["count", "list_datasets", "obs_preview", "obs_scan", "aggregate_expression"]


def route_tier(
    *,
    tool_kind: ToolKind,
    estimated_cells: int | None,
    estimated_runtime_ms: int | None,
    n_genes: int = 0,
    estimated_groups: int | None = None,
) -> tuple[int, str | None]:
    """(tier, refusal_reason). Tier 9 → snippet path."""
    s = get_settings()

    if tool_kind in ("count", "list_datasets"):
        return 0, None

    if tool_kind == "obs_preview":
        return 1, None

    if tool_kind == "obs_scan":
        if estimated_cells is not None and estimated_cells > s.max_tier1_cells:
            return 9, (
                f"Estimated {estimated_cells:,} cells exceeds Tier-1 cap "
                f"({s.max_tier1_cells:,}); use export_snippet."
            )
        if estimated_runtime_ms is not None and estimated_runtime_ms > s.max_tier1_runtime_ms:
            return 9, (
                f"Estimated runtime {estimated_runtime_ms} ms exceeds "
                f"max_tier1_runtime_ms ({s.max_tier1_runtime_ms} ms); use export_snippet."
            )
        return 1, None

    if tool_kind == "aggregate_expression":
        if n_genes > s.max_expression_genes:
            return 9, (
                f"{n_genes} genes exceeds max_expression_genes ({s.max_expression_genes}); "
                "split into batches or use export_snippet."
            )
        if estimated_groups is not None and estimated_groups > s.max_expression_groups:
            return 9, (
                f"Group cardinality {estimated_groups} exceeds "
                f"max_expression_groups ({s.max_expression_groups})."
            )
        if estimated_cells is not None and estimated_cells > s.max_expression_cells:
            return 9, (
                f"Estimated {estimated_cells:,} cells exceeds max_expression_cells "
                f"({s.max_expression_cells:,}); use export_snippet."
            )
        return 2, None

    return 0, None
