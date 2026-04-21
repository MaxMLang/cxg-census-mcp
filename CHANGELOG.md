# Changelog

All notable changes to this project will be documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (BREAKING — community rebrand)

- **Renamed** the project from `census-mcp` to **`cxg-census-mcp`** to (a)
  avoid naming collision with the U.S. Census Bureau and unrelated `census*`
  tooling, and (b) make the project's actual scope (the *CZ CELLxGENE*
  Discover Census single-cell atlas) unambiguous.
  - PyPI / distribution name: `cxg-census-mcp`.
  - Python import path: `cxg_census_mcp` (was `census_mcp`).
  - Console script: `cxg-census-mcp` (was `census-mcp`).
  - MCP resource URI scheme: `cxg-census-mcp://docs/{slug}` (was `census-mcp://...`).
  - Docker image: `cxg-census-mcp` (default `IMAGE` in the `Makefile`); GHCR
    path follows the GitHub repo slug.
- **Renamed env-var prefix** from `CENSUS_MCP_*` to `CXG_CENSUS_MCP_*`. Anyone
  who was setting `CENSUS_MCP_CACHE_DIR`, `CENSUS_MCP_MOCK_MODE`, etc. needs
  to update to `CXG_CENSUS_MCP_*`.
- **Default cache directory** path now resolves to
  `~/Library/Caches/cxg-census-mcp` (macOS) /
  `~/.cache/cxg-census-mcp` (Linux) /
  `%LOCALAPPDATA%\cxg-census-mcp\Cache` (Windows). Previous on-disk caches
  are not migrated; delete the old `census-mcp` cache directory if you want
  to reclaim space.

### Added

- Project is now explicitly **community-maintained**. Sole author/maintainer:
  Max M. Lang.
- **Trademark / unaffiliated notice** in `LICENSE` and `README.md`: this
  project is independent and not affiliated with the Chan Zuckerberg
  Initiative, EMBL-EBI, or any government statistical agency. References to
  third-party names (CELLxGENE, Cursor, Claude, Anthropic, MCP, ...) are
  descriptive (nominative use) only.
- **Stronger inline attribution.** `ATTRIBUTION` (returned in every tool
  envelope) now includes a direct URL to the
  [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/), notes
  that responses are *derived* (filtered/aggregated) rather than the raw
  Census, and credits OLS4 + per-ontology licensing.
- New `unaffiliated` field on every `ResponseEnvelope` so MCP clients can
  surface the community/unaffiliated status alongside results.
- PyPI metadata (`pyproject.toml`): added `Intended Audience`,
  `Topic :: Scientific/Engineering :: Bio-Informatics`, and
  `Operating System :: OS Independent` classifiers; expanded the keyword
  list for SEO without leaning on protected names.

## [0.3.0] - 2026-04-21

First production-grade cut. Replaces the v0.2 stubs with real implementations
across the execution layer, MCP wire protocol, and operational tooling.

### Added

- **MCP progress notifications.** Long-running tools (`count_cells`,
  `aggregate_expression`, `preview_obs`) emit periodic
  `notifications/progress` when the client passes a `progressToken`.
- **MCP cancellation.** `notifications/cancelled` from the client lands as
  `asyncio.CancelledError`; chunked loops yield via `CancellationToken.checkpoint()`
  so cancellation propagates promptly mid-scan.
- **MCP resources channel.** Markdown documentation (`schema`, `ontology`,
  `limitations`, `workflow`, `errors`, `progress`) is now exposed under
  `cxg-census-mcp://docs/{slug}`.
- **MCP prompts channel.** `census_workflow` and `disambiguation` workflow
  prompts are exposed via `prompts/list` and `prompts/get`.
- **Real Tier-1 obs scan.** `CensusClient.stream_obs` iterates SOMA `read().tables()`
  chunks; `run_tier1_obs` accumulates per-group counts without ever
  materialising the full obs table.
- **Real Tier-2 expression aggregation.** `CensusClient.aggregate_expression_chunks`
  uses `Experiment.axis_query` + chunked X iteration to compute per-(group, gene)
  mean / variance / fraction-expressing.
- **Real `gene_coverage`.** Reads `feature_dataset_presence_matrix` to fill
  `n_datasets_with_gene`. Documents `n_cells_with_gene` as null-by-design.
- **Real `export_snippet(intent="aggregate")`.** Emits a runnable Python
  snippet that performs per-group mean and fraction-expressing locally;
  captures the actual `gene_ids` and `group_by` from the stored plan.
- **Plan-store ops.** `PlanStore.vacuum()` (drop expired entries) and
  `PlanStore.stats()` for ops/CI.
- **Runtime metrics.** Process-local Prometheus textfile exporter
  (`cxg_census_mcp.metrics`, `python -m cxg_census_mcp.metrics_dump`) covering
  tool calls, tool errors, cap rejections, cancellations, cache hits/misses,
  and plan-cache size. `get_server_limits` now returns runtime stats too.
- **Makefile** with developer + ops targets (`install`, `lint`, `typecheck`,
  `test`, `cov`, `audit`, `prewarm`, `refresh-hints`, `refresh-facets`,
  `vacuum-plans`, `metrics`, `diff-versions`, `docker-build`, `docker-run`).
- **pre-commit** config (ruff, mypy, file hygiene).
- **CI hardening.** `pip-audit` job for known CVEs; coverage report; release
  workflow that builds the Docker image on tag push.
- New tests: schema contract (`tests/unit/test_schema_contract.py`),
  resolver multi-candidate ranking (`tests/unit/test_resolver_ranking.py`),
  progress + cancellation (`tests/unit/test_progress_cancellation.py`),
  resources/prompts channels (`tests/integration/test_resources_and_prompts.py`),
  and metrics rendering (`tests/unit/test_metrics.py`).

### Changed

- `QueryPlan` now carries `gene_ids` so the snippet emitter can reproduce
  expression queries faithfully.
- `ExpressionRow` adds `std`.
- `count_cells` now routes through Tier-1 (chunked obs scan) when the planner
  picks tier ≥ 1, instead of always going through Tier-0 facet counts.
- `Dockerfile` `prewarm` stage uses the actual `scripts/prewarm_ols_cache.py`
  entry point.

### Fixed

- Plan-cache TTL is now consistently honoured, with an explicit `vacuum`
  helper for cron-driven cleanup.
- Snippet emitter no longer leaks an empty `GENE_IDS = []` for aggregate
  intents; pulls them from the plan.

## [0.2.0] - 2026-04-21

Initial implementation of the merged v0.3 architecture spec: ontology
resolver, planner, tier router, mock-mode execution, all tools registered.

## [0.1.0]

Draft scaffolding from early internal plan notes.
