from cxg_census_mcp.config import get_settings
from cxg_census_mcp.planner.tier_router import route_tier


def test_count_kind_is_tier0():
    tier, refusal = route_tier(tool_kind="count", estimated_cells=100, estimated_runtime_ms=1)
    assert tier == 0 and refusal is None


def test_obs_scan_within_caps_is_tier1():
    s = get_settings()
    tier, refusal = route_tier(
        tool_kind="obs_scan",
        estimated_cells=s.max_tier1_cells // 2,
        estimated_runtime_ms=s.max_tier1_runtime_ms // 2,
    )
    assert tier == 1 and refusal is None


def test_obs_scan_over_cells_cap_routes_to_snippet():
    s = get_settings()
    tier, refusal = route_tier(
        tool_kind="obs_scan",
        estimated_cells=s.max_tier1_cells * 2,
        estimated_runtime_ms=1,
    )
    assert tier == 9
    assert refusal and "exceeds Tier-1 cap" in refusal


def test_obs_scan_over_runtime_cap_routes_to_snippet():
    s = get_settings()
    tier, refusal = route_tier(
        tool_kind="obs_scan",
        estimated_cells=10,
        estimated_runtime_ms=s.max_tier1_runtime_ms * 2,
    )
    assert tier == 9
    assert refusal and "runtime" in refusal


def test_aggregate_too_many_genes():
    s = get_settings()
    tier, refusal = route_tier(
        tool_kind="aggregate_expression",
        estimated_cells=10,
        estimated_runtime_ms=1,
        n_genes=s.max_expression_genes + 1,
    )
    assert tier == 9
    assert refusal and "genes" in refusal


def test_aggregate_too_many_groups():
    s = get_settings()
    tier, refusal = route_tier(
        tool_kind="aggregate_expression",
        estimated_cells=10,
        estimated_runtime_ms=1,
        n_genes=1,
        estimated_groups=s.max_expression_groups + 1,
    )
    assert tier == 9
    assert refusal and "Group cardinality" in refusal


def test_aggregate_within_caps_is_tier2():
    tier, refusal = route_tier(
        tool_kind="aggregate_expression",
        estimated_cells=1000,
        estimated_runtime_ms=100,
        n_genes=5,
        estimated_groups=10,
    )
    assert tier == 2 and refusal is None
