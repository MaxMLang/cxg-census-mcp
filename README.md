# cxg-census-mcp

A community-maintained [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) server for the [CZ CELLxGENE Discover Census](https://chanzuckerberg.github.io/cellxgene-census/) —
the public, programmatically-queryable single-cell atlas curated by the Chan
Zuckerberg Initiative. Free-text terms and CURIEs go through OLS4 + a small
hint file, filters become SOMA `value_filter` expressions, and every tool
response includes machine-readable provenance and attribution (with typed
errors when something cannot run server-side).

> **Independent / unaffiliated.** `cxg-census-mcp` is an independent,
> community-maintained project authored by Max M. Lang. It is **not**
> affiliated with, endorsed by, or sponsored by the Chan Zuckerberg Initiative
> (CZI), EMBL-EBI, the U.S. Census Bureau, or any other organization.
> "CELLxGENE", "CELLxGENE Discover", and "CELLxGENE Discover Census" are
> product/brand names of CZI; references here are descriptive (nominative use)
> only. See [LICENSE](LICENSE) for the full trademark and attribution notice.

> **No warranty.** This software is provided "as is", without warranty of
> any kind, under the MIT License. It is intended for **research and
> exploration**, not clinical or diagnostic use. Always verify results before
> publication.

> Alpha (v0.3.0). [`CHANGELOG.md`](CHANGELOG.md) · [`docs/architecture.md`](docs/architecture.md).

## What it does

- Resolve free-text labels to ontology IDs (CL, UBERON, MONDO, EFO, HANCESTRO, …) via OLS4 + local hints.
- Plan queries with a pinned Census version, schema-drift rewrites, tissue routing, and cost caps.
- Counts, dataset lists, gene presence, expression aggregates, obs previews — not bulk X export.
- Over caps or ambiguous terms: structured errors; large jobs can use `export_snippet` + local Python.

## MCP capabilities

| Channel       | What's exposed                                                              |
|---------------|-----------------------------------------------------------------------------|
| `tools`       | 13 tools — see below.                                                       |
| `resources`   | Markdown docs under `cxg-census-mcp://docs/{schema,ontology,limitations,workflow,errors,progress}`. |
| `prompts`     | `census_workflow`, `disambiguation` — agent-guidance templates.             |
| `progress`    | `notifications/progress` for `count_cells`, `aggregate_expression`, `preview_obs` when the client passes a `progressToken`. |
| `cancellation`| `notifications/cancelled` cooperatively stops chunked scans.                |

## Installation

Requires Python 3.11+. Uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/MaxMLang/cxg-census-mcp
cd cxg-census-mcp
uv sync                            # core install (mock-mode capable)
uv sync --extra census             # add cellxgene_census + tiledbsoma
uv sync --extra dev                # add test/lint tooling
```

To run the server over stdio:

```bash
uv run cxg-census-mcp
# or
uv run python -m cxg_census_mcp
```

## Configuration

All env vars use the `CXG_CENSUS_MCP_` prefix. Most-useful subset:

| Variable | Default | Purpose |
|---|---|---|
| `CXG_CENSUS_MCP_CENSUS_VERSION` | `stable` | Census release to pin |
| `CXG_CENSUS_MCP_CACHE_DIR` | platformdirs default | Disk cache root |
| `CXG_CENSUS_MCP_MOCK_MODE` | `0` | If `1`, never opens a real Census handle (dev/testing) |
| `CXG_CENSUS_MCP_LOG_LEVEL` | `WARNING` | stdlib log level |

All settings: `src/cxg_census_mcp/config.py` (`CXG_CENSUS_MCP_*`); defaults are conservative for local runs.

## MCP client setup

### Claude Desktop

```json
{
  "mcpServers": {
    "cxg-census": {
      "command": "uv",
      "args": ["--directory", "/path/to/cxg-census-mcp", "run", "cxg-census-mcp"]
    }
  }
}
```

### Cursor

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cxg-census": {
      "command": "uv",
      "args": ["--directory", "/path/to/cxg-census-mcp", "run", "cxg-census-mcp"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add cxg-census -- uv --directory /path/to/cxg-census-mcp run cxg-census-mcp
```

## Tools (high level)

**Workflow tools:** `census_summary`, `get_census_versions`, `count_cells`,
`list_datasets`, `gene_coverage`, `aggregate_expression`, `preview_obs`,
`export_snippet`, `get_server_limits`.

**Inspection tools:** `resolve_term`, `expand_term`, `term_definition`,
`list_available_values`.

See [`docs/tool-reference.md`](docs/tool-reference.md) for full signatures.

## Development

A `Makefile` wraps the common flows; run `make help` for the full list.

```bash
make install-all                   # uv sync --extra dev --extra census
make lint typecheck test           # ruff + mypy + pytest (mock mode)
make cov                           # tests + coverage HTML in ./htmlcov
make test-live                     # E2E against real OLS + Census (slow)
make audit                         # pip-audit against installed deps
make format                        # ruff format
```

### Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Operations

| Task                            | Command                                                  |
|---------------------------------|----------------------------------------------------------|
| Pre-warm OLS cache              | `make prewarm`                                           |
| Refresh `ontology_hints.json`   | `make refresh-hints` (also a weekly GitHub Action)       |
| Refresh `facet_catalog.json`    | `make refresh-facets` (also a weekly GitHub Action)      |
| Vacuum expired plan-cache rows  | `make vacuum-plans`                                      |
| Diff two Census schemas         | `make diff-versions FROM=2024-07-01 TO=stable`           |
| Dump Prometheus metrics         | `make metrics` (writes `metrics.prom`)                   |
| Build container                 | `make docker-build IMAGE=cxg-census-mcp TAG=$(git rev-parse --short HEAD)` |
| Run container (stdio)           | `make docker-run`                                        |

Runtime stats — cache hit/miss, cap rejections, tool calls/errors, plan-cache
size — are also returned inline by `get_server_limits` so MCP clients can
inspect them without a side channel.

## License, attribution, trademarks

The source code in this repository is released under the [MIT License](LICENSE).
The MIT license covers **only the code**, not the upstream data, ontologies,
or any third-party trademarks.

- **Upstream data.** Tool responses are derived (filtered/aggregated) from
  the **CZ CELLxGENE Discover Census**, distributed by the Chan Zuckerberg
  Initiative under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Every response carries an `attribution` field reflecting this; downstream
  users must preserve attribution and indicate that changes were made.
- **Ontology terms** come from the EBI **Ontology Lookup Service (OLS4)**
  and originate from third-party ontologies (CL, UBERON, MONDO, EFO,
  HANCESTRO, …). Each ontology carries its own license; consult the
  respective ontology for terms.
- **Trademarks.** "CELLxGENE", "CELLxGENE Discover", and
  "CELLxGENE Discover Census" are CZI marks. "Cursor", "Claude", "Anthropic",
  and "Model Context Protocol" are marks of their respective owners. Use of
  these names in this README is descriptive (nominative use) only and does
  not imply affiliation or endorsement.

This server is for research and exploration. It is **not** a clinical or
diagnostic tool. Always verify results before publication.
