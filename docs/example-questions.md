# Example questions for the Census MCP

Copy-paste prompts for Claude / Cursor / MCP Inspector. Each section lists the
tools you should see and a few fields worth checking in the JSON.

> Optional: have the agent read `cxg-census-mcp://docs/workflow` once before a long session.

---

## 1. Sanity / introspection

Quick checks that confirm wiring is correct before you trust any number.

- *"Give me a Census summary."*
  → `census_summary`. Look for `total_cells ≈ 217M`, `schema_version 2.4.0`,
  `build_date 2025-11-08`, five organisms.
- *"What Census versions are available?"*
  → `get_census_versions`.
- *"What are the server's caps and current cache stats?"*
  → `get_server_limits`. Returns both the cap config and runtime counters
  (tool calls, cap rejections, cache hit/miss).
- *"What ontology fields can I filter by?"*
  → `list_available_values` (no value), or `cxg-census-mcp://docs/schema` resource.

---

## 2. Resolution / disambiguation (no Census reads)

Cheap calls that just hit OLS + the local hint overlay. Use these when you
want to confirm what a free-text term will resolve to *before* spending a
Census query on it.

- *"What CURIE does 'B cell' resolve to?"*
  → `resolve_term`. Should return `CL:0000236` with `confidence: exact`.
- *"Resolve 'covid' as a disease."*
  → `resolve_term(facet=disease)`. Should return `MONDO:0100096` (COVID-19).
- *"Resolve 'tcell' — is it ambiguous?"*
  → `resolve_term`. Likely returns multiple candidates with
  `code: TERM_AMBIGUOUS` so the agent has to pick.
- *"What's the definition of `CL:0000084`?"*
  → `term_definition`. T cell.
- *"List descendants of `CL:0000236` (B cell)."*
  → `expand_term`. Should give plasma cells, memory B cells, naive B cells, etc.

---

## 3. Cell counts (Tier 0 — fast)

Index-only counts via `axis_query.n_obs`. Each one should be sub-second after
the first warm call.

- *"How many B cells are in human lung?"*
  → `count_cells`. Expect ~97,465.
- *"How many cells in the Census come from healthy donors?"*
  → `count_cells` with `disease: PATO:0000461` (normal).
- *"Total mouse cells across all tissues."*
  → `count_cells(organism=mus_musculus)`.
- *"Cells from 10x Genomics 3' v3 in human peripheral blood."*
  → Resolves `EFO:0009922` and `UBERON:0000178`.

---

## 4. Grouped counts (Tier 0/1)

Returns a per-group breakdown with **labels** for any ontology CURIE or
dataset_id key.

- *"Break down B cells in lung by dataset, top 10."*
  → `count_cells(... , group_by="dataset_id")`. Each row shows the dataset
  title (e.g. *"The single-cell lung cancer atlas (LuCA) -- extended atlas"*).
- *"What cell types are most common in human lung?"*
  → `count_cells(... , group_by="cell_type")`. Should put alveolar
  macrophages and AT2 cells near the top.
- *"Distribution of T cell subsets across tissues in healthy humans."*
  → `count_cells(cell_type=CL:0000084, group_by="tissue_general")`.
- *"How many B cells per assay technology?"*
  → `count_cells(cell_type=CL:0000236, group_by="assay")`.

---

## 5. Dataset discovery

Returns titles, collection name, DOI, and citation alongside cell counts.

- *"List the top 5 datasets that contain B cells from human lung."*
  → `list_datasets`. Each result has `title`, `collection_name`,
  `collection_doi`, `citation`, `n_cells` (matching filter), and
  `n_cells_total` (whole dataset).
- *"Which mouse brain datasets are largest?"*
  → `list_datasets(organism=mus_musculus, tissue=UBERON:0000955)`.
- *"Show me datasets covering COVID-19 lung tissue."*

---

## 6. Gene coverage

- *"How many datasets contain TP53?"*
  → `gene_coverage(["ENSG00000141510"])`. Expect ~1083 datasets.
- *"Are CD19, CD20, CD3E, and CD8A all present in the human var?"*
  → `gene_coverage(["ENSG00000177455", "ENSG00000156738", "ENSG00000198851", "ENSG00000153563"])`.
- *"Compare gene coverage of TP53 vs MYC."*

---

## 7. Aggregate expression (Tier 2 — slower, 10-60s)

Per-(group, gene) mean and fraction-expressing across the matched cells.
Streams progress notifications when the client supports them.

- *"Mean expression of CD19 across B cells in human lung."*
  → `aggregate_expression(cell_type=CL:0000236, gene_ids=[CD19], group_by="cell_type")`.
  Note: in most lung datasets B cells are annotated only at the parent
  `CL:0000236` level (see section 12). To resolve subtypes you usually need
  to drop down to a single dataset's `author_cell_type` column via
  `preview_obs`.
- *"Compare TP53 and MDM2 expression across cell types in colorectal cancer."*
  → `aggregate_expression(disease=MONDO:0005575, gene_ids=[TP53, MDM2], group_by="cell_type")`.
- *"Fraction of macrophages expressing CD68 across tissues."*
  → `aggregate_expression(cell_type=CL:0000235, group_by="tissue_general")`.
- *"Marker gene expression for the canonical PBMC panel across blood cell types."*

Each result row carries `group`, `group_label`, `gene_id`, `gene_symbol`,
`n_cells`, `mean`, `fraction_expressing`.

---

## 8. Cap-rejected queries (good for testing the snippet path)

These should refuse with a structured error and a `call_id` you can pass to
`export_snippet`.

- *"Mean expression of all 20,000 protein-coding genes across cell types in
  the entire Census."*
  → Refuses (`TOO_MANY_GENES` or `QUERY_TOO_LARGE`). Then:
- *"Give me a Python snippet I can run locally for that last query."*
  → `export_snippet(call_id=...)`. Returns runnable `cellxgene_census`
  code that streams X chunks and aggregates per group.

---

## 9. Multi-step workflows (good for evaluating LLM behaviour)

These exercise the agent's planning, not just one tool.

- *"I'm interested in tumor-associated B cells. Find the largest human lung
  cancer datasets that contain B cells, then tell me how many B cells each
  one has and what the dominant B cell subtypes are within them."*
- *"Compare immune cell composition of healthy vs COVID-19 human lung at the
  cell-type level."*
- *"For the top 3 datasets with the most CD8+ T cells in human gut, give me
  the mean expression of GZMB and PRF1 per dataset."*
- *"Which collection has the most diverse representation of human cell types across the most tissues?"*

---

## 10. Provenance / verification questions

Don't take the model's word for anything — verify against the envelope.

- *"Show me the value_filter that ran for the last query."*
  → Look at `query_provenance.value_filter` in the envelope.
- *"What did 'lung' resolve to and which tissue column was used?"*
  → `query_provenance.resolved_filters.tissue` +
  `query_provenance.tissue_field_used`.
- *"How many cells did the planner estimate vs how many were actually returned?"*
  → `estimated_cells_pre_query` vs `actual_cells_returned`.
- *"Was `is_primary_data == True` applied?"*
  → `is_primary_data_applied`.

---

## 11. Things the server is intentionally bad at

These should refuse cleanly. Use them to confirm error semantics.

- *"Give me the raw expression matrix for B cells in lung."*
  → Refuses; suggests `aggregate_expression` or `export_snippet`.
- *"Use Census version 1900-01-01."*
  → Refuses with `UNKNOWN_CENSUS_VERSION` and lists the actual versions.
- *"Filter by `made_up_field`."*
  → Refuses with `UNKNOWN_COLUMN`.
- *"Use cell type 'flarbnax cell'."*
  → Refuses with `TERM_NOT_FOUND` and suggests `list_available_values` or
  fuzzy candidates.

---

## 12. The Census harmonization caveat (read this once)

Census stores the *harmonized* ontology label that each contributing dataset
already had — it does not re-annotate cells against the full ontology. So
asking for "descendants of `CL:0000236` (B cell)" with
`expand="descendants_inclusive"` will dutifully expand to ~96 CL descendants
(memory B, naive B, plasmablast, germinal center B, plasma cell, …) and then
silently *drop every single one* in `presence.filter_present`, because no
contributing dataset annotated cells with those finer CURIEs in the
`cell_type_ontology_term_id` column.

The server now flags this for you. Look for a warning like:

> Expansion 'descendants_inclusive' of CL:0000236 ('B cell') was a no-op:
> all 96 ontology descendants are absent from this Census version's
> harmonized field, so the filter reduces to just CL:0000236 …

When you see that warning, the right next move is one of:

- *"Show me the `author_cell_type` values for B cells in dataset X."*
  → `preview_obs(filters={cell_type: CL:0000236, dataset_id: "<uuid>"},
  columns=["author_cell_type", "author_cluster_label"])`.
- *"Which datasets actually annotate B cell subtypes at finer resolution?"*
  → Resolve a subtype CURIE first (e.g. `CL:0000785` memory B cell) with
  `resolve_term`, then call `count_cells` with that CURIE and
  `expand="exact"`. If the count is zero across the whole Census, the
  subtype is not annotated anywhere in the harmonized field.
- Use `list_available_values(facet="cell_type")` to see exactly which
  ontology terms are populated in the current Census version.

This caveat applies to **every** ontology facet (`cell_type`, `tissue`,
`disease`, `assay`, `development_stage`, `self_reported_ethnicity`), not
just `cell_type`. The same warning fires for any of them when descendant
expansion produces no usable terms.

---

## Suggested prompt prefix

When you want consistent, well-grounded behaviour from the agent:

> You have access to the `census` MCP server, which queries the CZ CELLxGENE
> Discover Census. Always start by reading the
> `cxg-census-mcp://docs/workflow` resource. For any cell-type, tissue, disease,
> or assay term mentioned by the user, call `resolve_term` first and only
> trust the returned CURIE. Cite dataset titles and DOIs from
> `list_datasets` results when discussing specific datasets. Show counts
> and provenance values verbatim from tool envelopes — don't paraphrase
> numbers.
