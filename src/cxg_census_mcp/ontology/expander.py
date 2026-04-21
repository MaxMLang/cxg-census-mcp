"""Expand a CURIE to its descendants/ancestors, filtered to Census presence.

The width of an expansion is bounded by ``CXG_CENSUS_MCP_MAX_EXPANSION_TERMS`` to
prevent pathological cases (e.g. expanding "cell" → tens of thousands of CL
descendants) from constructing absurd ``in [...]`` predicates.
"""

from __future__ import annotations

from cxg_census_mcp.clients.ols import OLSClient, get_ols_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import (
    ExpansionTooWideError,
    OntologyUnavailableError,
    TermNotFoundError,
)
from cxg_census_mcp.models.ontology import ExpandDirection, ExpandedTerm
from cxg_census_mcp.ontology.presence import get_presence_index
from cxg_census_mcp.ontology.registry import column_for
from cxg_census_mcp.utils.curie import normalize_curie, parse_curie


async def expand(
    curie: str,
    *,
    direction: ExpandDirection = "exact",
    in_census_only: bool = True,
    include_cell_counts: bool = False,
    census_version: str = "stable",
    organism: str = "homo_sapiens",
    facet: str | None = None,
    client: OLSClient | None = None,
) -> ExpandedTerm:
    client = client or get_ols_client()
    curie = normalize_curie(curie)
    prefix, _ = parse_curie(curie)
    settings = get_settings()
    max_terms = settings.max_expansion_terms

    term = await client.get_term(curie)
    if term is None:
        raise TermNotFoundError(f"CURIE not found in OLS: {curie}")

    if direction == "exact":
        all_terms = [curie]
    elif direction == "descendants_inclusive":
        try:
            descendants = await client.get_descendants(curie, ontology=prefix.lower())
        except OntologyUnavailableError as exc:
            raise OntologyUnavailableError(
                f"OLS unavailable while expanding {curie}: {exc}"
            ) from exc
        all_terms = sorted({curie, *descendants})
    elif direction == "ancestors_inclusive":
        try:
            ancestors = await client.get_ancestors(curie, ontology=prefix.lower())
        except OntologyUnavailableError as exc:
            raise OntologyUnavailableError(
                f"OLS unavailable while expanding {curie}: {exc}"
            ) from exc
        all_terms = sorted({curie, *ancestors})
    else:  # pragma: no cover — pydantic enforces
        raise ValueError(f"Unknown expansion direction: {direction}")

    column = ""
    if facet is not None:
        try:
            column = column_for(prefix, facet=facet).get("id_col", "")
        except KeyError:
            column = ""

    # Filter to Census-present terms before applying max_expansion_terms.
    present: list[str] = list(all_terms)
    missing: list[str] = []
    if in_census_only and column:
        present, missing = get_presence_index().filter_present(
            all_terms, column=column, census_version=census_version, organism=organism
        )
        if not present:
            return ExpandedTerm(
                query_curie=curie,
                query_label=term.label,
                direction=direction,
                terms=[],
                terms_present_in_census=0,
                terms_missing_from_census=missing,
                terms_truncated=False,
                truncation_reason="all_terms_absent_from_census",
                cells_by_term=None,
                total_cells=None,
            )

    truncated = False
    truncation_reason: str | None = None
    effective_terms = present
    if len(effective_terms) > max_terms:
        raise ExpansionTooWideError(
            f"Expansion of {curie} ({direction}) yielded {len(effective_terms)} "
            f"in-Census terms (out of {len(all_terms)} from the ontology), "
            f"exceeding cap {max_terms}.",
            retry_with={
                "curie": curie,
                "direction": "exact",
            },
        )

    return ExpandedTerm(
        query_curie=curie,
        query_label=term.label,
        direction=direction,
        terms=effective_terms,
        terms_present_in_census=len(effective_terms),
        terms_missing_from_census=missing,
        terms_truncated=truncated,
        truncation_reason=truncation_reason,
        cells_by_term=None,  # populated by the planner if requested
        total_cells=None,
    )
