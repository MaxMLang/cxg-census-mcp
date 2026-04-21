"""Tier 1: chunked obs iteration; aggregates only; checkpoints for cancel."""

from __future__ import annotations

from collections import Counter
from typing import Any

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.execution.caps import enforce_obs_caps
from cxg_census_mcp.models.counts import CellCount, GroupCount
from cxg_census_mcp.progress import ProgressReporter

CHUNK_ROWS = 50_000


async def run_tier1_obs(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    estimated_cells: int | None = None,
    estimated_runtime_ms: int | None = None,
    group_by: str | None = None,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
    client: CensusClient | None = None,
) -> CellCount:
    enforce_obs_caps(estimated_cells=estimated_cells, estimated_runtime_ms=estimated_runtime_ms)
    client = client or get_census_client()

    cols = ["soma_joinid"]
    if group_by:
        cols.append(group_by)

    counter: Counter = Counter()
    total = 0
    if progress is not None:
        progress.total = max(1, estimated_cells or 1)

    for chunk in client.stream_obs(
        version=census_version,
        organism=organism,
        value_filter=value_filter,
        column_names=cols,
        chunk_rows=CHUNK_ROWS,
    ):
        if cancel is not None:
            await cancel.checkpoint()
        n = chunk.num_rows
        total += n
        if group_by and group_by in chunk.column_names:
            counter.update(
                str(v) if v is not None else "<unknown>" for v in chunk[group_by].to_pylist()
            )
        if progress is not None:
            await progress.update(total, f"scanning obs ({total}/{progress.total})")

    by_group = [GroupCount(group=k, count=v) for k, v in counter.most_common()]
    return CellCount(total=total, group_by=group_by, by_group=by_group, n_groups=len(by_group))


async def get_obs_columns(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    columns: list[str],
    limit: int,
    client: CensusClient | None = None,
) -> list[dict[str, Any]]:
    client = client or get_census_client()
    rows: list[dict[str, Any]] = []
    for chunk in client.stream_obs(
        version=census_version,
        organism=organism,
        value_filter=value_filter,
        column_names=columns,
        chunk_rows=min(limit * 4, CHUNK_ROWS),
    ):
        rows.extend(chunk.to_pylist())
        if len(rows) >= limit:
            break
    return rows[:limit]
