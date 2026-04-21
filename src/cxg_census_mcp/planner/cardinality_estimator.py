"""Group-by cardinality estimation (how many distinct groups we'd return)."""

from __future__ import annotations

from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.planner._long_table import (
    group_value_long,
    is_long_format,
    matches_long,
)


def estimate_group_count(
    *,
    organism: str,
    census_version: str,
    group_by: str | None,
    resolved_filters: dict[str, list[str]],
    client: CensusClient | None = None,
) -> int | None:
    if group_by is None:
        return None

    # e.g. group_by=dataset_id with dataset_id=[...] — summary table has no dataset_id column.
    pinned = resolved_filters.get(group_by)
    if pinned:
        return len(set(pinned))

    client = client or get_census_client()
    try:
        tbl = client.summary_cell_counts(census_version, organism)
    except Exception:
        return None

    df = tbl.to_pylist()

    if is_long_format(tbl):
        seen: set[str] = set()
        for r in df:
            v = group_value_long(r, group_by)
            if v is None:
                continue
            if not matches_long(r, resolved_filters):
                continue
            seen.add(v)
        return len(seen) or None

    if group_by not in tbl.column_names:
        return None

    seen = set()
    for r in df:
        if not _matches_wide(r, resolved_filters):
            continue
        seen.add(r.get(group_by))
    return len(seen)


def _matches_wide(row: dict, resolved: dict[str, list[str]]) -> bool:
    for col, allowed in resolved.items():
        if not allowed:
            continue
        v = row.get(col)
        if v is None:
            continue
        if v not in allowed:
            return False
    return True
