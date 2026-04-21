"""Unit tests for the runtime metrics module."""

from __future__ import annotations

import pytest

from cxg_census_mcp import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset_for_tests()
    yield
    metrics.reset_for_tests()


def test_inc_tool_call_increments_counter():
    metrics.inc_tool_call("count_cells")
    metrics.inc_tool_call("count_cells")
    metrics.inc_tool_call("preview_obs")
    snap = metrics.snapshot()
    assert snap["tool_calls"] == {"count_cells": 2, "preview_obs": 1}


def test_inc_tool_error_keys_by_tool_and_code():
    metrics.inc_tool_error("count_cells", "TERM_NOT_FOUND")
    metrics.inc_tool_error("count_cells", "TERM_NOT_FOUND")
    metrics.inc_tool_error("aggregate_expression", "QUERY_TOO_LARGE")
    snap = metrics.snapshot()
    assert snap["tool_errors"] == {
        "count_cells|TERM_NOT_FOUND": 2,
        "aggregate_expression|QUERY_TOO_LARGE": 1,
    }


def test_cap_rejection_counters():
    metrics.inc_cap_rejection("expression_cells")
    metrics.inc_cap_rejection("tier1_cells")
    metrics.inc_cap_rejection("expression_cells")
    snap = metrics.snapshot()
    assert snap["cap_rejections"] == {"expression_cells": 2, "tier1_cells": 1}


def test_cancellation_counter():
    metrics.inc_cancellation()
    metrics.inc_cancellation()
    assert metrics.snapshot()["cancellations"] == 2


def test_render_prometheus_includes_all_sections():
    metrics.inc_tool_call("count_cells")
    metrics.inc_tool_error("count_cells", "TERM_NOT_FOUND")
    metrics.inc_cap_rejection("tier1_cells")
    metrics.inc_cancellation()

    out = metrics.render_prometheus()
    for marker in (
        "census_mcp_tool_calls_total",
        'tool="count_cells"',
        "census_mcp_tool_errors_total",
        'code="TERM_NOT_FOUND"',
        "census_mcp_cap_rejections_total",
        'kind="tier1_cells"',
        "census_mcp_cancellations_total",
        "census_mcp_ols_cache_hits_total",
        "census_mcp_facet_cache_hits_total",
        "census_mcp_plan_cache_size",
    ):
        assert marker in out, f"missing {marker} in:\n{out}"
