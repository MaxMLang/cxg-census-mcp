"""Happy-path coverage for tool wrappers that lacked direct envelope tests.

These intentionally stay shallow — deeper unit tests for the underlying
execution / planner / OLS code already exist; the goal here is just to
exercise the public ``tools.*`` surface end-to-end so that the envelope
shape, attribution, call_id, and provenance all stay covered.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cxg_census_mcp.config import get_settings
from cxg_census_mcp.models.filters import FilterSpec, TermFilter
from cxg_census_mcp.tools import (
    aggregate_expression,
    expand_term,
    gene_coverage,
    term_definition,
)
from cxg_census_mcp.tools.previews import preview_obs

pytestmark = pytest.mark.asyncio


def _ols_term_doc(curie: str, label: str, ontology: str, *, definition: str | None = None) -> dict:
    doc = {
        "obo_id": curie,
        "label": label,
        "ontology_prefix": ontology,
        "ontology_name": ontology.lower(),
        "iri": f"http://purl.obolibrary.org/obo/{curie.replace(':', '_')}",
        "is_obsolete": False,
        "synonym": [],
    }
    if definition is not None:
        doc["description"] = [definition]
    return doc


# --- aggregate_expression ----------------------------------------------------


async def test_aggregate_expression_returns_grouped_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock catalog says lung+covid+B-cell still estimates well above the
    # default 2M expression cap, so widen it for this happy-path test.
    monkeypatch.setenv("CXG_CENSUS_MCP_MAX_EXPRESSION_CELLS", "100000000")
    from cxg_census_mcp import config as _cfg

    _cfg.reset_settings_cache()
    spec = FilterSpec(
        cell_type=TermFilter(term="CL:0000236"),
        tissue=TermFilter(term="UBERON:0002048"),
        disease=TermFilter(term="MONDO:0100096"),
    )
    env = await aggregate_expression(
        spec,
        gene_ids=["ENSG00000141510", "ENSG00000146648"],
        group_by="cell_type",
    )
    rows = env.data["rows"]
    assert isinstance(rows, list) and rows, "expected at least one aggregated group"
    sample = rows[0]
    assert sample["group"]
    assert "mean" in sample or "fraction_expressing" in sample
    p = env.query_provenance
    assert p.census_version == "stable"
    assert p.execution_tier >= 2
    assert env.attribution
    assert env.unaffiliated


# --- preview_obs -------------------------------------------------------------


async def test_preview_obs_returns_capped_rows() -> None:
    spec = FilterSpec(cell_type=TermFilter(term="CL:0000236"))
    env = await preview_obs(spec, limit=5)
    data = env.data
    assert data["n_rows"] <= 5
    assert isinstance(data["rows"], list)
    assert env.defaults_applied.get("limit") == data["n_rows"]
    assert any("preview rows are a small sample" in w for w in env.warnings)


# --- gene_coverage -----------------------------------------------------------


async def test_gene_coverage_marks_known_genes_present() -> None:
    env = await gene_coverage(
        gene_ids=["ENSG00000141510", "ENSG00000999999"],  # TP53 + a fake ID
        organism="homo_sapiens",
    )
    rows = {row["gene_id"]: row for row in env.data["gene_coverage"]}
    assert rows["ENSG00000141510"]["present_in_var"] is True
    assert rows["ENSG00000141510"]["gene_symbol"] == "TP53"
    assert rows["ENSG00000999999"]["present_in_var"] is False
    # n_cells_with_gene is intentionally null; warning surfaces that.
    assert any("n_cells_with_gene" in w for w in env.warnings)


# --- expand_term -------------------------------------------------------------


@respx.mock
async def test_expand_term_exact_returns_single_term() -> None:
    ols = get_settings().ols_base.rstrip("/")
    respx.get(f"{ols}/search").mock(
        return_value=httpx.Response(
            200,
            json={"response": {"docs": [_ols_term_doc("CL:0000236", "B cell", "CL")]}},
        )
    )
    env = await expand_term("CL:0000236", direction="exact", in_census_only=False)
    data = env.data
    assert data["query_curie"] == "CL:0000236"
    assert data["query_label"] == "B cell"
    assert data["terms"] == ["CL:0000236"]
    assert env.call_id


# --- term_definition ---------------------------------------------------------


@respx.mock
async def test_term_definition_surfaces_label_and_description() -> None:
    ols = get_settings().ols_base.rstrip("/")
    respx.get(f"{ols}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "docs": [
                        _ols_term_doc(
                            "CL:0000236",
                            "B cell",
                            "CL",
                            definition="A lymphocyte of B lineage.",
                        )
                    ]
                }
            },
        )
    )
    env = await term_definition("CL:0000236")
    data = env.data
    assert data["curie"] == "CL:0000236"
    assert data["label"] == "B cell"
    assert data["definition"] == "A lymphocyte of B lineage."
    assert data["is_obsolete"] is False
