"""Group-by allowlist + helpers (the FilterSpec model itself lives in models/filters.py)."""

from __future__ import annotations

from cxg_census_mcp.errors import InvalidFilterError

GROUP_BY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "cell_type",
        "cell_type_ontology_term_id",
        "tissue",
        "tissue_ontology_term_id",
        "tissue_general",
        "tissue_general_ontology_term_id",
        "disease",
        "disease_ontology_term_id",
        "assay",
        "assay_ontology_term_id",
        "self_reported_ethnicity",
        "self_reported_ethnicity_ontology_term_id",
        "development_stage",
        "development_stage_ontology_term_id",
        "sex",
        "suspension_type",
        "is_primary_data",
        "dataset_id",
        "donor_id",
        "collection_id",
    }
)


def validate_group_by(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cols = [value] if isinstance(value, str) else list(value)
    bad = [c for c in cols if c not in GROUP_BY_ALLOWLIST]
    if bad:
        raise InvalidFilterError(
            f"Unsupported group_by columns: {bad}",
            action_hint=("Choose from: " + ", ".join(sorted(GROUP_BY_ALLOWLIST))),
        )
    return cols
