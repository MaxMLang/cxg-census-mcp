# Progress and cancellation

## Progress

Tools whose `query_provenance.estimated_runtime_ms` exceeds
`CXG_CENSUS_MCP_PROGRESS_MIN_MS` (default 750ms) emit MCP progress notifications.
Each notification carries `(progress, total)` where progress is the fraction
of work done so far.

A throttled emitter ensures we don't spam the transport — clients can rely on
roughly one update per 250ms during the active phase, plus a final
`progress=1.0` event on completion.

## Cancellation

Long Tier-1/Tier-2 operations check a cancellation token between chunks. If
the client sends an MCP cancel notification, the server raises a
`CANCELLED` error and tears down any open Census handles cleanly.

## What's safe to cancel?

- All Tier-0 calls (`count_cells`, `list_datasets`, `list_available_values`)
  are short enough that cancellation is moot.
- Tier-1 obs scans honor cancellation between chunks.
- Tier-2 aggregate expression honors cancellation between gene-batch boundaries.
- Snippet export and OLS lookups are sub-second and not cancellable.
