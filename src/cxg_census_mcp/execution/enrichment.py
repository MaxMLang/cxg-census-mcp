"""Attach labels to CURIEs (OLS) and dataset_id (census_info.datasets)."""

from __future__ import annotations

import asyncio
from typing import Any

from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.clients.ols import get_ols_client
from cxg_census_mcp.errors import OntologyUnavailableError
from cxg_census_mcp.logging_setup import get_logger

log = get_logger(__name__)


# Map an obs column name to whether it carries a CURIE we can resolve via OLS.
_ONTOLOGY_COLUMNS: set[str] = {
    "cell_type_ontology_term_id",
    "tissue_ontology_term_id",
    "tissue_general_ontology_term_id",
    "disease_ontology_term_id",
    "assay_ontology_term_id",
    "self_reported_ethnicity_ontology_term_id",
    "development_stage_ontology_term_id",
    "sex_ontology_term_id",
}

# Friendly short names → canonical obs column. Accepted in any tool that takes
# a ``group_by`` argument.
GROUP_BY_ALIASES: dict[str, str] = {
    "cell_type": "cell_type_ontology_term_id",
    "tissue": "tissue_ontology_term_id",
    "tissue_general": "tissue_general_ontology_term_id",
    "disease": "disease_ontology_term_id",
    "assay": "assay_ontology_term_id",
    "ethnicity": "self_reported_ethnicity_ontology_term_id",
    "development_stage": "development_stage_ontology_term_id",
    "sex": "sex_ontology_term_id",
}


def canonical_group_by(group_by: str | None) -> str | None:
    """Resolve short forms (``cell_type`` → ``cell_type_ontology_term_id``).

    Pass-through for unknown / already-canonical names.
    """
    if group_by is None:
        return None
    return GROUP_BY_ALIASES.get(group_by, group_by)


_ONTOLOGY_PREFIXES: set[str] = {
    "CL",
    "UBERON",
    "MONDO",
    "PATO",
    "EFO",
    "HANCESTRO",
    "HsapDv",
    "MmusDv",
    "PR",
    "NCBITaxon",
}


def _is_curie(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if ":" not in value:
        return False
    prefix = value.split(":", 1)[0]
    return prefix in _ONTOLOGY_PREFIXES


async def resolve_curie_labels(curies: list[str]) -> dict[str, str | None]:
    """Batch-resolve CURIEs to labels via OLS. Missing → ``None``."""
    unique = sorted({c for c in curies if _is_curie(c)})
    if not unique:
        return {}
    client = get_ols_client()

    async def _one(c: str) -> tuple[str, str | None]:
        try:
            term = await client.get_term(c)
            return c, (term.label if term else None)
        except OntologyUnavailableError as exc:
            log.warning("label_lookup_failed", curie=c, error=str(exc))
            return c, None

    pairs = await asyncio.gather(*(_one(c) for c in unique))
    return dict(pairs)


def resolve_dataset_titles(
    dataset_ids: list[str],
    *,
    census_version: str,
) -> dict[str, str | None]:
    """Lookup dataset titles. Missing → ``None``."""
    unique = sorted({d for d in dataset_ids if isinstance(d, str)})
    if not unique:
        return {}
    meta = get_census_client().dataset_metadata(version=census_version, dataset_ids=unique)
    return {d: (meta.get(d) or {}).get("title") for d in unique}


async def label_for_group(
    group_by: str,
    group_keys: list[str],
    *,
    census_version: str,
) -> dict[str, str | None]:
    """Resolve labels for a list of group keys, dispatching on column type.

    * ``dataset_id`` → dataset title
    * any ``*_ontology_term_id`` column → OLS label
    * everything else → all ``None``
    """
    if not group_keys:
        return {}
    if group_by == "dataset_id":
        return resolve_dataset_titles(group_keys, census_version=census_version)
    if group_by in _ONTOLOGY_COLUMNS:
        return await resolve_curie_labels(group_keys)
    return dict.fromkeys(group_keys)


async def enrich_obs_rows(
    rows: list[dict[str, Any]],
    *,
    census_version: str,
) -> list[dict[str, Any]]:
    """Add ``*_label`` and ``dataset_title`` fields to each preview row.

    Returns a *new* list — does not mutate the input. Existing keys are
    preserved; new keys use the convention ``{column_without_suffix}_label``
    for ontology columns (e.g. ``cell_type_ontology_term_id`` →
    ``cell_type_label``) and ``dataset_title`` for ``dataset_id``.
    """
    if not rows:
        return rows

    curies: list[str] = []
    dataset_ids: list[str] = []
    for r in rows:
        for col, val in r.items():
            if col in _ONTOLOGY_COLUMNS and _is_curie(val):
                curies.append(val)
            elif col == "dataset_id" and isinstance(val, str):
                dataset_ids.append(val)

    label_map = await resolve_curie_labels(curies)
    title_map = resolve_dataset_titles(dataset_ids, census_version=census_version)

    enriched: list[dict[str, Any]] = []
    for r in rows:
        new = dict(r)
        for col, val in r.items():
            if col in _ONTOLOGY_COLUMNS and _is_curie(val):
                key = _label_key_for(col)
                new[key] = label_map.get(val)
            elif col == "dataset_id" and isinstance(val, str):
                new["dataset_title"] = title_map.get(val)
        enriched.append(new)
    return enriched


def _label_key_for(column: str) -> str:
    """Map ``foo_ontology_term_id`` → ``foo_label``."""
    if column.endswith("_ontology_term_id"):
        return column[: -len("_ontology_term_id")] + "_label"
    return column + "_label"
