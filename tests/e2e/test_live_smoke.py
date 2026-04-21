"""Network smoke (``pytest -m live tests/e2e/test_live_smoke.py``)."""

import os

import pytest

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _live_env(monkeypatch):
    monkeypatch.setenv("CXG_CENSUS_MCP_MOCK_MODE", "0")
    yield


@pytest.mark.asyncio
async def test_live_resolve_b_cell():
    from cxg_census_mcp.models.ontology import ResolvedTerm
    from cxg_census_mcp.ontology.resolver import resolve

    result = await resolve("B cell", facet="cell_type")
    assert isinstance(result, ResolvedTerm)
    assert result.curie == "CL:0000236"


@pytest.mark.asyncio
async def test_live_term_definition_fetches_label():
    from cxg_census_mcp.tools import term_definition

    env = await term_definition("CL:0000236")
    assert env.data["label"]


@pytest.mark.asyncio
async def test_live_census_summary_has_total_cells():
    if not os.environ.get("CXG_CENSUS_MCP_LIVE_OK"):
        pytest.skip("Set CXG_CENSUS_MCP_LIVE_OK=1 to opt into Census reads.")
    from cxg_census_mcp.tools import census_summary

    env = await census_summary()
    assert int(env.data.get("total_cells", 0)) > 0
