import pytest

from cxg_census_mcp.errors import CallIdNotFoundError
from cxg_census_mcp.models.filters import FilterSpec, TermFilter
from cxg_census_mcp.tools import count_cells, export_snippet


@pytest.mark.asyncio
async def test_export_snippet_round_trip_after_count():
    env = await count_cells(FilterSpec(cell_type=TermFilter(term="CL:0000236")))
    snippet_env = await export_snippet(env.call_id)
    code = snippet_env.data["snippet"]
    assert "cellxgene_census" in code
    assert "open_soma" in code
    assert "stable" in code  # census_version pinning baked in


@pytest.mark.asyncio
async def test_export_snippet_obs_only_intent_uses_get_obs():
    env = await count_cells(FilterSpec(cell_type=TermFilter(term="CL:0000236")))
    snippet_env = await export_snippet(env.call_id, intent="obs_only")
    assert "get_obs" in snippet_env.data["snippet"]
    assert snippet_env.data["intent"] == "obs_only"


@pytest.mark.asyncio
async def test_export_snippet_aggregate_uses_tiledbsoma_axis_query():
    env = await count_cells(FilterSpec(cell_type=TermFilter(term="CL:0000236")))
    snippet_env = await export_snippet(env.call_id, intent="aggregate")
    code = snippet_env.data["snippet"]
    assert "import tiledbsoma as soma" in code
    assert "soma.AxisQuery" in code
    assert "experimental" not in code


@pytest.mark.asyncio
async def test_export_snippet_unknown_call_id_raises():
    with pytest.raises(CallIdNotFoundError) as ei:
        await export_snippet("does-not-exist")
    assert ei.value.code == "CALL_ID_NOT_FOUND"


@pytest.mark.asyncio
async def test_export_snippet_includes_rewrite_comment_when_applied():
    env = await count_cells(FilterSpec(disease=TermFilter(term="MONDO:0100096")))
    snippet_env = await export_snippet(env.call_id)
    code = snippet_env.data["snippet"]
    assert "disease_multi_value_v7" in code
