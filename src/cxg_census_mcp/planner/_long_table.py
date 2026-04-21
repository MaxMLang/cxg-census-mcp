"""Helpers for live Census ``summary_cell_counts`` (long rows: category + label/ontology id)."""

from __future__ import annotations

from typing import Any

import pyarrow as pa

_LONG_FACET_MAP: dict[str, tuple[str, str]] = {
    "cell_type": ("cell_type_ontology_term_id", "ontology_term_id"),
    "tissue": ("tissue_ontology_term_id", "ontology_term_id"),
    "tissue_general": ("tissue_general_ontology_term_id", "ontology_term_id"),
    "disease": ("disease_ontology_term_id", "ontology_term_id"),
    "assay": ("assay_ontology_term_id", "ontology_term_id"),
    "self_reported_ethnicity": (
        "self_reported_ethnicity_ontology_term_id",
        "ontology_term_id",
    ),
    "sex": ("sex", "label"),
    "suspension_type": ("suspension_type", "label"),
}


def is_long_format(tbl: pa.Table) -> bool:
    names = set(tbl.column_names)
    return "category" in names and ("ontology_term_id" in names or "label" in names)


def matches_long(row: dict[str, Any], resolved: dict[str, list[str]]) -> bool:
    """Whether this long-format row passes the given planner-column filters."""
    cat = row.get("category")
    mapping = _LONG_FACET_MAP.get(cat) if cat else None
    if cat == "all" or mapping is None:
        return False
    planner_col, value_col = mapping
    allowed = resolved.get(planner_col)
    if allowed:
        v = row.get(value_col)
        if v not in allowed:
            return False
    return True


def n_cells_for_long_row(row: dict[str, Any]) -> int:
    for key in ("total_cell_count", "n_cells", "unique_cell_count"):
        v = row.get(key)
        if v is not None:
            return int(v)
    return 0


def group_value_long(row: dict[str, Any], group_by: str) -> str | None:
    for cat, (planner_col, value_col) in _LONG_FACET_MAP.items():
        if planner_col == group_by:
            if row.get("category") != cat:
                return None
            return row.get(value_col)
    return row.get(group_by)
