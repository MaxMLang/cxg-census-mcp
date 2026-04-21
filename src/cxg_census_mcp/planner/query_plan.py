"""Build a fully-resolved :class:`QueryPlan` from a :class:`FilterSpec`."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cxg_census_mcp.clients.census import CensusClient, get_census_client
from cxg_census_mcp.clients.ols import OLSClient, get_ols_client
from cxg_census_mcp.errors import InvalidFilterError
from cxg_census_mcp.models.filters import (
    FilterSpec,
    MultiTermFilter,
    TermFilter,
)
from cxg_census_mcp.models.ontology import (
    ExpandedTerm,
    ResolutionRefusal,
    ResolvedTerm,
)
from cxg_census_mcp.models.provenance import (
    ExpansionTrace,
    ResolvedFilterTrace,
)
from cxg_census_mcp.ontology.expander import expand
from cxg_census_mcp.ontology.registry import column_for, ontology_for_facet
from cxg_census_mcp.ontology.resolver import resolve
from cxg_census_mcp.ontology.rewrites import RewriteContext, apply_rewrites
from cxg_census_mcp.ontology.tissue_router import TissueRouting, pick_tissue_column
from cxg_census_mcp.planner.cardinality_estimator import estimate_group_count
from cxg_census_mcp.planner.cost_estimator import CostEstimate, estimate_cost, runtime_for_tier
from cxg_census_mcp.planner.filter_spec import validate_group_by
from cxg_census_mcp.planner.tier_router import ToolKind, route_tier
from cxg_census_mcp.utils import soma_filter as sf
from cxg_census_mcp.utils.curie import is_curie
from cxg_census_mcp.utils.stable_hash import stable_hash


class QueryPlan(BaseModel):
    value_filter: str
    columns_used: list[str] = Field(default_factory=list)
    tissue_field_used: str | None = None
    tissue_strategy: str | None = None
    resolved_filters: dict[str, ResolvedFilterTrace] = Field(default_factory=dict)
    ontology_expansions: list[ExpandedTerm] = Field(default_factory=list)
    expansion_traces: list[ExpansionTrace] = Field(default_factory=list)
    schema_rewrites_applied: list[str] = Field(default_factory=list)
    estimated_cell_count: int | None = None
    estimated_group_count: int | None = None
    estimated_runtime_ms: int | None = None
    execution_tier: Literal[0, 1, 2, 9] = 0
    must_use_snippet: bool = False
    refusal_reason: str | None = None
    organism: str
    census_version: str
    schema_version: str
    plan_hash: str
    is_primary_data_applied: bool = True
    group_by: list[str] | None = None
    n_genes: int = 0
    gene_ids: list[str] = Field(default_factory=list)


_FACETS = (
    "cell_type",
    "tissue",
    "disease",
    "assay",
    "development_stage",
    "self_reported_ethnicity",
)


async def plan_query(
    spec: FilterSpec,
    *,
    tool_kind: ToolKind,
    census_version: str,
    schema_version: str,
    group_by: str | list[str] | None = None,
    n_genes: int = 0,
    gene_ids: list[str] | None = None,
    ols_client: OLSClient | None = None,
    census_client: CensusClient | None = None,
) -> QueryPlan | ResolutionRefusal:
    """Build a plan, or short-circuit with a :class:`ResolutionRefusal`."""
    ols_client = ols_client or get_ols_client()
    census_client = census_client or get_census_client()
    ctx = RewriteContext(census_version=census_version, schema_version=schema_version)

    resolved_traces: dict[str, ResolvedFilterTrace] = {}
    expansions: list[ExpandedTerm] = []
    expansion_traces: list[ExpansionTrace] = []
    rewrites_applied: list[str] = []
    columns_used: set[str] = set()
    predicates: list[str] = []
    tissue_routing: TissueRouting | None = None
    resolved_filters_for_cost: dict[str, list[str]] = {}

    for facet in _FACETS:
        value = getattr(spec, facet, None)
        if value is None:
            continue

        resolved_curies: list[str] = []
        labels: list[str] = []
        confidences: list[str] = []
        expand_dir = "exact"

        if isinstance(value, MultiTermFilter):
            expand_dir = value.expand
            for entry in value.any_of:
                r = await _resolve_single(
                    entry, facet, value.confirm_ambiguous, census_version, spec.organism, ols_client
                )
                if isinstance(r, ResolutionRefusal):
                    return r
                resolved_curies.append(r.curie)
                labels.append(r.label)
                confidences.append(r.confidence)
        elif isinstance(value, TermFilter):
            entry = value.term or value.text  # type: ignore[assignment]
            assert entry is not None
            expand_dir = value.expand
            r = await _resolve_single(
                entry, facet, value.confirm_ambiguous, census_version, spec.organism, ols_client
            )
            if isinstance(r, ResolutionRefusal):
                return r
            resolved_curies = [r.curie]
            labels = [r.label]
            confidences = [r.confidence]
        else:
            continue

        # Expansion
        all_terms: list[str] = []
        for cur in resolved_curies:
            exp = await expand(
                cur,
                direction=expand_dir,
                in_census_only=True,
                census_version=census_version,
                organism=spec.organism,
                facet=facet,
                client=ols_client,
            )
            expansions.append(exp)
            n_dropped = len(exp.terms_missing_from_census)
            n_total = len(exp.terms) + n_dropped
            expansion_traces.append(
                ExpansionTrace(
                    query_curie=exp.query_curie,
                    query_label=exp.query_label,
                    direction=exp.direction,
                    n_terms=len(exp.terms),
                    n_terms_total_in_ontology=n_total,
                    n_terms_dropped_no_cells=n_dropped,
                    dropped_terms_sample=tuple(exp.terms_missing_from_census[:10]),
                    truncated=exp.terms_truncated,
                    truncation_reason=exp.truncation_reason,
                )
            )
            all_terms.extend(exp.terms)

        # Tissue routing happens here, before column selection.
        if facet == "tissue":
            primary = expansions[-len(resolved_curies)]
            tissue_routing = pick_tissue_column(resolved_curies[0], primary)

        # Column selection
        prefix = resolved_curies[0].split(":", 1)[0]
        try:
            cols = column_for(prefix, facet=facet)
        except KeyError as exc:
            raise InvalidFilterError(
                f"No Census column known for facet={facet} prefix={prefix}"
            ) from exc

        # Empty in_() is invalid; use a fake CURIE so curie_in() accepts it.
        sentinel_terms = ["CENSUSMCPNULL:0000000"]
        emit_terms = all_terms or sentinel_terms

        if facet == "tissue" and tissue_routing is not None:
            if tissue_routing.strategy == "tissue_general":
                col = "tissue_general_ontology_term_id"
                columns_used.add(col)
                pred, applied = apply_rewrites(ctx, column=col, operator="in", value=emit_terms)
                predicates.append(pred)
                rewrites_applied.extend(applied)
                resolved_filters_for_cost[col] = all_terms
            elif tissue_routing.strategy == "dual_column":
                spec_col = "tissue_ontology_term_id"
                gen_col = "tissue_general_ontology_term_id"
                columns_used.update({spec_col, gen_col})
                pred_specific, ap1 = apply_rewrites(
                    ctx, column=spec_col, operator="in", value=emit_terms
                )
                pred_general, ap2 = apply_rewrites(
                    ctx, column=gen_col, operator="in", value=emit_terms
                )
                predicates.append(sf.or_(pred_specific, pred_general))
                rewrites_applied.extend([*ap1, *ap2])
                resolved_filters_for_cost[spec_col] = all_terms
            else:
                col = "tissue_ontology_term_id"
                columns_used.add(col)
                pred, applied = apply_rewrites(ctx, column=col, operator="in", value=emit_terms)
                predicates.append(pred)
                rewrites_applied.extend(applied)
                resolved_filters_for_cost[col] = all_terms
        else:
            col = cols["id_col"]
            columns_used.add(col)
            pred, applied = apply_rewrites(ctx, column=col, operator="in", value=emit_terms)
            predicates.append(pred)
            rewrites_applied.extend(applied)
            resolved_filters_for_cost[col] = all_terms

        resolved_traces[facet] = ResolvedFilterTrace(
            field=facet,
            input=labels[0] if len(labels) == 1 else labels,
            curie=resolved_curies[0] if len(resolved_curies) == 1 else resolved_curies,
            label=labels[0] if len(labels) == 1 else labels,
            confidence=confidences[0] if len(confidences) == 1 else ",".join(confidences),
            expand=expand_dir,
        )

    # Categorical filters
    if spec.sex is not None:
        predicates.append(sf.eq("sex", spec.sex))
        columns_used.add("sex")
        resolved_traces["sex"] = ResolvedFilterTrace(
            field="sex", input=spec.sex, curie=None, label=spec.sex, confidence="literal"
        )

    if spec.suspension_type is not None:
        predicates.append(sf.eq("suspension_type", spec.suspension_type))
        columns_used.add("suspension_type")
        resolved_traces["suspension_type"] = ResolvedFilterTrace(
            field="suspension_type",
            input=spec.suspension_type,
            curie=None,
            label=spec.suspension_type,
            confidence="literal",
        )

    if spec.dataset_id is not None:
        ids = [spec.dataset_id] if isinstance(spec.dataset_id, str) else spec.dataset_id
        predicates.append(sf.in_("dataset_id", ids))
        columns_used.add("dataset_id")
        resolved_filters_for_cost["dataset_id"] = list(ids)
        resolved_traces["dataset_id"] = ResolvedFilterTrace(
            field="dataset_id", input=ids, curie=None, label=ids, confidence="literal"
        )

    if spec.donor_id is not None:
        ids = [spec.donor_id] if isinstance(spec.donor_id, str) else spec.donor_id
        predicates.append(sf.in_("donor_id", ids))
        columns_used.add("donor_id")
        resolved_filters_for_cost["donor_id"] = list(ids)
        resolved_traces["donor_id"] = ResolvedFilterTrace(
            field="donor_id", input=ids, curie=None, label=ids, confidence="literal"
        )

    if spec.is_primary_data:
        predicates.append(sf.eq("is_primary_data", True))
        columns_used.add("is_primary_data")

    value_filter = sf.and_(*predicates)

    group_by_cols = validate_group_by(group_by)

    cost = estimate_cost(
        organism=spec.organism,
        census_version=census_version,
        resolved_filters=resolved_filters_for_cost,
    )
    n_groups = estimate_group_count(
        organism=spec.organism,
        census_version=census_version,
        group_by=group_by_cols[0] if group_by_cols else None,
        resolved_filters=resolved_filters_for_cost,
    )

    tier, refusal = route_tier(
        tool_kind=tool_kind,
        estimated_cells=cost.estimated_cells,
        estimated_runtime_ms=cost.estimated_runtime_ms,
        n_genes=n_genes,
        estimated_groups=n_groups,
    )

    # Rollup can wildly overcount (marginals aren't joint). Re-check with n_obs.
    if (
        refusal is not None
        and tier == 9
        and cost.estimated_cells is not None
        and len(resolved_filters_for_cost) >= 2
        and not census_client.is_mock
    ):
        try:
            exact = census_client.count_obs(
                version=census_version,
                organism=spec.organism,
                value_filter=value_filter,
            )
        except Exception:
            exact = None
        if exact is not None:
            cost = CostEstimate(
                estimated_cells=exact,
                estimated_runtime_ms=int(exact * 0.005),
                coarse=False,
            )
            tier, refusal = route_tier(
                tool_kind=tool_kind,
                estimated_cells=cost.estimated_cells,
                estimated_runtime_ms=cost.estimated_runtime_ms,
                n_genes=n_genes,
                estimated_groups=n_groups,
            )

    plan_hash = stable_hash(
        value_filter,
        sorted(columns_used),
        spec.organism,
        census_version,
        schema_version,
        sorted(rewrites_applied),
    )

    return QueryPlan(
        value_filter=value_filter,
        columns_used=sorted(columns_used),
        tissue_field_used=(tissue_routing.column if tissue_routing else None),
        tissue_strategy=(tissue_routing.strategy if tissue_routing else None),
        resolved_filters=resolved_traces,
        ontology_expansions=expansions,
        expansion_traces=expansion_traces,
        schema_rewrites_applied=sorted(set(rewrites_applied)),
        estimated_cell_count=cost.estimated_cells,
        estimated_group_count=n_groups,
        estimated_runtime_ms=runtime_for_tier(tier, cost.estimated_cells),
        execution_tier=tier,
        must_use_snippet=(tier == 9),
        refusal_reason=refusal,
        organism=spec.organism,
        census_version=census_version,
        schema_version=schema_version,
        plan_hash=plan_hash,
        is_primary_data_applied=spec.is_primary_data,
        group_by=group_by_cols,
        n_genes=n_genes,
        gene_ids=list(gene_ids or []),
    )


async def _resolve_single(
    entry: str,
    facet: str,
    confirm_ambiguous: bool,
    census_version: str,
    organism: str,
    ols_client: OLSClient,
) -> ResolvedTerm | ResolutionRefusal:
    if is_curie(entry):
        return await resolve(
            entry,
            ontology=ontology_for_facet(facet),
            facet=facet,
            census_version=census_version,
            organism=organism,
            client=ols_client,
        )
    return await resolve(
        entry,
        ontology=ontology_for_facet(facet),
        facet=facet,
        confirm_ambiguous=confirm_ambiguous,
        census_version=census_version,
        organism=organism,
        client=ols_client,
    )


def plan_to_serializable(plan: QueryPlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")


def expansion_warnings(plan: QueryPlan) -> list[str]:
    """Warn when expansion collapses because harmonized obs rarely use child terms."""
    warnings: list[str] = []
    for tr in plan.expansion_traces:
        label = tr.query_label or tr.query_curie
        if tr.n_terms == 0:
            sample = ", ".join(tr.dropped_terms_sample[:5])
            more = (
                f" (e.g. {sample}{', ...' if tr.n_terms_dropped_no_cells > 5 else ''})"
                if sample
                else ""
            )
            warnings.append(
                f"{tr.query_curie} ('{label}') is not present in this Census "
                f"version's harmonized field, and {tr.n_terms_dropped_no_cells} "
                f"of its ontology relatives ({tr.direction}) are also absent"
                f"{more}. The query will return zero cells. Try a sibling or "
                f"parent CURIE via expand_term, inspect raw annotations with "
                f"preview_obs(columns=['author_cell_type', 'author_cluster_label']), "
                f"or call list_available_values to see which terms ARE populated."
            )
            continue
        if tr.direction == "exact" or tr.n_terms_dropped_no_cells == 0:
            continue
        if tr.n_terms == 1:
            sample = ", ".join(tr.dropped_terms_sample[:5])
            more = (
                f" (e.g. {sample}{', ...' if tr.n_terms_dropped_no_cells > 5 else ''})"
                if sample
                else ""
            )
            warnings.append(
                f"Expansion '{tr.direction}' of {tr.query_curie} ('{label}') was a "
                f"no-op: all {tr.n_terms_dropped_no_cells} ontology descendants are "
                f"absent from this Census version's harmonized field, so the filter "
                f"reduces to just {tr.query_curie}{more}. Datasets contributing to "
                f"Census harmonize cell types to whatever label the submitters used; "
                f"finer subtypes are typically only available in raw author "
                f"annotations. Use preview_obs to inspect dataset-specific columns "
                f"like 'author_cell_type', or query individual datasets via "
                f"list_datasets + dataset_id to find subtype-resolved cohorts."
            )
        else:
            warnings.append(
                f"Expansion '{tr.direction}' of {tr.query_curie} ('{label}') kept "
                f"{tr.n_terms}/{tr.n_terms_total_in_ontology} terms; "
                f"{tr.n_terms_dropped_no_cells} descendants were dropped because no "
                f"cell in this Census version uses them."
            )
    return warnings
