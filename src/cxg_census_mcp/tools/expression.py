"""aggregate_expression — Tier 2 tool."""

from __future__ import annotations

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import CensusMCPError
from cxg_census_mcp.execution.enrichment import canonical_group_by, label_for_group
from cxg_census_mcp.execution.tier2_expression import run_tier2_expression
from cxg_census_mcp.models.filters import FilterSpec
from cxg_census_mcp.models.ontology import ResolutionRefusal
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.planner.plan_store import get_plan_store, make_call_id
from cxg_census_mcp.planner.query_plan import (
    expansion_warnings,
    plan_query,
    plan_to_serializable,
)
from cxg_census_mcp.progress import ProgressReporter, should_report
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope


async def aggregate_expression(
    filters: FilterSpec | dict,
    gene_ids: list[str],
    *,
    group_by: str = "cell_type",
    aggregations: list[str] | None = None,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    spec = FilterSpec.model_validate(filters) if isinstance(filters, dict) else filters
    group_by = canonical_group_by(group_by) or "cell_type_ontology_term_id"
    aggregations = aggregations or ["mean", "fraction_expressing"]

    summary = get_census_client().summary(s.census_version)
    schema_version = str(summary.get("schema_version") or "unknown")

    plan_or_refusal = await plan_query(
        spec,
        tool_kind="aggregate_expression",
        census_version=s.census_version,
        schema_version=schema_version,
        group_by=group_by,
        n_genes=len(gene_ids),
        gene_ids=gene_ids,
    )
    if isinstance(plan_or_refusal, ResolutionRefusal):
        raise CensusMCPError(
            plan_or_refusal.message,
            action_hint=plan_or_refusal.action_hint,
            retry_with=plan_or_refusal.retry_with,
            candidates=[c.model_dump() for c in plan_or_refusal.candidates],
        )
    plan = plan_or_refusal
    if plan.must_use_snippet:
        raise CensusMCPError(
            plan.refusal_reason or "Query exceeds caps; use export_snippet.",
            action_hint="Call export_snippet(call_id) and run locally.",
            retry_with={"call_id_hint": "use the call_id from this error's parent envelope"},
        )

    result = await run_tier2_expression(
        organism=spec.organism,
        census_version=s.census_version,
        value_filter=plan.value_filter,
        gene_ids=gene_ids,
        group_by=group_by,
        aggregations=aggregations,
        estimated_cells=plan.estimated_cell_count,
        estimated_groups=plan.estimated_group_count,
        progress=progress,
        cancel=cancel,
    )

    if result.rows:
        labels = await label_for_group(
            group_by,
            [r.group for r in result.rows],
            census_version=s.census_version,
        )
        for r in result.rows:
            r.group_label = labels.get(r.group)

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
        actual_cells_returned=result.n_cells_total,
        estimated_group_count=plan.estimated_group_count,
        actual_group_count=result.n_groups,
        estimated_runtime_ms=plan.estimated_runtime_ms,
        progress_supported=should_report(plan.estimated_runtime_ms),
    )
    call_id = make_call_id(plan.plan_hash, "aggregate_expression", s.census_version)
    get_plan_store().put(call_id=call_id, plan_json=plan_to_serializable(plan))
    return build_envelope(
        data=result.model_dump(),
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        warnings=expansion_warnings(plan),
        defaults_applied={
            "is_primary_data": spec.is_primary_data,
            "aggregations": aggregations,
        },
    )
