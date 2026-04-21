# Operational playbook

All tasks below have a `make` target — see `make help` for the full list.

## Weekly automation

| Workflow                  | Schedule  | What it does                                                        |
|---------------------------|-----------|---------------------------------------------------------------------|
| `ci.yml`                  | per-PR    | ruff, mypy, pytest matrix, pip-audit, fixtures validation, Docker build. |
| `ontology-refresh.yml`    | weekly    | Refreshes `data/ontology_hints.json` from OLS; opens a PR on diff.  |
| `facet-refresh.yml`       | Tue       | Refreshes `data/facet_catalog.json` from the live Census; opens PR. |
| `live-smoke.yml`          | Wed       | Runs `pytest -m live` against real OLS + Census; opens issue on fail. |
| `release.yml`             | tag push  | Builds wheel + sdist, pushes multi-arch image to GHCR, GitHub release. |

## Routine ops

```bash
make prewarm           # warm OLS cache from data/ols_seed_terms.json
make refresh-hints     # sync ontology_hints.json with OLS
make refresh-facets    # sync facet_catalog.json with the live Census
make vacuum-plans      # drop expired plan-cache entries (cron-friendly)
make metrics           # write Prometheus textfile → metrics.prom
```

For a node-exporter textfile collector:

```cron
*/1 * * * * cd /opt/cxg-census-mcp && \
  python -m cxg_census_mcp.metrics_dump > /var/lib/node_exporter/textfile_collector/cxg_census_mcp.prom
```

## When OLS is down

- Resolver falls back to the local hint overlay where possible
  (`confidence="hint_fallback"`).
- HTTP layer's circuit breaker opens after 5 consecutive failures and stays
  open for 30 seconds.
- Tools surface `ONTOLOGY_UNAVAILABLE` once the breaker is open and no hint
  match is found.
- Watch `census_mcp_ols_cache_misses_total` ramp; expect a steady rise.

## When Census is unavailable

- Set `CXG_CENSUS_MCP_MOCK_MODE=1` to operate against shipped fixtures.
- `census_summary` and the discovery tools continue to function with mock data.
- Tier-1 / Tier-2 tools return small deterministic mock results — useful for
  agent harness tests.

## When a new Census release lands

1. Bump `CXG_CENSUS_MCP_CENSUS_VERSION` (or rely on `stable`).
2. Refresh facets: `make refresh-facets`.
3. Diff schemas: `make diff-versions FROM=<old> TO=<new>`.
4. If columns moved/renamed, add a rule to `data/schema_drift.json` and a
   matching fixture under `tests/fixtures/schema_drift_cases.yaml`.
5. Bump SemVer minor; tag a release; CI publishes the new image.

## Incident: oversized requests

If `census_mcp_cap_rejections_total{kind="..."}` rises sharply, an LLM is
probably issuing too-broad queries. Either:

- Tighten the relevant cap in `Settings`.
- Update the agent prompt to recommend `preview_obs` first.
- Inspect the offending plans via `get_server_limits` — runtime stats include
  the per-tool error counts.

## Container

```bash
make docker-build IMAGE=ghcr.io/your-org/cxg-census-mcp TAG=$(git rev-parse --short HEAD)
make docker-run                  # stdio; pipe MCP framing to stdin
```

The image runs as non-root `uid=1000`, with a healthcheck that confirms the
package imports.
