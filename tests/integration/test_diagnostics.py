import pytest

from cxg_census_mcp.tools import get_server_limits


@pytest.mark.asyncio
async def test_get_server_limits_reports_caps_and_runtime_stats():
    env = await get_server_limits()
    data = env.data

    assert "limits" in data
    limits = data["limits"]
    assert "max_tier1_cells" in limits
    assert "max_expression_genes" in limits
    assert env.query_provenance.execution_tier == 0

    assert "runtime_stats" in data
    stats = data["runtime_stats"]
    for key in (
        "tool_calls",
        "tool_errors",
        "cap_rejections",
        "cancellations",
        "ols_cache",
        "facet_cache",
        "plan_cache",
    ):
        assert key in stats
