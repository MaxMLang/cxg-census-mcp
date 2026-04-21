"""Map ontology prefix (+ facet) to Census obs column names."""

from __future__ import annotations

from typing import TypedDict


class OntologyColumns(TypedDict, total=False):
    id_col: str
    label_col: str
    general_id_col: str
    general_label_col: str


ONTOLOGY_COLUMN_MAP: dict[str, OntologyColumns] = {
    "CL": {
        "id_col": "cell_type_ontology_term_id",
        "label_col": "cell_type",
    },
    "UBERON": {
        "id_col": "tissue_ontology_term_id",
        "label_col": "tissue",
        "general_id_col": "tissue_general_ontology_term_id",
        "general_label_col": "tissue_general",
    },
    "MONDO": {
        "id_col": "disease_ontology_term_id",
        "label_col": "disease",
    },
    "PATO": {  # `normal` lives in PATO
        "id_col": "disease_ontology_term_id",
        "label_col": "disease",
    },
    "EFO_ASSAY": {
        "id_col": "assay_ontology_term_id",
        "label_col": "assay",
    },
    "HsapDv": {
        "id_col": "development_stage_ontology_term_id",
        "label_col": "development_stage",
    },
    "MmusDv": {
        "id_col": "development_stage_ontology_term_id",
        "label_col": "development_stage",
    },
    "HANCESTRO": {
        "id_col": "self_reported_ethnicity_ontology_term_id",
        "label_col": "self_reported_ethnicity",
    },
}


# Map FilterSpec field name → ontology prefix expected for resolver scoping.
FACET_TO_ONTOLOGY: dict[str, str] = {
    "cell_type": "CL",
    "tissue": "UBERON",
    "disease": "MONDO",
    "assay": "EFO",
    "development_stage": "HsapDv",
    "self_reported_ethnicity": "HANCESTRO",
}


def ontology_for_facet(facet: str) -> str | None:
    """Return the canonical ontology prefix for a facet, or None if untyped."""
    return FACET_TO_ONTOLOGY.get(facet)


def column_for(curie_prefix: str, *, facet: str | None = None) -> OntologyColumns:
    """Look up Census columns for a CURIE prefix.

    EFO is ambiguous (assay vs developmental stage); pass ``facet`` to disambiguate.
    """
    if curie_prefix == "EFO":
        if facet == "development_stage":
            return ONTOLOGY_COLUMN_MAP["HsapDv"]
        return ONTOLOGY_COLUMN_MAP["EFO_ASSAY"]
    if curie_prefix in ONTOLOGY_COLUMN_MAP:
        return ONTOLOGY_COLUMN_MAP[curie_prefix]
    raise KeyError(f"No Census column mapping for ontology prefix {curie_prefix!r}")
