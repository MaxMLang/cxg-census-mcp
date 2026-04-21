# Census schema cheat-sheet

This server exposes the CZ CELLxGENE Discover Census, schema 6+ (currently
pinned by `CXG_CENSUS_MCP_CENSUS_VERSION`).

## Ontology columns

| Facet | Ontology | ID column | Label column |
|---|---|---|---|
| `cell_type` | Cell Ontology (CL) | `cell_type_ontology_term_id` | `cell_type` |
| `tissue` | UBERON | `tissue_ontology_term_id` | `tissue` |
| `tissue_general` | UBERON (roll-up) | `tissue_general_ontology_term_id` | `tissue_general` |
| `disease` | MONDO + PATO | `disease_ontology_term_id` | `disease` |
| `assay` | EFO (assay subset) | `assay_ontology_term_id` | `assay` |
| `development_stage` | HsapDv / MmusDv | `development_stage_ontology_term_id` | `development_stage` |
| `self_reported_ethnicity` | HANCESTRO | `self_reported_ethnicity_ontology_term_id` | `self_reported_ethnicity` |

## Categorical columns

`sex`, `suspension_type`, `is_primary_data`, `dataset_id`, `donor_id`,
`collection_id`.

## `tissue` vs `tissue_general`

Census denormalises tissue to two columns: `tissue` for specific anatomy and
`tissue_general` for roll-up terms (~50). The server picks the right column
automatically; see `docs/ontology` for details.

## `is_primary_data`

Census can include duplicate cells across overlapping datasets. By default
this server applies `is_primary_data == True` to deduplicate. Pass
`is_primary_data: false` in your `FilterSpec` to disable.
