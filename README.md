# cxg-census-mcp

<!-- mcp-name: io.github.MaxMLang/cxg-census-mcp -->

[![PyPI](https://img.shields.io/pypi/v/cxg-census-mcp.svg)](https://pypi.org/project/cxg-census-mcp/)
[![PyPI downloads](https://img.shields.io/pypi/dm/cxg-census-mcp.svg)](https://pypi.org/project/cxg-census-mcp/)
[![CI](https://github.com/MaxMLang/cxg-census-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/MaxMLang/cxg-census-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/MaxMLang/cxg-census-mcp/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://github.com/MaxMLang/cxg-census-mcp/blob/main/pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange)](https://github.com/MaxMLang/cxg-census-mcp/blob/main/CHANGELOG.md)
[![Last commit](https://img.shields.io/github/last-commit/MaxMLang/cxg-census-mcp)](https://github.com/MaxMLang/cxg-census-mcp/commits/main)

An [MCP](https://modelcontextprotocol.io) server that lets LLM agents
query the [CZ CELLxGENE Discover Census](https://chanzuckerberg.github.io/cellxgene-census/)
single-cell atlas without lying about it — ontology-aware filters, cost
caps, full provenance + attribution on every response. Drop it into
Cursor / Claude Desktop / Claude Code and ask questions like *"compare
immune cell composition of healthy vs COVID-19 human lung"* in plain
English.

> **Independent / unaffiliated.** Not affiliated
> with, endorsed by, or sponsored by the Chan Zuckerberg Initiative (CZI),
> EMBL-EBI, the U.S. Census Bureau, or anyone else. "CELLxGENE" is a CZI
> mark; references here are descriptive (nominative) use only.
>
> **No warranty.** MIT-licensed source, "as is". Research/exploration tool —
> **not** a clinical or diagnostic instrument. Always verify results before
> publication. See [LICENSE](https://github.com/MaxMLang/cxg-census-mcp/blob/main/LICENSE)
> for the full trademark and content attribution notice, and
> [SECURITY.md](https://github.com/MaxMLang/cxg-census-mcp/blob/main/SECURITY.md)
> for the threat model and known-issues policy.

> Alpha (v0.1.2). [`CHANGELOG.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/CHANGELOG.md)

## Demos

**Healthy vs COVID-19 lung, side-by-side.** Two parallel queries, the
`disease_multi_value_v7` schema-drift rewrite kicks in for the COVID
cohort, attribution from both contributing dataset sets surfaces in the
same chat turn.

https://github.com/user-attachments/assets/c836f225-5075-4643-87aa-70d311bc5fd2

**Cell-type composition of human lung in one query.** Free-text "lung"
resolved to `UBERON:0002048`, routed through `tissue_general`, every CURIE
labeled, all in a single Tier-0 call.

https://github.com/user-attachments/assets/b0e10ca7-e46b-4e5f-ae63-11949d328c4d

(Videos render on GitHub. On PyPI they appear as bare URLs — head to the
[GitHub README](https://github.com/MaxMLang/cxg-census-mcp#demos) to watch.)

More prompts in [`docs/example-questions.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/example-questions.md).

## Architecture at a glance

```
                 ┌──────────────────────────────────────────────┐
   MCP client    │   tools/        thin MCP wrappers, no logic  │
   (Claude,  ─►  │     │                                        │
    Cursor,      │     ▼                                        │
    Code, …)     │   planner/      FilterSpec → QueryPlan,      │
                 │     │           cost estimate, tier routing  │
                 │     ▼                                        │
                 │   ontology/     OLS4 + hint overlay,         │
                 │     │           CL/UBERON/MONDO expansion    │
                 │     ▼                                        │
                 │   execution/    Tier 0  facet counts         │
                 │     │           Tier 1  chunked obs scan     │
                 │     │           Tier 2  expression aggregate │
                 │     │           Tier 9  refuse → snippet     │
                 │     ▼                                        │
                 │   clients/      OLS4 (HTTPS) + Census/SOMA   │
                 │                                              │
                 │   caches/       OLS, facet, plan, filter LRU │
                 │   models/       Response envelope w/         │
                 │                 attribution + provenance     │
                 └──────────────────────────────────────────────┘
                                    │
                                    ▼
                       ┌────────────────────────┐
                       │ EBI OLS4 (ontology)    │
                       │ CZ CELLxGENE Census    │
                       │ (CC BY 4.0 data)       │
                       └────────────────────────┘
```

Full architecture notes: [`docs/architecture.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/architecture.md).
Tool reference: [`docs/tool-reference.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/tool-reference.md).
Example questions: [`docs/example-questions.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/example-questions.md).

## Install

From PyPI (recommended):

```bash
uv tool install "cxg-census-mcp[census]"
cxg-census-mcp                       # speaks MCP over stdio
```

Or with pip:

```bash
pip install "cxg-census-mcp[census]"
```

Without the `[census]` extra you get **mock mode** (deterministic fixtures) —
handy for offline demos and verifying your MCP client config without pulling
tiledbsoma's ~1 GB of native deps.

From source (for development):

```bash
git clone https://github.com/MaxMLang/cxg-census-mcp
cd cxg-census-mcp
uv sync --extra dev --extra census
uv run cxg-census-mcp
```

## MCP client config

Cursor (`~/.cursor/mcp.json`) and Claude Desktop
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS)
both expect the same shape. Cleanest is `uvx` once installed from PyPI:

```json
{
  "mcpServers": {
    "cxg-census": {
      "command": "/absolute/path/to/uvx",
      "args": ["--from", "cxg-census-mcp[census]", "cxg-census-mcp"]
    }
  }
}
```

> Use the **absolute** path to `uvx` (`which uvx` from your shell). MCP
> clients spawn the server in a non-interactive subprocess that doesn't
> source your shell rc, so a bare `"uvx"` will fail with
> `No such file or directory`.

If you cloned from source instead, point at the checkout:

```json
{
  "mcpServers": {
    "cxg-census": {
      "command": "/absolute/path/to/uv",
      "args": ["--directory", "/path/to/cxg-census-mcp", "run", "cxg-census-mcp"]
    }
  }
}
```

Claude Code:

```bash
claude mcp add cxg-census -- /absolute/path/to/uvx --from "cxg-census-mcp[census]" cxg-census-mcp
```

Quit + relaunch your client (⌘Q on macOS — closing the window isn't enough)
and the server should show up in the MCP panel with 13 tools.

## Tools (13 total)

**Workflow:** `census_summary`, `get_census_versions`, `count_cells`,
`list_datasets`, `gene_coverage`, `aggregate_expression`, `preview_obs`,
`export_snippet`, `get_server_limits`.

**Inspection:** `resolve_term`, `expand_term`, `term_definition`,
`list_available_values`.

Plus MCP `resources` (markdown docs at `cxg-census-mcp://docs/{slug}`),
`prompts` (`census_workflow`, `disambiguation`), and cooperative
`progress` / `cancellation` notifications. Details in
[`docs/tool-reference.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/tool-reference.md).

## Configuration

All env vars use the `CXG_CENSUS_MCP_` prefix. Most useful:

| Variable | Default | Purpose |
|---|---|---|
| `CXG_CENSUS_MCP_CENSUS_VERSION` | `stable` | Census release to pin |
| `CXG_CENSUS_MCP_CACHE_DIR` | platformdirs default | Disk cache root |
| `CXG_CENSUS_MCP_MOCK_MODE` | `0` | If `1`, never opens a real Census handle |
| `CXG_CENSUS_MCP_LOG_LEVEL` | `WARNING` | stdlib log level |

Full list and validation: `src/cxg_census_mcp/config.py`.

## Development & operations

Quick loop:

```bash
make install-all                 # uv sync --extra dev --extra census
make lint typecheck test         # ruff + mypy + pytest (mock mode)
make cov                         # tests + coverage HTML in ./htmlcov
make audit                       # pip-audit on locked production deps
```

Operational tasks (cache pre-warm, schema diff, container build, metrics
dump, plan-cache vacuum, weekly hint/facet refresh) live in the
[`Makefile`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/Makefile)
and are documented in
[`docs/operational-playbook.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/operational-playbook.md).

## Documentation index

| Topic | Where |
|---|---|
| System architecture | [`docs/architecture.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/architecture.md) |
| Tool reference | [`docs/tool-reference.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/tool-reference.md) |
| Example agent questions | [`docs/example-questions.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/example-questions.md) |
| Ontology resolution | [`docs/ontology-resolution.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/ontology-resolution.md) |
| Schema-drift handling | [`docs/schema-drift-format.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/schema-drift-format.md) |
| Census version pinning | [`docs/version-pinning.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/version-pinning.md) |
| Progress / cancellation | [`docs/progress-and-cancellation.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/progress-and-cancellation.md) |
| Error model | [`docs/error-model.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/error-model.md) |
| Known limitations | [`docs/limitations.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/limitations.md) |
| Ops runbook | [`docs/operational-playbook.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/docs/operational-playbook.md) |
| Changelog | [`CHANGELOG.md`](https://github.com/MaxMLang/cxg-census-mcp/blob/main/CHANGELOG.md) |

## License & attribution

Source code: [MIT](https://github.com/MaxMLang/cxg-census-mcp/blob/main/LICENSE).
The MIT license covers **only** the code in this repository, not the upstream
data, ontologies, or third-party trademarks.

- **Data.** Tool responses are derived (filtered/aggregated) from the
  CZ CELLxGENE Discover Census, distributed by the Chan Zuckerberg
  Initiative under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Every response carries an `attribution` field; downstream users must
  preserve attribution and indicate that changes were made.
- **Ontologies** are fetched via EBI Ontology Lookup Service (OLS4) from
  CL, UBERON, MONDO, EFO, HANCESTRO, and others; each carries its own
  license.
- **Trademarks** ("CELLxGENE", "Cursor", "Claude", "Anthropic", "Model
  Context Protocol", …) belong to their respective owners. Use here is
  descriptive only and does not imply affiliation.

This project is a *client* of the CZ CELLxGENE Discover Census; it does
not host, mirror, or redistribute Census data.

Full notice in [LICENSE](https://github.com/MaxMLang/cxg-census-mcp/blob/main/LICENSE).
