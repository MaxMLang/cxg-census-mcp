"""Tier 0: n_obs / light obs column reads / dataset metadata (no X)."""

from __future__ import annotations

from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.models.counts import CellCount, DatasetSummary, GroupCount


def run_tier0_count(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    group_by: str | None = None,
    client: CensusClient | None = None,
) -> CellCount:
    client = client or get_census_client()

    if group_by:
        grouped = client.count_obs_grouped(
            version=census_version,
            organism=organism,
            value_filter=value_filter,
            group_by=group_by,
        )
        by_group = [
            GroupCount(group=k, count=v) for k, v in sorted(grouped.items(), key=lambda x: -x[1])
        ]
        total = sum(g.count for g in by_group)
        return CellCount(
            total=total,
            group_by=group_by,
            by_group=by_group,
            n_groups=len(by_group),
        )

    total = client.count_obs(
        version=census_version,
        organism=organism,
        value_filter=value_filter,
    )
    return CellCount(total=total, group_by=None, by_group=[], n_groups=0)


def run_tier0_datasets(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    limit: int = 100,
    client: CensusClient | None = None,
) -> list[DatasetSummary]:
    """List datasets matching ``value_filter`` ranked by cell count.

    We do this via a single-column obs scan over ``dataset_id`` (same
    machinery as :func:`run_tier0_count` with ``group_by="dataset_id"``)
    then enrich with title / collection / DOI from
    ``census_info.datasets``.
    """
    client = client or get_census_client()
    counts = client.count_obs_grouped(
        version=census_version,
        organism=organism,
        value_filter=value_filter,
        group_by="dataset_id",
    )
    sorted_ds = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]

    metadata = client.dataset_metadata(
        version=census_version,
        dataset_ids=[ds_id for ds_id, _ in sorted_ds],
    )

    out: list[DatasetSummary] = []
    for ds_id, n_cells in sorted_ds:
        meta = metadata.get(ds_id, {})
        out.append(
            DatasetSummary(
                dataset_id=ds_id,
                organism=organism,
                n_cells=n_cells,
                title=meta.get("title"),
                collection_id=meta.get("collection_id"),
                collection_name=meta.get("collection_name"),
                collection_doi=meta.get("collection_doi"),
                citation=meta.get("citation"),
                n_cells_total=meta.get("n_cells_total"),
            )
        )
    return out
