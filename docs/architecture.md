# Architecture

High-level layout of the `cxg_census_mcp` Python package and how requests flow.

## Layer overview

```
LLM ──MCP─→ tools/ ──→ planner/ ──→ ontology/ ──→ clients/
                              │                       (OLS, Census)
                              └─→ execution/ (Tier 0/1/2/snippet)
                                       └─→ models/ (response envelope)
                              Caches: ols, facets, plans, filter_lru
```

- `clients/` — only place that talks to OLS or TileDB-SOMA.
- `ontology/` — all term resolution and DAG operations.
- `planner/` — turns structured filters into a `QueryPlan`; estimates costs.
- `execution/` — runs the read; one module per tier.
- `tools/` — thin MCP wrappers; no business logic.

## Tier semantics

| Tier | Source | Examples |
|---|---|---|
| 0 | `summary_cell_counts` (pre-aggregated) | `count_cells`, `list_datasets` |
| 1 | obs scan, chunked | `preview_obs`, large `count_cells` with novel filter |
| 2 | aggregate expression | `aggregate_expression` |
| 9 | refusal: must use `export_snippet` | over-cap requests |
