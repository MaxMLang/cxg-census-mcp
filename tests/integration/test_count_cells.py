import pytest

from cxg_census_mcp.models.filters import FilterSpec, TermFilter
from cxg_census_mcp.tools import count_cells


@pytest.mark.asyncio
async def test_count_cells_returns_envelope_with_provenance():
    spec = FilterSpec(cell_type=TermFilter(term="CL:0000236"))
    env = await count_cells(spec)
    assert env.data["total"] >= 0
    p = env.query_provenance
    assert p.census_version == "stable"
    assert p.execution_tier == 0
    assert p.is_primary_data_applied is True
    assert "is_primary_data" in env.defaults_applied


@pytest.mark.asyncio
async def test_count_cells_grouped_by_dataset_returns_groups():
    spec = FilterSpec(cell_type=TermFilter(term="CL:0000236"))
    env = await count_cells(spec, group_by="dataset_id")
    by_group = env.data.get("by_group", [])
    assert isinstance(by_group, list)


@pytest.mark.asyncio
async def test_count_cells_call_id_is_deterministic():
    spec = FilterSpec(cell_type=TermFilter(term="CL:0000236"))
    a = await count_cells(spec)
    b = await count_cells(spec)
    assert a.call_id == b.call_id


@pytest.mark.asyncio
async def test_count_cells_lung_routes_to_general_tissue_column():
    spec = FilterSpec(
        cell_type=TermFilter(term="CL:0000236"),
        tissue=TermFilter(term="UBERON:0002048"),
    )
    env = await count_cells(spec)
    p = env.query_provenance
    assert p.tissue_field_used == "tissue_general_ontology_term_id"
    assert p.tissue_strategy == "tissue_general"


@pytest.mark.asyncio
async def test_count_cells_records_disease_rewrite_at_schema_7():
    spec = FilterSpec(disease=TermFilter(term="MONDO:0100096"))
    env = await count_cells(spec)
    assert "disease_multi_value_v7" in env.query_provenance.schema_rewrites_applied
