"""preview_obs — cheap obs preview before launching a Tier-1 scan."""

from __future__ import annotations

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import CensusMCPError
from cxg_census_mcp.execution.enrichment import enrich_obs_rows
from cxg_census_mcp.execution.preview import preview_obs as run_preview
from cxg_census_mcp.models.filters import FilterSpec
from cxg_census_mcp.models.ontology import ResolutionRefusal
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.planner.plan_store import get_plan_store, make_call_id
from cxg_census_mcp.planner.query_plan import (
    expansion_warnings,
    plan_query,
    plan_to_serializable,
)
from cxg_census_mcp.progress import ProgressReporter
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope


async def preview_obs(
    filters: FilterSpec | dict,
    *,
    columns: list[str] | None = None,
    limit: int | None = None,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
) -> ResponseEnvelope:
    _ = progress, cancel  # preview_obs is bounded so progress/cancel are no-ops here
    timer = TimedScope()
    s = get_settings()
    spec = FilterSpec.model_validate(filters) if isinstance(filters, dict) else filters
    spec = spec.model_copy(update={"preview_only": True})

    summary = get_census_client().summary(s.census_version)
    schema_version = str(summary.get("schema_version") or "unknown")

    plan_or_refusal = await plan_query(
        spec,
        tool_kind="obs_preview",
        census_version=s.census_version,
        schema_version=schema_version,
    )
    if isinstance(plan_or_refusal, ResolutionRefusal):
        raise CensusMCPError(
            plan_or_refusal.message,
            action_hint=plan_or_refusal.action_hint,
            retry_with=plan_or_refusal.retry_with,
            candidates=[c.model_dump() for c in plan_or_refusal.candidates],
        )
    plan = plan_or_refusal

    preview = run_preview(
        organism=spec.organism,
        census_version=s.census_version,
        value_filter=plan.value_filter,
        columns=columns,
        limit=limit,
    )

    preview.rows = await enrich_obs_rows(preview.rows, census_version=s.census_version)

    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version=schema_version,
        resolved_filters=plan.resolved_filters,
        value_filter=plan.value_filter,
        ontology_expansions=plan.expansion_traces,
        tissue_field_used=plan.tissue_field_used,
        tissue_strategy=plan.tissue_strategy,
        is_primary_data_applied=plan.is_primary_data_applied,
        schema_rewrites_applied=plan.schema_rewrites_applied,
        execution_tier=plan.execution_tier,
        estimated_cells_pre_query=plan.estimated_cell_count,
        actual_cells_returned=preview.n_rows,
    )
    call_id = make_call_id(plan.plan_hash, "preview_obs", s.census_version)
    get_plan_store().put(call_id=call_id, plan_json=plan_to_serializable(plan))
    return build_envelope(
        data=preview.model_dump(),
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        defaults_applied={
            "is_primary_data": spec.is_primary_data,
            "limit": preview.n_rows,
        },
        warnings=[
            "preview rows are a small sample; cardinality_hints are lower bounds only.",
            *expansion_warnings(plan),
        ],
    )
