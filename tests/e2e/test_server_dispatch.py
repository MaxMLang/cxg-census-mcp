"""Mock-mode end-to-end: dispatch through the same router the MCP SDK uses."""

import json

import pytest

from cxg_census_mcp.server import _route


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_route_census_summary():
    env = await _route("census_summary", {})
    assert env.data["census_version"] == "stable"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_route_count_cells_with_text_resolution():
    env = await _route(
        "count_cells",
        {
            "filters": {
                "organism": "homo_sapiens",
                "disease": {"text": "covid-19"},
                "tissue": {"text": "lung"},
            }
        },
    )
    assert env.data["total"] >= 0
    assert env.query_provenance.tissue_strategy == "tissue_general"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_route_export_snippet_after_count():
    count_env = await _route(
        "count_cells",
        {"filters": {"organism": "homo_sapiens", "cell_type": {"term": "CL:0000236"}}},
    )
    snippet_env = await _route("export_snippet", {"call_id": count_env.call_id})
    assert "cellxgene_census" in snippet_env.data["snippet"]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_route_unknown_tool_raises():
    from cxg_census_mcp.errors import CensusMCPError

    with pytest.raises(CensusMCPError):
        await _route("not_a_tool", {})


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_envelope_serialises_to_json():
    env = await _route("census_summary", {})
    payload = env.model_dump(mode="json")
    json.dumps(payload)  # smoke test: no non-serialisable content
