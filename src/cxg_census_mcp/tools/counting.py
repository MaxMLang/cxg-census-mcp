"""count_cells, list_datasets, gene_coverage."""

from __future__ import annotations

from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import CensusMCPError
from cxg_census_mcp.execution.enrichment import canonical_group_by, label_for_group
from cxg_census_mcp.execution.tier0_summary import (
    run_tier0_count,
    run_tier0_datasets,
)
from cxg_census_mcp.execution.tier1_obs import run_tier1_obs
from cxg_census_mcp.models.counts import GeneCoverage
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


async def count_cells(
    filters: FilterSpec | dict,
    *,
    group_by: str | None = None,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    spec = FilterSpec.model_validate(filters) if isinstance(filters, dict) else filters
    group_by = canonical_group_by(group_by)

    summary = get_census_client().summary(s.census_version)
    schema_version = str(summary.get("schema_version") or "unknown")

    plan_or_refusal = await plan_query(
        spec,
        tool_kind="count",
        census_version=s.census_version,
        schema_version=schema_version,
        group_by=group_by,
    )
    if isinstance(plan_or_refusal, ResolutionRefusal):
        raise CensusMCPError(
            plan_or_refusal.message,
            action_hint=plan_or_refusal.action_hint,
            retry_with=plan_or_refusal.retry_with,
            candidates=[c.model_dump() for c in plan_or_refusal.candidates],
        )
    plan = plan_or_refusal

    if plan.execution_tier <= 0:
        result = run_tier0_count(
            organism=spec.organism,
            census_version=s.census_version,
            value_filter=plan.value_filter,
            group_by=group_by,
        )
    else:
        result = await run_tier1_obs(
            organism=spec.organism,
            census_version=s.census_version,
            value_filter=plan.value_filter,
            estimated_cells=plan.estimated_cell_count,
            estimated_runtime_ms=plan.estimated_runtime_ms,
            group_by=group_by,
            progress=progress,
            cancel=cancel,
        )

    if group_by and result.by_group:
        labels = await label_for_group(
            group_by,
            [g.group for g in result.by_group],
            census_version=s.census_version,
        )
        for g in result.by_group:
            g.label = labels.get(g.group)

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
        actual_cells_returned=result.total,
        estimated_group_count=plan.estimated_group_count,
        actual_group_count=result.n_groups,
        estimated_runtime_ms=plan.estimated_runtime_ms,
        progress_supported=should_report(plan.estimated_runtime_ms),
    )

    call_id = make_call_id(plan.plan_hash, "count_cells", s.census_version)
    get_plan_store().put(call_id=call_id, plan_json=plan_to_serializable(plan))
    return build_envelope(
        data=result.model_dump(),
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        warnings=expansion_warnings(plan),
        defaults_applied={"is_primary_data": spec.is_primary_data},
    )


async def list_datasets(
    filters: FilterSpec | dict,
    *,
    limit: int = 100,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    spec = FilterSpec.model_validate(filters) if isinstance(filters, dict) else filters

    summary = get_census_client().summary(s.census_version)
    schema_version = str(summary.get("schema_version") or "unknown")

    plan_or_refusal = await plan_query(
        spec,
        tool_kind="list_datasets",
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

    rows = run_tier0_datasets(
        organism=spec.organism,
        census_version=s.census_version,
        value_filter=plan.value_filter,
        limit=limit,
    )

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
        actual_cells_returned=sum(r.n_cells or 0 for r in rows),
    )
    call_id = make_call_id(plan.plan_hash, "list_datasets", s.census_version)
    get_plan_store().put(call_id=call_id, plan_json=plan_to_serializable(plan))
    return build_envelope(
        data={"datasets": [r.model_dump() for r in rows], "n_datasets": len(rows)},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        warnings=expansion_warnings(plan),
        defaults_applied={"is_primary_data": spec.is_primary_data, "limit": limit},
    )


async def gene_coverage(
    gene_ids: list[str],
    *,
    organism: str = "homo_sapiens",
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    client = get_census_client()
    info = client.gene_presence_summary(
        version=s.census_version, organism=organism, gene_ids=gene_ids
    )
    out = [
        GeneCoverage(
            gene_id=gid,
            gene_symbol=info[gid]["feature_name"],
            organism=organism,
            n_cells_with_gene=None,
            n_datasets_with_gene=info[gid]["n_datasets"],
            present_in_var=info[gid]["present_in_var"],
        ).model_dump()
        for gid in gene_ids
    ]
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="unknown",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = "gene_coverage:" + str(hash(tuple(gene_ids)))[:16]
    return build_envelope(
        data={"gene_coverage": out, "organism": organism},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        warnings=[
            "n_cells_with_gene is intentionally null; computing it requires a "
            "full X scan. Use export_snippet for local computation if needed.",
        ],
    )
