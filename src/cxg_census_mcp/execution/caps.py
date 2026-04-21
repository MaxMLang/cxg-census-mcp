"""Raise typed errors when estimates exceed configured caps."""

from __future__ import annotations

from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import (
    GroupCardinalityTooHighError,
    QueryTooLargeError,
    TooManyGenesError,
)
from cxg_census_mcp.metrics import inc_cap_rejection


def enforce_obs_caps(*, estimated_cells: int | None, estimated_runtime_ms: int | None) -> None:
    s = get_settings()
    if estimated_cells is not None and estimated_cells > s.max_tier1_cells:
        inc_cap_rejection("tier1_cells")
        raise QueryTooLargeError(
            f"Estimated {estimated_cells:,} cells exceeds max_tier1_cells ({s.max_tier1_cells:,}).",
            retry_with={"use_export_snippet": True},
        )
    if estimated_runtime_ms is not None and estimated_runtime_ms > s.max_tier1_runtime_ms:
        inc_cap_rejection("tier1_runtime")
        raise QueryTooLargeError(
            f"Estimated runtime {estimated_runtime_ms} ms exceeds "
            f"max_tier1_runtime_ms ({s.max_tier1_runtime_ms} ms).",
            retry_with={"use_export_snippet": True},
        )


def enforce_expression_caps(
    *,
    estimated_cells: int | None,
    estimated_groups: int | None,
    n_genes: int,
) -> None:
    s = get_settings()
    if n_genes > s.max_expression_genes:
        inc_cap_rejection("expression_genes")
        raise TooManyGenesError(
            f"{n_genes} genes exceeds max_expression_genes ({s.max_expression_genes}).",
            retry_with={"batch_size": s.max_expression_genes},
        )
    if estimated_groups is not None and estimated_groups > s.max_expression_groups:
        inc_cap_rejection("expression_groups")
        raise GroupCardinalityTooHighError(
            f"{estimated_groups} groups exceeds max_expression_groups ({s.max_expression_groups}).",
        )
    if estimated_cells is not None and estimated_cells > s.max_expression_cells:
        inc_cap_rejection("expression_cells")
        raise QueryTooLargeError(
            f"Estimated {estimated_cells:,} cells exceeds max_expression_cells "
            f"({s.max_expression_cells:,}).",
            retry_with={"use_export_snippet": True},
        )
