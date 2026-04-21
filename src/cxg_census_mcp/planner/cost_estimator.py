"""Pre-query cell-count and runtime estimation.

Lookups consult the per-version ``summary_cell_counts`` table (cached) and
fall back to coarse heuristics when the table is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.planner._long_table import (
    is_long_format,
    matches_long,
    n_cells_for_long_row,
)


@dataclass
class CostEstimate:
    estimated_cells: int | None
    estimated_runtime_ms: int | None
    coarse: bool = False


def _dataset_upper_bound(
    client: CensusClient,
    census_version: str,
    dataset_ids: list[str],
) -> int | None:
    """Sum dataset_total_cell_count for dataset_ids (upper bound for any filter)."""
    try:
        meta = client.dataset_metadata(version=census_version, dataset_ids=dataset_ids)
    except Exception:
        return None
    if not meta:
        return None
    total = 0
    for ds_id in dataset_ids:
        info = meta.get(ds_id)
        if not info:
            continue
        n = info.get("n_cells_total")
        if n is None:
            continue
        total += int(n)
    return total or None


def estimate_cost(
    *,
    organism: str,
    census_version: str,
    resolved_filters: dict[str, list[str]],
    client: CensusClient | None = None,
) -> CostEstimate:
    """Estimate cells matching ``resolved_filters`` (each value is a list of CURIEs).

    Treats unrecognised columns as no-op constraints. Runtime estimate is a
    coarse heuristic: ~5µs per cell for tier-0/1, ~20µs per cell for tier-2.
    """
    client = client or get_census_client()
    try:
        tbl = client.summary_cell_counts(census_version, organism)
    except Exception:
        return CostEstimate(estimated_cells=None, estimated_runtime_ms=None, coarse=True)

    dataset_ids = resolved_filters.get("dataset_id") or []
    dataset_bound = (
        _dataset_upper_bound(client, census_version, list(dataset_ids))
        if dataset_ids
        else None
    )

    df = tbl.to_pylist()
    if not df:
        cells = dataset_bound if dataset_bound is not None else 0
        return CostEstimate(
            estimated_cells=cells,
            estimated_runtime_ms=int(cells * 0.005),
            coarse=True,
        )

    if is_long_format(tbl):
        # Long table = per-facet marginals; min over constrained facets is a safe upper bound.
        constrained = {
            col: vals
            for col, vals in resolved_filters.items()
            if vals and col not in {"dataset_id", "donor_id"}
        }
        if not constrained and dataset_bound is None:
            total = next(
                (int(r.get("total_cell_count") or 0) for r in df if r.get("category") == "all"),
                None,
            )
            return CostEstimate(
                estimated_cells=total,
                estimated_runtime_ms=int((total or 0) * 0.005),
                coarse=True,
            )
        per_facet_totals: list[int] = []
        for col, allowed in constrained.items():
            facet_total = sum(
                n_cells_for_long_row(r) for r in df if matches_long(r, {col: allowed})
            )
            per_facet_totals.append(facet_total)
        if dataset_bound is not None:
            per_facet_totals.append(dataset_bound)
        cells = min(per_facet_totals) if per_facet_totals else 0
        return CostEstimate(
            estimated_cells=cells,
            estimated_runtime_ms=int(cells * 0.005),
            coarse=True,
        )

    wide_filters = {
        col: vals
        for col, vals in resolved_filters.items()
        if col not in {"dataset_id", "donor_id"}
    }
    matched = [r for r in df if _matches_wide(r, wide_filters)]
    cells = sum(int(r.get("n_cells") or 0) for r in matched)
    if dataset_bound is not None:
        cells = min(cells, dataset_bound) if matched else dataset_bound
    return CostEstimate(
        estimated_cells=cells,
        estimated_runtime_ms=int(cells * 0.005),  # 5µs/cell baseline
        coarse=dataset_bound is not None,
    )


def _matches_wide(row: dict[str, Any], resolved: dict[str, list[str]]) -> bool:
    for col, allowed in resolved.items():
        if not allowed:
            continue
        v = row.get(col)
        if v is None:
            continue
        if v not in allowed:
            return False
    return True


def runtime_for_tier(tier: int, cells: int | None) -> int | None:
    if cells is None:
        return None
    factor = {0: 0.001, 1: 0.005, 2: 0.020}.get(tier, 0.005)
    return int(cells * factor)
