"""Resolver tests covering OLS multi-candidate ranking via mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from cxg_census_mcp.clients.ols import get_ols_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.models.ontology import ResolutionRefusal, ResolvedTerm
from cxg_census_mcp.ontology.resolver import resolve

pytestmark = pytest.mark.asyncio


def _docs(*entries: dict) -> dict:
    return {"response": {"docs": list(entries)}}


def _hit(curie: str, label: str, ontology: str = "CL", **extras) -> dict:
    return {
        "obo_id": curie,
        "label": label,
        "ontology_prefix": ontology,
        "synonym": extras.pop("synonym", []),
        "is_obsolete": extras.pop("is_obsolete", False),
        **extras,
    }


@respx.mock
async def test_ranks_exact_label_above_fuzzy():
    """An exact label hit beats a partially-matching fuzzy hit."""
    ols_url = get_settings().ols_base.rstrip("/")
    # Pick a query NOT in the local hint overlay so OLS is consulted.
    respx.get(f"{ols_url}/search").mock(
        return_value=httpx.Response(
            200,
            json=_docs(_hit("CL:0000084", "T cell receptor positive cell", ontology="CL")),
        )
    )
    res = await resolve("T cell receptor positive cell", facet="cell_type")
    assert isinstance(res, ResolvedTerm)
    assert res.curie == "CL:0000084"
    assert res.confidence == "label_match"


@respx.mock
async def test_multiple_exact_label_hits_refuses_with_candidates():
    """If OLS returns >1 exact-label hit the resolver must refuse, not guess."""
    ols_url = get_settings().ols_base.rstrip("/")
    respx.get(f"{ols_url}/search").mock(
        return_value=httpx.Response(
            200,
            json=_docs(
                _hit("CL:0000236", "lymphocyte", ontology="CL"),
                _hit("CL:0000084", "lymphocyte", ontology="CL"),
            ),
        )
    )
    res = await resolve("lymphocyte", facet="cell_type")
    assert isinstance(res, ResolvedTerm) is False
    assert isinstance(res, ResolutionRefusal)
    assert res.code == "TERM_AMBIGUOUS"
    assert {c.curie for c in res.candidates} == {"CL:0000236", "CL:0000084"}


@respx.mock
async def test_fuzzy_ranking_picks_highest_score_when_gap_is_clear():
    """When exact hit list is empty but fuzzy returns a clear winner, accept it."""
    ols_url = get_settings().ols_base.rstrip("/")
    get_ols_client.cache_clear()
    respx.get(f"{ols_url}/search", params={"exact": "true"}).mock(
        return_value=httpx.Response(200, json=_docs())
    )
    # Top hit: matches BOTH label and a synonym exactly (5.0) and is in the
    # facet catalog (no presence penalty). Others fuzz-score far below.
    respx.get(f"{ols_url}/search", params={"exact": "false"}).mock(
        return_value=httpx.Response(
            200,
            json=_docs(
                _hit(
                    "CL:0000236",
                    "naive b lymphocyte",
                    ontology="CL",
                    synonym=["naive b lymphocyte"],
                ),
                _hit("CL:0000540", "neuron", ontology="CL"),
            ),
        )
    )
    res = await resolve("naive b lymphocyte", facet="cell_type")
    assert isinstance(res, ResolvedTerm)
    assert res.curie == "CL:0000236"
    assert res.confidence == "fuzzy"


@respx.mock
async def test_fuzzy_no_clear_winner_refuses_with_candidates():
    """When two fuzzy candidates score within 1.0 of each other, refuse."""
    ols_url = get_settings().ols_base.rstrip("/")
    get_ols_client.cache_clear()
    # Exact path returns nothing.
    respx.get(f"{ols_url}/search", params={"exact": "true"}).mock(
        return_value=httpx.Response(200, json=_docs())
    )
    # Two fuzzy hits both far from query → small score gap.
    respx.get(f"{ols_url}/search", params={"exact": "false"}).mock(
        return_value=httpx.Response(
            200,
            json=_docs(
                _hit("CL:0000236", "alpha cell", ontology="CL"),
                _hit("CL:0000084", "beta cell", ontology="CL"),
            ),
        )
    )
    res = await resolve("gamma cell", facet="cell_type")
    assert isinstance(res, ResolutionRefusal)
    assert res.code == "TERM_AMBIGUOUS"
    assert len(res.candidates) >= 2


@respx.mock
async def test_no_hits_at_all_returns_term_not_found():
    ols_url = get_settings().ols_base.rstrip("/")
    get_ols_client.cache_clear()
    respx.get(f"{ols_url}/search").mock(return_value=httpx.Response(200, json=_docs()))
    res = await resolve("xyzzy nonexistent term qqq", facet="cell_type")
    assert isinstance(res, ResolutionRefusal)
    assert res.code == "TERM_NOT_FOUND"


@respx.mock
async def test_ols_outage_falls_back_to_hint_overlay():
    ols_url = get_settings().ols_base.rstrip("/")
    get_ols_client.cache_clear()
    # First exact-search 5xx -> client raises OntologyUnavailableError -> hint fallback
    respx.get(f"{ols_url}/search").mock(return_value=httpx.Response(503, json={"error": "down"}))
    res = await resolve("MS", facet="disease")
    # MS is in the hint overlay (Multiple Sclerosis -> MONDO:...).
    assert isinstance(res, ResolvedTerm)
    assert res.curie.startswith("MONDO:")
    assert res.resolution_path.startswith("hint")
