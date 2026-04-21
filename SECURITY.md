# Security policy

`cxg-census-mcp` is alpha, single-author, and provided "as is" under MIT (no
warranty — see [`LICENSE`](LICENSE)). This file describes the threat model,
known issues, and how to report problems.

## Threat model (what this server is and is not)

`cxg-census-mcp` is intended to run **as the same user as the MCP client**
(Cursor, Claude Desktop, Claude Code, …) and read **public** data from
`https://www.ebi.ac.uk/ols4/api` and the public CZ CELLxGENE Discover Census
SOMA store.

**Trust boundaries assumed:**

- The user running the server is trusted with their own files.
- The cache directory (`~/.cache/cxg-census-mcp/` on Linux,
  `~/Library/Caches/cxg-census-mcp/` on macOS, the equivalent on Windows) is
  **not** a shared/multi-user location. Other local users on the same
  machine should not be able to write into it. We `chmod 0700` the cache
  root on POSIX best-effort; on Windows you should rely on the default
  per-user ACL of the user-cache directory.
- The MCP transport is local stdio. Network exposure is whatever your MCP
  client decides; we do not open a listening socket.
- We do **not** authenticate to OLS or to the Census; both are public.

**Out of scope:**

- Running as root.
- Running on a shared multi-user system where untrusted local users could
  write into your home / cache directory.
- Acting as a clinical or diagnostic tool. This is a research/exploration
  utility. Always verify results before publication.

## Known issues / accepted risk

None at the moment.

## Resolved

### CVE-2025-69872 — `diskcache` pickle deserialization (resolved by removing the dependency)

Earlier versions of `cxg-census-mcp` used [`diskcache`](https://pypi.org/project/diskcache/)
for the on-disk OLS / facet / plan caches. Through 5.6.3, diskcache uses
Python `pickle` for value serialization, so an attacker with write access
to the cache directory could achieve code execution when the server next
read the cache (CVE-2025-69872).

We dropped `diskcache` entirely and replaced it with a small sqlite + JSON
KV store (`src/cxg_census_mcp/caches/_sqlite_kv.py`). All cached values are
JSON-serialized; a tampered row at worst raises `json.JSONDecodeError` and
is treated as a cache miss. There is no deserialization-to-code path.

The `chmod 0700` on the cache root in `Settings.ensure_dirs()` is kept as
defense-in-depth hygiene, but is no longer load-bearing.

If you intend to deploy this on a **shared / multi-user host**, set
`CXG_CENSUS_MCP_CACHE_DIR` to a path you fully control and audit its
permissions yourself regardless.

## Reporting a vulnerability

This project is maintained by a single author, in spare time. Please **do
not** file public GitHub issues for security problems.

- Open a [private GitHub Security Advisory](https://github.com/MaxMLang/cxg-census-mcp/security/advisories/new)
  on the repository — this keeps the report confidential until a fix is ready.
- Include a minimal reproduction and the version (`pip show cxg-census-mcp`).
- Expect a best-effort response within 1–2 weeks. There are no SLAs.

## Supported versions

Only the latest tagged release on `main` receives fixes. There are no
backports during alpha.
