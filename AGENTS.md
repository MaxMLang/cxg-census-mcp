# AGENTS.md

Project context for AI coding agents (Cursor, Claude Code, etc.). If you're
a human, [`README.md`](README.md) is the better entry point.

## What this is

`cxg-census-mcp` is a Model Context Protocol (MCP) server that lets LLM
agents query the [CZ CELLxGENE Discover Census](https://chanzuckerberg.github.io/cellxgene-census/)
single-cell atlas with ontology-aware filters, cost caps, and per-response
provenance. It speaks MCP over stdio.

It is **independent** — not affiliated with CZI, EMBL-EBI, or any government
agency. Every tool response carries `attribution` and `unaffiliated` fields
that downstream code must preserve.

## Layout

```
src/cxg_census_mcp/
  tools/        # thin MCP wrappers, no business logic
  planner/      # FilterSpec → QueryPlan; cost estimate; tier routing
  ontology/     # OLS4 client + local hint overlay + CL/UBERON/MONDO expansion
  execution/    # Tier 0 facet counts | Tier 1 chunked obs scan |
                # Tier 2 expression aggregate | Tier 9 refuse → snippet
  clients/      # OLS4 (HTTPS) + Census/SOMA wrappers
  caches/       # SqliteKV-backed OLS / facet / plan caches + filter LRU
  models/       # Pydantic models incl. ResponseEnvelope (provenance + caveats)
```

## Build / test / lint

```bash
uv sync --extra dev                # install everything except live Census
uv sync --extra dev --extra census # add cellxgene_census + tiledbsoma

make lint typecheck test           # ruff + mypy + pytest (mock mode)
make audit                         # pip-audit on locked prod deps
make cov                           # tests + coverage
```

`make test` runs in mock mode (`CXG_CENSUS_MCP_MOCK_MODE=1`) and uses
deterministic fixtures. `make test-live` hits real OLS / Census and is
gated by the `live` pytest marker.

## Conventions

- **Comments explain *why*, not *what*.** Don't narrate code.
- **No new runtime deps without strong justification.** This is a single
  user-installable tool; every dep is a Docker layer and a CVE surface.
- **Cache values are JSON-serializable.** The KV layer (`caches/_sqlite_kv.py`)
  json-encodes; storing arbitrary pickle values would re-introduce
  CVE-2025-69872. See [`SECURITY.md`](SECURITY.md).
- **Every tool returns `ResponseEnvelope`.** Includes `data`, `query_provenance`,
  `attribution`, `unaffiliated`, `disclaimer`, `call_id`, `defaults_applied`,
  `warnings`. Don't return raw payloads.
- **Tools are async, planner is async, execution is async.** Stay in
  `asyncio`; don't introduce threadpools.
- **Caps live in `Settings`** (`config.py`). Don't hard-code limits in tools.
- **Don't bypass the planner.** Tools must call `plan_query(...)` first; it
  is responsible for ontology resolution + tier selection + cost estimate +
  refusal logic.

## Add a new tool

1. New module under `src/cxg_census_mcp/tools/yourtool.py`. Follow the
   existing pattern: validate input, call planner, run execution, build
   envelope, register call_id.
2. Export from `tools/__init__.py`.
3. Register in `server.py` so MCP `tools/list` advertises it.
4. Integration test under `tests/integration/test_yourtool.py` (the
   `_isolated_env` fixture handles cache + mock mode for you).
5. Update `docs/tool-reference.md`.

## Don't touch without asking

- `LICENSE` and the trademark / unaffiliated notices in `README.md`,
  `__init__.py`, `models/provenance.py`. They're load-bearing legally.
- `data/ontology_hints.json` and `data/facet_catalog.json`. They're
  refreshed by scheduled GitHub Actions, not edited by hand.
- The `ATTRIBUTION` / `UNAFFILIATED` / `DISCLAIMER` strings in
  `src/cxg_census_mcp/__init__.py`. They surface in every response.

## Useful entry points

- `src/cxg_census_mcp/server.py` — MCP wire protocol, tool dispatch.
- `src/cxg_census_mcp/planner/query_plan.py` — `plan_query`, the brain.
- `src/cxg_census_mcp/execution/tier{0,1,2}_*.py` — actual Census reads.
- `src/cxg_census_mcp/ontology/resolver.py` — text → CURIE.

## When unsure

- Read `docs/architecture.md` and `docs/tool-reference.md` first.
- Then look at how an existing similar tool / planner branch is wired and
  copy the pattern.
- The mock-mode fixtures in `clients/census.py` (`_mock_*`) are the
  canonical reference for the data shape.
