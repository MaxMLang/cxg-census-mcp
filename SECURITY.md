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

### CVE-2025-69872 — `diskcache` pickle deserialization (open, no upstream fix)

We depend on [`diskcache`](https://pypi.org/project/diskcache/) for the
on-disk OLS / facet / plan caches. Through 5.6.3, diskcache uses Python
`pickle` for value serialization. Per the published CVE, an attacker with
**write access to the cache directory** can achieve arbitrary code execution
when a victim application reads from the cache.

**Why it is intentionally still in `pip-audit --ignore-vuln` for now:**

- The risk is **local**: it requires write access to the user's cache
  directory. An attacker with that level of access on a single-user system
  already has many easier ways to execute code as that user
  (`~/.bashrc`, `~/.zshrc`, `pip install ...`, …). diskcache is not the weak
  link in that scenario.
- We do not deserialize pickles from untrusted sources at runtime — every
  value in the cache was serialized by this same process.
- We harden the cache root to `0700` on POSIX (`config.Settings.ensure_dirs`).
- There is no upstream fix yet (NVD lists no fix version as of writing).

**When this should be revisited:**

- Immediately if `diskcache` ships a fix → drop the `--ignore-vuln` line in
  `Makefile` and `.github/workflows/ci.yml`, bump the version pin in
  `pyproject.toml`.
- Or proactively, by replacing diskcache with a non-pickle backend (sqlite +
  JSON), which is tracked as a follow-up.

If you intend to deploy this on a **shared / multi-user host**, do not use
the default cache directory; set `CXG_CENSUS_MCP_CACHE_DIR` to a path you
fully control, and audit its permissions yourself.

## Reporting a vulnerability

This project is maintained by a single author, in spare time. Please **do
not** file public GitHub issues for security problems.

- Email: open the GitHub profile of the maintainer
  ([@MaxMLang](https://github.com/MaxMLang)) and use the contact listed
  there, or open a [GitHub Security Advisory](https://github.com/MaxMLang/cxg-census-mcp/security/advisories/new)
  on the repo (preferred — keeps the report private).
- Please include a minimal reproduction and the version (`pip show cxg-census-mcp`).
- Expect a best-effort response within 1–2 weeks. There are no SLAs.

## Supported versions

Only the latest tagged release on `main` receives fixes. There are no
backports during alpha.
