import pytest

from cxg_census_mcp.tools import (
    census_summary,
    get_census_versions,
    list_available_values,
)


@pytest.mark.asyncio
async def test_census_summary_returns_envelope():
    env = await census_summary()
    assert env.data["census_version"] == "stable"
    assert env.query_provenance.execution_tier == 0
    assert env.attribution
    assert env.disclaimer
    assert env.call_id
    assert env.meta.server_version


@pytest.mark.asyncio
async def test_get_census_versions_includes_pinned_version():
    env = await get_census_versions()
    versions = env.data["versions"]
    assert any(v["version"] == "stable" for v in versions)


@pytest.mark.asyncio
async def test_list_available_values_lists_cell_types():
    env = await list_available_values(column="cell_type_ontology_term_id")
    values = [v["value"] for v in env.data["values"]]
    assert "CL:0000236" in values  # B cell, seeded in mock catalog


@pytest.mark.asyncio
async def test_list_available_values_supports_prefix():
    env = await list_available_values(
        column="disease_ontology_term_id",
        prefix="MONDO:",
    )
    values = [v["value"] for v in env.data["values"]]
    assert all(v.startswith("MONDO:") for v in values)
