# Recommended agent workflow

For most exploratory questions, follow this loop:

1. **Pin once.** Don't change `census_version` mid-conversation unless the
   user asks. Reproducibility depends on it.
2. **Resolve ambiguous terms first.** If the user asks something like
   "B cells in lung from COVID patients", call `count_cells` directly — the
   resolver runs inline and surfaces ambiguities. Only call `resolve_term`
   independently when the user explicitly wants to inspect or disambiguate.
3. **Count before scanning.** `count_cells` is Tier-0 (cheap). Use it to size
   things up before any obs scan.
4. **Preview before scanning.** Call `preview_obs` to see representative rows
   and per-column cardinality hints before launching a Tier-1 obs scan.
5. **Read the provenance.** Every response includes `query_provenance.tissue_strategy`,
   `schema_rewrites_applied`, `resolved_filters`. Surface the salient bits to
   the user (especially `tissue_strategy` and any expansion).
6. **On refusal, use the snippet.** If the server refuses with `QUERY_TOO_LARGE`
   or similar, call `export_snippet(call_id)` and hand the snippet to the user
   to run locally. Don't retry the same oversized query.
7. **Treat ambiguity as clarification, not failure.** A `TERM_AMBIGUOUS` error
   includes `candidates` and a `retry_with` payload. Ask the user which term
   they meant; re-call with `confirm_ambiguous=true`.
