"""Fetch seed CURIEs into disk OLS cache (Docker build); no-op if OLS down."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from importlib import resources

from cxg_census_mcp.clients.ols import get_ols_client
from cxg_census_mcp.errors import OntologyUnavailableError
from cxg_census_mcp.logging_setup import configure_logging, get_logger

log = get_logger(__name__)


def _load_seed() -> list[str]:
    raw = resources.files("cxg_census_mcp.data").joinpath("ols_seed_terms.json").read_text()
    return list(json.loads(raw).get("curies") or [])


async def _prewarm(curies: list[str], *, fetch_dag: bool) -> tuple[int, int]:
    client = get_ols_client()
    ok = fail = 0
    for curie in curies:
        try:
            term = await client.get_term(curie)
            if term is None:
                fail += 1
                log.warning("seed_miss", curie=curie)
                continue
            ok += 1
            if fetch_dag:
                # Only descendants for taxonomic ontologies; ancestors come for free
                # via downstream resolver fallbacks.
                await client.get_descendants(curie)
        except OntologyUnavailableError as exc:
            fail += 1
            log.error("ols_unavailable", curie=curie, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            fail += 1
            log.error("seed_failed", curie=curie, error=str(exc))
    return ok, fail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-dag",
        action="store_true",
        help="Also prewarm hierarchical descendants for each seed term.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    curies = _load_seed()
    log.info("prewarm_start", count=len(curies), with_dag=args.with_dag)
    ok, fail = asyncio.run(_prewarm(curies, fetch_dag=args.with_dag))
    log.info("prewarm_done", ok=ok, fail=fail)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
