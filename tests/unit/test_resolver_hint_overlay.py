"""Resolver tests that exercise the hint overlay (no OLS network needed)."""

import pytest

from cxg_census_mcp.models.ontology import ResolutionRefusal, ResolvedTerm
from cxg_census_mcp.ontology.resolver import resolve


@pytest.mark.asyncio
async def test_hint_overlay_resolves_covid():
    result = await resolve("covid-19", facet="disease")
    assert isinstance(result, ResolvedTerm)
    assert result.curie == "MONDO:0100096"
    assert result.resolution_path == "hint-overlay"


@pytest.mark.asyncio
async def test_hint_overlay_resolves_b_cell():
    result = await resolve("B cell", facet="cell_type")
    assert isinstance(result, ResolvedTerm)
    assert result.curie == "CL:0000236"


@pytest.mark.asyncio
async def test_empty_text_refuses():
    result = await resolve("", facet="cell_type")
    assert isinstance(result, ResolutionRefusal)
    assert result.code == "TERM_NOT_FOUND"


@pytest.mark.asyncio
async def test_alias_resolves():
    result = await resolve("nsclc", facet="disease")
    assert isinstance(result, ResolvedTerm)
    assert result.curie == "MONDO:0008903"


@pytest.mark.asyncio
async def test_normalisation_handles_case_and_punctuation():
    result = await resolve("Alzheimer's Disease", facet="disease")
    assert isinstance(result, ResolvedTerm)
    assert result.curie == "MONDO:0004975"
