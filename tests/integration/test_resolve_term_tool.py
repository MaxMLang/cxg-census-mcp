import pytest

from cxg_census_mcp.tools import resolve_term


@pytest.mark.asyncio
async def test_resolve_term_via_hint_overlay():
    env = await resolve_term(text="covid-19", facet="disease")
    payload = env.data["result"]
    assert env.data["kind"] == "ResolvedTerm"
    assert payload["curie"] == "MONDO:0100096"
    assert payload["resolution_path"] in {"hint-overlay", "exact-curie"}


@pytest.mark.asyncio
async def test_resolve_term_empty_text_returns_refusal_payload():
    env = await resolve_term(text="", facet="cell_type")
    assert env.data["kind"] == "ResolutionRefusal"
    assert env.data["result"]["code"] == "TERM_NOT_FOUND"
