"""Small obs slice + per-column cardinality."""

from __future__ import annotations

from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.models.previews import ObsPreview


def preview_obs(
    *,
    organism: str,
    census_version: str,
    value_filter: str,
    columns: list[str] | None,
    limit: int | None = None,
    client: CensusClient | None = None,
) -> ObsPreview:
    s = get_settings()
    client = client or get_census_client()
    n = limit or s.preview_default_rows
    n = max(1, min(n, s.max_preview_rows))

    cols = columns or [
        "cell_type_ontology_term_id",
        "tissue_general_ontology_term_id",
        "disease_ontology_term_id",
        "assay_ontology_term_id",
        "is_primary_data",
        "dataset_id",
    ]

    tbl = client.read_obs(
        version=census_version,
        organism=organism,
        value_filter=value_filter,
        column_names=cols,
        limit=n,
    )

    rows = tbl.to_pylist()
    cardinality_hints: dict[str, int] = {}
    for c in cols:
        if c not in tbl.column_names:
            continue
        vals = tbl[c].to_pylist()
        cardinality_hints[c] = len(set(vals))

    note = (
        "Cardinality hints are computed from the preview sample only; "
        "they are lower bounds, not population estimates."
    )
    return ObsPreview(
        columns=cols,
        rows=rows,
        n_rows=len(rows),
        cardinality_hints=cardinality_hints,
        note=note,
    )
