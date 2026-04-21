"""Community MCP server for the CZ CELLxGENE Discover Census.

This is an independent, community-maintained project. It is *not* affiliated
with, endorsed by, or sponsored by the Chan Zuckerberg Initiative (CZI),
EMBL-EBI, or any government statistical agency (including the U.S. Census
Bureau). All trademarks remain the property of their respective owners.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("cxg-census-mcp")
except PackageNotFoundError:  # editable installs without metadata
    __version__ = "0.1.0"

ATTRIBUTION = (
    "Data: CZ CELLxGENE Discover Census, distributed by the Chan Zuckerberg "
    "Initiative under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). "
    "Results here are derived (filtered/aggregated) from that dataset. "
    "Ontology terms: EBI Ontology Lookup Service (OLS4); each ontology "
    "(CL, UBERON, MONDO, EFO, HANCESTRO, ...) carries its own license."
)

UNAFFILIATED = (
    "cxg-census-mcp is an independent, community-maintained Model Context "
    "Protocol server. It is not affiliated with, endorsed by, or sponsored by "
    "the Chan Zuckerberg Initiative, EMBL-EBI, or any government statistical "
    "agency."
)

DISCLAIMER = (
    "This server is for research and exploration. It is not a clinical or "
    "diagnostic tool. The software is provided 'as is', without warranty of "
    "any kind (see LICENSE). Verify all results before publication."
)

__all__ = [
    "ATTRIBUTION",
    "DISCLAIMER",
    "UNAFFILIATED",
    "__version__",
]
