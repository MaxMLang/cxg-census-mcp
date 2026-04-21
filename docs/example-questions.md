# Example questions

Prompts that show off what the server can actually do. Each one is written
the way you'd ask it in Cursor / Claude / MCP Inspector — paste it verbatim,
then watch which tools the agent picks and what comes back in the
`ResponseEnvelope`.

The interesting bits to inspect on every response:

- `query_provenance.value_filter` — the literal SOMA expression that ran
- `query_provenance.resolved_filters` — what your free-text terms actually
  resolved to (CURIE + label + path: hint vs OLS exact vs OLS fuzzy)
- `query_provenance.tissue_field_used` + `tissue_strategy` — `tissue` vs
  `tissue_general` routing
- `query_provenance.estimated_cells_pre_query` vs `actual_cells_returned`
- `query_provenance.schema_rewrites_applied` — schema-version drift fixes
- `warnings` — harmonization caveats, expansion no-ops, planner downgrades
- `attribution`, `unaffiliated`, `disclaimer` — keep these visible to users
- `call_id` — feed into `export_snippet` for the local-Python escape hatch

Read [`docs/tool-reference.md`](tool-reference.md) for the full tool list,
[`docs/architecture.md`](architecture.md) for tier semantics, and
[`docs/error-model.md`](error-model.md) for the structured-error contract.

> Tip: have the agent read the `cxg-census-mcp://docs/workflow` resource
> once at the start of a long session. It's a short prompt-prefix that
> teaches it to call `resolve_term` before guessing CURIEs and to cite
> dataset titles + DOIs from `list_datasets` envelopes.

---

## 1. Sanity wiring (run these once)

Just enough to confirm the server is alive and which Census version it's
pointed at. Skip after the first session.

- *"Census summary, please."*
  → `census_summary`. Confirms version, schema, organism list, total cells.
- *"What are the server's caps and current cache stats?"*
  → `get_server_limits`. Both static config and live counters (cap
  rejections, cache hit/miss, tool-call totals).

---

## 2. Multi-step biology workflows

These are the questions worth pasting. Each one forces the agent through
**multiple tools**, ontology resolution, planner cost-estimation, and at
least one envelope field worth verifying.

### 2.1 Tumor-associated B cells in human lung cancer

> *I'm interested in tumor-associated B cells in human lung. Find the five
> largest lung cancer datasets that contain B cells, then for each one
> tell me how many B cells it has, what the dominant `author_cell_type`
> labels are, and which collection / DOI it came from.*

Forces the agent to chain:
1. `resolve_term("lung cancer", facet="disease")` → `MONDO:0008903` (or
   refusal with candidates if ambiguous; check `code: TERM_AMBIGUOUS`).
2. `list_datasets(cell_type=CL:0000236, tissue=UBERON:0002048,
   disease=<resolved>)` → top-N by `n_cells`.
3. For each dataset_id: `count_cells(cell_type=CL:0000236,
   dataset_id=<uuid>)`.
4. For each dataset_id: `preview_obs(filters={cell_type=CL:0000236,
   dataset_id=<uuid>}, columns=["author_cell_type",
   "author_cluster_label"], limit=200)` → harmonization escape hatch
   (see §6).

What to verify in the envelopes:
- Every resolved term has `resolution_path` ∈ {`exact-curie`,
  `hint-overlay`, `ols-exact`} and `confidence` is not `fuzzy`.
- Each `list_datasets` row carries `collection_doi` and `citation` —
  cite those, not invented references.
- `tissue_field_used == "tissue_general_ontology_term_id"` (lung is
  routed through the general column; see `tissue_strategy`).

### 2.2 Healthy vs COVID-19 lung at cell-type resolution

> *Compare immune-cell composition of healthy human lung vs COVID-19
> human lung. Give me per-cell-type counts for both cohorts, normalized
> to total cells in each cohort, and flag any cell type whose share at
> least doubles in COVID.*

Exercises:
- Two parallel `count_cells(... , group_by="cell_type")` calls — one
  with `disease=PATO:0000461` (normal), one with `disease=MONDO:0100096`
  (COVID-19).
- Forces the agent to do the normalization + fold-change in its head
  (or in code), then explain it. Don't accept "macrophages double" — ask
  for the `cell_type_ontology_term_id` and the absolute counts.
- `query_provenance.schema_rewrites_applied` should include
  `disease_multi_value_v7` because COVID-19 is split across multiple
  values in schema ≥7.

### 2.3 Cytotoxicity markers in CD8 T cells across the gut

> *For the top three datasets with the most CD8+ T cells in human gut,
> give me the mean expression of GZMB, PRF1, and GNLY per dataset. Tell
> me which dataset has the most cytotoxic profile and cite its DOI.*

Chain:
1. `resolve_term("CD8+ T cell")` → `CL:0000625`.
2. `list_datasets(cell_type=CL:0000625, tissue=UBERON:0000059,
   limit=3)` (large intestine).
3. For each dataset: `aggregate_expression(filters={cell_type=CL:0000625,
   dataset_id=<uuid>}, gene_ids=[ENSG00000100453, ENSG00000180644,
   ENSG00000115008], group_by="dataset_id")` → mean +
   fraction_expressing.
4. Sort by `mean(GZMB)` and quote the citation from step 2.

Tier-2 calls (`aggregate_expression`) are the slow ones. Watch for
streamed `progress` notifications if your client supports them, and
check `query_provenance.estimated_runtime_ms` against actual.

### 2.4 Cross-tissue macrophage marker panel

> *Show me a heatmap-ready table: for each of CD68, CD163, MRC1, MARCO,
> and ITGAX (CD11c), give me mean expression in macrophages across
> blood, lung, brain, liver, gut, and spleen in healthy adult humans.*

Single `aggregate_expression(cell_type=CL:0000235,
disease=PATO:0000461, gene_ids=[5 IDs], group_by="tissue_general")`
call. The interesting envelope fields:
- `defaults_applied.is_primary_data` should be `True` (no donor
  double-counting).
- `actual_group_count` ≈ 6 (some tissues may be absent — watch for
  empty groups).
- `attribution` lists every dataset that contributed cells to any
  group. Surface this; it's the citation contract.

### 2.5 The "is this even possible?" planner question

> *Mean expression of every protein-coding gene across every cell type
> in the entire Census.*

Deliberately un-runnable. Should:
1. Get refused with a structured error (`TOO_MANY_GENES` or
   `QUERY_TOO_LARGE`) carrying a `call_id` and an `action_hint`.
2. Follow up with *"Give me a Python snippet I can run locally for
   that"* → `export_snippet(call_id=<from above>)`. Returns runnable
   `cellxgene_census` code that streams X chunks and aggregates per
   group locally. This is the production escape hatch — every cap
   rejection is paired with a snippet path.

---

## 3. Ontology workflows

These showcase the OLS4 + hint-overlay + presence-filter machinery.

### 3.1 Disambiguation that the server *should* refuse

> *How many "T cells" are there in lung?*

`resolve_term("T cell", facet="cell_type")` should not silently pick
`CL:0000084`. With ambiguous text the server returns a
`ResolutionRefusal` with `code: TERM_AMBIGUOUS` and a candidate list
(α-β T cell, γ-δ T cell, regulatory T cell, …). The agent must pick one
and re-call with the CURIE. Confirm the refusal payload — silent
auto-pick is a bug.

### 3.2 DAG expansion that *will* no-op (and should warn)

> *Count all B-lineage cells (descendants of `CL:0000236`) in human
> lung.*

`expand_term("CL:0000236", direction="descendants_inclusive")` returns
~96 CL descendants, but `presence.filter_present` then drops every one
because no contributing dataset annotated cells with finer CURIEs in
the harmonized `cell_type_ontology_term_id` column. The envelope must
carry the *expansion no-op* warning verbatim:

> Expansion 'descendants_inclusive' of CL:0000236 ('B cell') was a
> no-op: all 96 ontology descendants are absent from this Census
> version's harmonized field…

Use this to verify the warning fires. Then escalate to §6.

### 3.3 Term lookup for a casual abbreviation

> *What CURIE does "covid" resolve to as a disease, and what's its
> definition?*

Two-call chain: `resolve_term(text="covid", facet="disease")` →
`MONDO:0100096`, `resolution_path: hint-overlay`; then
`term_definition(curie="MONDO:0100096")`. Useful for evaluating the
hint overlay quality without going to OLS.

---

## 4. Provenance / reproducibility verification

Don't take the model's prose for anything — make it cite the envelope.

- *"Show me the literal `value_filter` that ran for the last query."*
  → `query_provenance.value_filter`.
- *"What did 'lung' resolve to and which tissue column was used?"*
  → `query_provenance.resolved_filters.tissue.curie/label/path` plus
  `query_provenance.tissue_field_used` (`tissue_general_…` for lung).
- *"How many cells did the planner estimate vs how many were actually
  returned, and was that within 2x?"*
  → `estimated_cells_pre_query` vs `actual_cells_returned`. If the
  ratio is wild, the facet catalog is stale and needs a refresh.
- *"Was `is_primary_data == True` applied? If not, donors may be
  double-counted across datasets."*
  → `is_primary_data_applied`.
- *"Give me the call_id for the last query so I can reproduce it."*
  → top-level `call_id`. Pass it to `export_snippet` for a runnable
  Python equivalent.

---

## 5. Cap-rejection / refusal contracts

These should refuse cleanly with structured errors. Use them to confirm
the safety rails fire.

- *"Give me the raw expression matrix for B cells in lung."*
  → Refuses with a hint to use `aggregate_expression` or
  `export_snippet`.
- *"Use Census version `1900-01-01`."*
  → `UNKNOWN_CENSUS_VERSION` with the actual visible versions in
  `retry_with`.
- *"Filter by `made_up_field` = 1."*
  → `UNKNOWN_COLUMN`.
- *"Use cell type 'flarbnax cell'."*
  → `TERM_NOT_FOUND` with fuzzy candidates and a pointer to
  `list_available_values`.
- *"Aggregate expression of 5,000 genes across all human cells."*
  → `TOO_MANY_GENES` (or `QUERY_TOO_LARGE` depending on
  cell-count). Pair with `export_snippet(call_id=…)`.

---

## 6. The Census harmonization caveat (read this once)

Census stores the *harmonized* ontology label that each contributing
dataset already had — it does not re-annotate cells against the full
ontology. So a "memory B cell" study that originally annotated cells as
`CL:0000787` may end up with those cells stored under the parent
`CL:0000236` (B cell) in the harmonized column. Descendant expansion
will dutifully expand `CL:0000236` → 96 CL terms and then drop every
single one because none of them are populated in
`cell_type_ontology_term_id`.

The server emits an explicit warning when this happens. When you see
it, the right next move is one of:

- *"Show me the `author_cell_type` and `author_cluster_label` values
  for B cells in dataset `<uuid>`."*
  → `preview_obs(filters={cell_type: CL:0000236, dataset_id: <uuid>},
  columns=["author_cell_type", "author_cluster_label"], limit=500)`.
  This is how you recover the dataset-original subtype labels that the
  Census harmonization layer flattened away.
- *"Which datasets actually annotate B cell subtypes at finer
  resolution in the harmonized column?"*
  → Resolve a subtype CURIE (e.g. `CL:0000787` memory B cell) with
  `resolve_term`, then call `count_cells(cell_type=CL:0000787,
  expand="exact")`. Zero across the whole Census ⇒ that subtype is
  never populated in the harmonized field; you need
  `author_cell_type` via `preview_obs`.
- *"Which ontology terms are actually populated for `cell_type` in
  this Census version?"*
  → `list_available_values(facet="cell_type")`.

This caveat applies to **every** ontology facet (`cell_type`, `tissue`,
`disease`, `assay`, `development_stage`, `self_reported_ethnicity`),
not just `cell_type`. The same warning fires for any of them.

---

## 7. Suggested system / prompt prefix

Drop this once at the start of a session for consistent agent behaviour:

> You have access to the `cxg-census` MCP server, which queries the CZ
> CELLxGENE Discover Census. Read the `cxg-census-mcp://docs/workflow`
> resource once before answering.
>
> Rules:
> 1. For any cell-type, tissue, disease, or assay term mentioned by the
>    user, call `resolve_term` first and only trust the returned CURIE.
>    Do not guess CURIEs from memory.
> 2. When you cite a dataset, include the title, `collection_name`, and
>    `collection_doi` exactly as returned by `list_datasets`.
> 3. Show counts and provenance values verbatim from tool envelopes.
>    Do not paraphrase numbers.
> 4. If the server warns about a harmonization no-op (descendant
>    expansion produced no in-Census terms), surface that warning to
>    the user and propose `preview_obs` against `author_cell_type`
>    instead of silently using the parent term.
> 5. If a query is refused with a `call_id`, offer
>    `export_snippet(call_id)` as the local-Python alternative.
> 6. Always preserve the `attribution`, `unaffiliated`, and
>    `disclaimer` strings from the envelope when summarizing results
>    for the user — they are the upstream-license contract.
