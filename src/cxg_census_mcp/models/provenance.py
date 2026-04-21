"""Envelope + ``query_provenance`` models for tool responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cxg_census_mcp import ATTRIBUTION, DISCLAIMER, UNAFFILIATED


class ResolvedFilterTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    input: str | list[str] | None
    curie: str | list[str] | None
    label: str | list[str] | None
    confidence: str | None = None
    expand: str | None = None


class ExpansionTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_curie: str
    query_label: str | None = None
    direction: str
    n_terms: int
    n_terms_total_in_ontology: int = 0
    n_terms_dropped_no_cells: int = 0
    dropped_terms_sample: tuple[str, ...] = Field(default_factory=tuple)
    truncated: bool = False
    truncation_reason: str | None = None


class QueryProvenance(BaseModel):
    """Resolved filters, tier, estimates vs actuals."""

    census_version: str
    schema_version: str
    resolved_filters: dict[str, ResolvedFilterTrace] = Field(default_factory=dict)
    value_filter: str
    ontology_expansions: list[ExpansionTrace] = Field(default_factory=list)
    tissue_field_used: str | None = None
    tissue_strategy: str | None = None
    is_primary_data_applied: bool = True
    schema_rewrites_applied: list[str] = Field(default_factory=list)
    execution_tier: int
    estimated_cells_pre_query: int | None = None
    actual_cells_returned: int | None = None
    estimated_group_count: int | None = None
    actual_group_count: int | None = None
    estimated_runtime_ms: int | None = None
    progress_supported: bool = False


class ResponseMeta(BaseModel):
    elapsed_ms: float
    cache_hits: dict[str, int] = Field(default_factory=dict)
    cache_misses: dict[str, int] = Field(default_factory=dict)
    server_version: str


class ResponseEnvelope(BaseModel):
    """Every tool response inherits this envelope structure."""

    data: Any
    query_provenance: QueryProvenance
    attribution: str = ATTRIBUTION
    disclaimer: str = DISCLAIMER
    unaffiliated: str = UNAFFILIATED
    call_id: str
    meta: ResponseMeta
    warnings: list[str] = Field(default_factory=list)
    defaults_applied: dict[str, Any] = Field(default_factory=dict)
