"""Ontology layer: resolver, expander, tissue router, schema rewrites."""

from cxg_census_mcp.ontology.expander import expand
from cxg_census_mcp.ontology.presence import PresenceIndex, get_presence_index
from cxg_census_mcp.ontology.registry import (
    FACET_TO_ONTOLOGY,
    ONTOLOGY_COLUMN_MAP,
    column_for,
    ontology_for_facet,
)
from cxg_census_mcp.ontology.resolver import resolve
from cxg_census_mcp.ontology.rewrites import RewriteContext, apply_rewrites
from cxg_census_mcp.ontology.tissue_router import TissueRouting, pick_tissue_column

__all__ = [
    "FACET_TO_ONTOLOGY",
    "ONTOLOGY_COLUMN_MAP",
    "PresenceIndex",
    "RewriteContext",
    "TissueRouting",
    "apply_rewrites",
    "column_for",
    "expand",
    "get_presence_index",
    "ontology_for_facet",
    "pick_tissue_column",
    "resolve",
]
