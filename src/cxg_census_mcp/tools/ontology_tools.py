"""Ontology inspection tools: resolve_term, expand_term, term_definition."""

from __future__ import annotations

from cxg_census_mcp.clients.ols import get_ols_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import TermNotFoundError
from cxg_census_mcp.models.ontology import (
    ExpandDirection,
    ExpandedTerm,
    ResolutionRefusal,
    ResolvedTerm,
    TermDefinition,
)
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.ontology.expander import expand
from cxg_census_mcp.ontology.resolver import resolve
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope
from cxg_census_mcp.utils.curie import normalize_curie
from cxg_census_mcp.utils.stable_hash import stable_hash


async def resolve_term(
    text: str,
    *,
    ontology: str | None = None,
    facet: str | None = None,
    confirm_ambiguous: bool = False,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    result = await resolve(
        text,
        ontology=ontology,
        facet=facet,
        confirm_ambiguous=confirm_ambiguous,
        census_version=s.census_version,
    )
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="unknown",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash("resolve_term", text, ontology, facet, length=20)
    payload = (
        result.model_dump() if isinstance(result, (ResolvedTerm, ResolutionRefusal)) else result
    )
    return build_envelope(
        data={"result": payload, "kind": result.__class__.__name__},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
    )


async def expand_term(
    curie: str,
    *,
    direction: ExpandDirection = "descendants_inclusive",
    in_census_only: bool = True,
    include_counts: bool = False,
    facet: str | None = None,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    expanded: ExpandedTerm = await expand(
        normalize_curie(curie),
        direction=direction,
        in_census_only=in_census_only,
        include_cell_counts=include_counts,
        census_version=s.census_version,
        facet=facet,
    )
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="unknown",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash("expand_term", curie, direction, in_census_only, length=20)
    return build_envelope(
        data=expanded.model_dump(),
        provenance=provenance,
        call_id=call_id,
        timer=timer,
    )


async def term_definition(curie: str) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    client = get_ols_client()
    curie = normalize_curie(curie)
    term = await client.get_term(curie)
    if term is None:
        raise TermNotFoundError(f"CURIE not found in OLS: {curie}")
    payload = TermDefinition(
        curie=term.curie,
        label=term.label,
        ontology=term.ontology,
        definition=term.definition,
        synonyms=term.synonyms,
        is_obsolete=term.is_obsolete,
        iri=term.iri,
    )
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="unknown",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash("term_definition", curie, length=20)
    return build_envelope(
        data=payload.model_dump(),
        provenance=provenance,
        call_id=call_id,
        timer=timer,
    )
