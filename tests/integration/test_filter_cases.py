"""YAML-driven golden tests over filter resolution."""

import pytest
import yaml

from cxg_census_mcp.models.filters import FilterSpec
from cxg_census_mcp.tools import count_cells


def _load_cases():
    from pathlib import Path

    cases = yaml.safe_load(
        (Path(__file__).parent.parent / "fixtures" / "filter_cases.yaml").read_text()
    )
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
async def test_filter_case(case):
    spec = FilterSpec.model_validate(case["filters"])
    env = await count_cells(spec)
    expected = case["expected"]
    p = env.query_provenance

    if "tissue_strategy" in expected:
        assert p.tissue_strategy == expected["tissue_strategy"]
    if "rewrites_applied" in expected:
        for rule in expected["rewrites_applied"]:
            assert rule in p.schema_rewrites_applied
    if "is_primary_data" in expected:
        assert p.is_primary_data_applied is expected["is_primary_data"]
