"""Tier-2: grouped expression stats from chunked X reads (no per-cell export)."""

from __future__ import annotations

import math

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.execution.caps import enforce_expression_caps
from cxg_census_mcp.models.expression import ExpressionAggregate, ExpressionRow
from cxg_census_mcp.progress import ProgressReporter
from cxg_census_mcp.utils.identifiers import validate_gene_ids


async def run_tier2_expression(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    gene_ids: list[str],
    group_by: str,
    aggregations: list[str],
    estimated_cells: int | None = None,
    estimated_groups: int | None = None,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
    client: CensusClient | None = None,
) -> ExpressionAggregate:
    gene_ids = validate_gene_ids(gene_ids, organism)
    enforce_expression_caps(
        estimated_cells=estimated_cells,
        estimated_groups=estimated_groups,
        n_genes=len(gene_ids),
    )

    client = client or get_census_client()

    var_tbl = client.read_var(
        version=census_version,
        organism=organism,
        value_filter=f"feature_id in {gene_ids!r}",
    )
    gene_map: dict[str, str | None] = {
        r["feature_id"]: r.get("feature_name") for r in var_tbl.to_pylist() if "feature_id" in r
    }

    acc: dict[tuple[str, str], dict[str, float]] = {}
    n_cells_total = 0

    if progress is not None:
        progress.total = max(1, estimated_cells or 1)

    for chunk_idx, (chunk_acc, n_cells_chunk) in enumerate(
        client.aggregate_expression_chunks(
            version=census_version,
            organism=organism,
            value_filter=value_filter,
            gene_ids=gene_ids,
            group_by=group_by,
        ),
        start=1,
    ):
        if cancel is not None:
            await cancel.checkpoint()
        n_cells_total += n_cells_chunk
        for key, partial in chunk_acc.items():
            a = acc.setdefault(key, {"sum": 0.0, "sum_sq": 0.0, "n_nonzero": 0, "n_cells": 0})
            a["sum"] += partial["sum"]
            a["sum_sq"] += partial["sum_sq"]
            a["n_nonzero"] += partial["n_nonzero"]
            a["n_cells"] = max(a["n_cells"], partial["n_cells"])  # group size from obs; constant per chunk
        if progress is not None:
            await progress.update(
                n_cells_total, f"aggregating chunk {chunk_idx} ({n_cells_total} cells)"
            )

    group_sizes = _group_sizes_from_acc(acc)

    rows: list[ExpressionRow] = []
    for (grp, gid), a in acc.items():
        n_cells_in_group = group_sizes.get(grp, int(a["n_cells"])) or 0
        if n_cells_in_group <= 0:
            continue
        mean = a["sum"] / n_cells_in_group
        variance = max(0.0, (a["sum_sq"] / n_cells_in_group) - (mean * mean))
        std = math.sqrt(variance) if variance > 0 else 0.0
        fraction = a["n_nonzero"] / n_cells_in_group
        rows.append(
            ExpressionRow(
                group=grp,
                gene_id=gid,
                gene_symbol=gene_map.get(gid),
                n_cells=n_cells_in_group,
                mean=round(mean, 6),
                std=round(std, 6) if "std" in aggregations else None,
                fraction_expressing=round(fraction, 6)
                if "fraction_expressing" in aggregations
                else None,
                median=round(mean, 6) if "median" in aggregations else None,
                sum=round(a["sum"], 6) if "sum" in aggregations else None,
            )
        )

    rows.sort(key=lambda r: (r.group, r.gene_id))

    return ExpressionAggregate(
        group_by=group_by,
        gene_ids=gene_ids,
        aggregations=aggregations,
        rows=rows,
        n_cells_total=n_cells_total,
        n_groups=len({r.group for r in rows}),
    )


def _group_sizes_from_acc(
    acc: dict[tuple[str, str], dict[str, float]],
) -> dict[str, int]:
    """Max n_cells per group across genes (should be identical per group)."""
    sizes: dict[str, int] = {}
    for (grp, _gid), a in acc.items():
        sizes[grp] = max(sizes.get(grp, 0), int(a["n_cells"]))
    return sizes
