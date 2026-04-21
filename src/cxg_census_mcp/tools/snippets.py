"""export_snippet — restart-safe runnable Python snippet emission."""

from __future__ import annotations

from typing import Literal

from cxg_census_mcp.errors import CallIdNotFoundError
from cxg_census_mcp.execution.snippet_emitter import emit_snippet
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.planner.plan_store import get_plan_store
from cxg_census_mcp.planner.query_plan import QueryPlan
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope


async def export_snippet(
    call_id: str,
    *,
    intent: Literal["anndata", "obs_only", "aggregate"] = "anndata",
) -> ResponseEnvelope:
    timer = TimedScope()
    raw = get_plan_store().get(call_id)
    if raw is None:
        raise CallIdNotFoundError(
            f"call_id not found in plan store: {call_id}",
            retry_with=None,
        )
    plan = QueryPlan.model_validate(raw)
    code = emit_snippet(plan, intent=intent)

    provenance = QueryProvenance(
        census_version=plan.census_version,
        schema_version=plan.schema_version,
        resolved_filters=plan.resolved_filters,
        value_filter=plan.value_filter,
        ontology_expansions=plan.expansion_traces,
        tissue_field_used=plan.tissue_field_used,
        tissue_strategy=plan.tissue_strategy,
        is_primary_data_applied=plan.is_primary_data_applied,
        schema_rewrites_applied=plan.schema_rewrites_applied,
        execution_tier=plan.execution_tier,
        estimated_cells_pre_query=plan.estimated_cell_count,
    )
    return build_envelope(
        data={"snippet": code, "intent": intent, "language": "python"},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        defaults_applied={"intent": intent},
    )
