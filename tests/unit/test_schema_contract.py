"""Tool JSON schemas stay aligned with Pydantic FilterSpec / tool models."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator, ValidationError

from cxg_census_mcp.models.filters import FilterSpec
from cxg_census_mcp.server import (
    TOOL_DESCRIPTORS,
    _filter_spec_schema,
    tool_accepts_progress,
)


def _validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema)


def test_all_tool_descriptors_have_valid_schemas():
    for tool in TOOL_DESCRIPTORS:
        Draft202012Validator.check_schema(tool.inputSchema)


def test_filter_spec_schema_accepts_minimal_filter():
    v = _validator(_filter_spec_schema())
    v.validate({"organism": "homo_sapiens"})
    FilterSpec.model_validate({"organism": "homo_sapiens"})


def test_filter_spec_schema_accepts_term_filter_by_text():
    v = _validator(_filter_spec_schema())
    payload = {
        "organism": "homo_sapiens",
        "cell_type": {"text": "B cell"},
    }
    v.validate(payload)
    FilterSpec.model_validate(payload)


def test_filter_spec_schema_accepts_multi_term_filter():
    v = _validator(_filter_spec_schema())
    payload = {
        "organism": "mus_musculus",
        "tissue": {"any_of": ["UBERON:0002048"], "expand": "descendants_inclusive"},
    }
    v.validate(payload)
    FilterSpec.model_validate(payload)


def test_filter_spec_schema_rejects_unknown_field():
    v = _validator(_filter_spec_schema())
    with pytest.raises(ValidationError):
        v.validate({"organism": "homo_sapiens", "unknown_field": 1})


def test_count_cells_schema_requires_filters():
    descriptor = next(t for t in TOOL_DESCRIPTORS if t.name == "count_cells")
    v = _validator(descriptor.inputSchema)
    with pytest.raises(ValidationError):
        v.validate({})
    v.validate({"filters": {"organism": "homo_sapiens"}})


def test_aggregate_expression_schema_requires_genes():
    descriptor = next(t for t in TOOL_DESCRIPTORS if t.name == "aggregate_expression")
    v = _validator(descriptor.inputSchema)
    with pytest.raises(ValidationError):
        v.validate({"filters": {"organism": "homo_sapiens"}})
    v.validate(
        {
            "filters": {"organism": "homo_sapiens"},
            "gene_ids": ["ENSG00000141510"],
        }
    )


def test_long_running_tools_accept_progress_and_cancel():
    for name in ("count_cells", "preview_obs", "aggregate_expression"):
        assert tool_accepts_progress(name), f"{name} should accept progress + cancel kwargs"
