"""Entry point: ``python -m cxg_census_mcp`` (also installed as ``cxg-census-mcp``)."""

from __future__ import annotations

import asyncio
import sys

from cxg_census_mcp.logging_setup import configure_logging
from cxg_census_mcp.server import run_stdio


def main() -> int:
    configure_logging()
    try:
        asyncio.run(run_stdio())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
