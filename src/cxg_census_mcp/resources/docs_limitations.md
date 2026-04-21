# Known limitations (v0.3)

This server is intentionally narrow. Things it does **not** do:

- **No expression matrices over the wire.** Aggregate statistics only. For
  per-cell per-gene values, call `export_snippet` and run locally.
- **No embeddings or semantic similarity.** Out of scope for v0.3.
- **No differential expression.** Out of scope for v0.3.
- **No writes / submissions.** Read-only.
- **No authenticated datasets.** Public Census only.
- **No HCA Azul integration.** v0.3 only talks to CZ CELLxGENE Discover.
- **No background jobs.** Long work routes to `export_snippet` instead.
- **Author free text may not match ontology labels.** When in doubt, check
  `query_provenance.resolved_filters` to see what the resolver actually used.
- **Per-dataset licenses vary.** All Census data is CC BY 4.0 at the corpus
  level, but always check individual collection licenses before redistribution.
- **Schema drift happens.** New Census releases occasionally rename or
  restructure columns. The schema-drift rewriter handles the cases we know
  about; new ones land via PR after a `facet-refresh` workflow run.
