# Tool reference

| Tool | Tier | Purpose |
|---|---:|---|
| `census_summary` | 0 | Version metadata + cell count |
| `get_census_versions` | 0 | List visible versions |
| `list_available_values` | 0 | Enumerate facet values |
| `resolve_term` | 0 | Free text → CURIE |
| `expand_term` | 0 | DAG expansion |
| `term_definition` | 0 | OLS metadata for a CURIE |
| `count_cells` | 0 | Counts (optionally grouped) |
| `list_datasets` | 0 | Datasets matching filter |
| `gene_coverage` | 0 | Ensembl ID presence in var |
| `preview_obs` | 1 | Cheap obs preview |
| `aggregate_expression` | 2 | Per-group expression aggregates |
| `export_snippet` | 0 | Reproducible Python snippet for a stored plan |
| `get_server_limits` | 0 | Cap configuration |

Every tool returns a `ResponseEnvelope` with `data`, `query_provenance`,
`defaults_applied`, `warnings`, `call_id`, `meta`, `attribution`,
`disclaimer`. Errors are returned as a separate `MCPToolError` envelope
(see [`docs/error-model.md`](error-model.md)).
