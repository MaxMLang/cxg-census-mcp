"""Pick tissue vs tissue_general (or both) from expansion + curated general terms."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Literal

from cxg_census_mcp.models.ontology import ExpandedTerm

TissueStrategy = Literal["tissue", "tissue_general", "dual_column"]


def _load_general_terms() -> set[str]:
    raw = resources.files("cxg_census_mcp.data").joinpath("tissue_general_terms.json").read_text()
    data = json.loads(raw)
    return {t["curie"] for t in data.get("terms", [])}


@dataclass
class TissueRouting:
    strategy: TissueStrategy
    column: str
    rewrite_to: str | None = None
    reason: str = ""
    dual_predicates: list[str] = field(default_factory=list)


_TISSUE_GENERAL_TERMS = _load_general_terms()


def is_general_term(curie: str) -> bool:
    return curie in _TISSUE_GENERAL_TERMS


def pick_tissue_column(
    curie: str,
    expansion: ExpandedTerm | None = None,
) -> TissueRouting:
    """Decide tissue routing for a single resolved tissue term.

    Rules:

    1. If the queried term is itself a tissue_general roll-up → use ``tissue_general``.
    2. If we have an expansion, every expanded term is a roll-up → ``tissue_general``.
    3. If expansion contains both general and specific representations →
       ``dual_column`` (predicate ORs both columns to avoid losing rows).
    4. Otherwise → ``tissue`` for specific anatomy.
    """
    if is_general_term(curie):
        return TissueRouting(
            strategy="tissue_general",
            column="tissue_general_ontology_term_id",
            reason="term_is_roll_up",
        )

    if expansion is None or not expansion.terms:
        return TissueRouting(
            strategy="tissue",
            column="tissue_ontology_term_id",
            reason="specific_anatomy",
        )

    expanded = set(expansion.terms)
    expanded_general = expanded & _TISSUE_GENERAL_TERMS
    expanded_specific = expanded - _TISSUE_GENERAL_TERMS

    if expanded and expanded.issubset(_TISSUE_GENERAL_TERMS):
        return TissueRouting(
            strategy="tissue_general",
            column="tissue_general_ontology_term_id",
            reason="all_expanded_terms_are_roll_ups",
        )

    if expanded_general and expanded_specific:
        return TissueRouting(
            strategy="dual_column",
            column="tissue_ontology_term_id",
            dual_predicates=[
                "tissue_ontology_term_id",
                "tissue_general_ontology_term_id",
            ],
            reason=(
                "expansion_spans_general_and_specific; querying both columns "
                "to avoid losing data only present in one representation"
            ),
        )

    return TissueRouting(
        strategy="tissue",
        column="tissue_ontology_term_id",
        reason="specific_anatomy_or_descendants",
    )
