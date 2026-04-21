"""Regression: expansion_warnings when harmonized obs drop descendant terms."""

from __future__ import annotations

from cxg_census_mcp.models.provenance import ExpansionTrace
from cxg_census_mcp.planner.query_plan import QueryPlan, expansion_warnings


def _plan_with_traces(*traces: ExpansionTrace) -> QueryPlan:
    return QueryPlan(
        value_filter="",
        organism="homo_sapiens",
        census_version="2025-11-08",
        schema_version="1.0.0",
        plan_hash="x" * 16,
        expansion_traces=list(traces),
    )


def test_no_warning_for_exact_expansion() -> None:
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="CL:0000236",
            query_label="B cell",
            direction="exact",
            n_terms=1,
            n_terms_total_in_ontology=1,
            n_terms_dropped_no_cells=0,
        )
    )
    assert expansion_warnings(plan) == []


def test_no_warning_when_no_terms_dropped() -> None:
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="UBERON:0002048",
            query_label="lung",
            direction="descendants_inclusive",
            n_terms=12,
            n_terms_total_in_ontology=12,
            n_terms_dropped_no_cells=0,
        )
    )
    assert expansion_warnings(plan) == []


def test_warns_when_expansion_collapses_to_original_term() -> None:
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="CL:0000236",
            query_label="B cell",
            direction="descendants_inclusive",
            n_terms=1,
            n_terms_total_in_ontology=97,
            n_terms_dropped_no_cells=96,
            dropped_terms_sample=("CL:0000785", "CL:0000787", "CL:0000788"),
        )
    )
    warnings = expansion_warnings(plan)
    assert len(warnings) == 1
    msg = warnings[0]
    assert "CL:0000236" in msg
    assert "B cell" in msg
    assert "no-op" in msg
    assert "96" in msg
    assert "CL:0000785" in msg
    assert "preview_obs" in msg
    assert "author_cell_type" in msg


def test_warns_softly_when_some_descendants_dropped() -> None:
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="CL:0000084",
            query_label="T cell",
            direction="descendants_inclusive",
            n_terms=8,
            n_terms_total_in_ontology=42,
            n_terms_dropped_no_cells=34,
            dropped_terms_sample=("CL:0000800", "CL:0000913"),
        )
    )
    warnings = expansion_warnings(plan)
    assert len(warnings) == 1
    msg = warnings[0]
    assert "8/42" in msg
    assert "34" in msg
    assert "no-op" not in msg


def test_warns_loudly_when_all_terms_absent_from_census() -> None:
    """When the original term itself is absent (n_terms=0), the warning has
    to be loud and tell the agent that the count of zero is an artifact of
    the harmonisation, not a fact about biology."""
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="CL:0000625",
            query_label="CD8 T cell",
            direction="exact",
            n_terms=0,
            n_terms_total_in_ontology=1,
            n_terms_dropped_no_cells=1,
            dropped_terms_sample=("CL:0000625",),
        )
    )
    warnings = expansion_warnings(plan)
    assert len(warnings) == 1
    msg = warnings[0]
    assert "CL:0000625" in msg
    assert "not present" in msg
    assert "zero cells" in msg
    assert "preview_obs" in msg
    assert "list_available_values" in msg


def test_warns_per_facet_independently() -> None:
    plan = _plan_with_traces(
        ExpansionTrace(
            query_curie="CL:0000236",
            query_label="B cell",
            direction="descendants_inclusive",
            n_terms=1,
            n_terms_total_in_ontology=97,
            n_terms_dropped_no_cells=96,
        ),
        ExpansionTrace(
            query_curie="UBERON:0002048",
            query_label="lung",
            direction="exact",
            n_terms=1,
            n_terms_total_in_ontology=1,
            n_terms_dropped_no_cells=0,
        ),
    )
    warnings = expansion_warnings(plan)
    assert len(warnings) == 1
    assert "CL:0000236" in warnings[0]
