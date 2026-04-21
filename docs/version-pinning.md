# Version pinning

The Census version is pinned via `CXG_CENSUS_MCP_CENSUS_VERSION` and reported in
every response's `query_provenance.census_version`. Results are not
comparable across versions; the planner's `plan_hash` mixes the version into
the call_id so snippet exports remain reproducible.

When upgrading the Census version pin:

1. Run `scripts/refresh_facet_catalog.py` (or trigger the workflow).
2. Run `scripts/diff_schema_versions.py` to surface column changes.
3. Add any required rewrites to `src/cxg_census_mcp/data/schema_drift.json`.
4. Bump the package SemVer minor.
