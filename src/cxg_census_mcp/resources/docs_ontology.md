# Ontology resolution model

## Three modes

1. **Exact CURIE.** Input matches `^[A-Z]+:[0-9]+$` → validated via OLS,
   `confidence="exact"`.
2. **Label match.** OLS exact-search scoped to the relevant ontology. Single
   hit → `confidence="label_match"`. Multiple hits → refusal with candidates.
3. **Fuzzy.** OLS fuzzy search + rapidfuzz re-rank with these adjustments:
   - +3.0 exact label, +2.0 exact synonym
   - + label / synonym similarity terms
   - −1.0 obsolete, −2.0 zero cells in pinned Census version
   - top-1 ≥ 4.5 *and* clear winner → return; else refuse with candidates.

## Hint overlay

`data/ontology_hints.json` overrides OLS for community-canonical terms
("covid-19" → MONDO:0100096, "10x v3" → EFO:0009922). Refreshed weekly;
canonical-target changes require human approval.

## Expansion

`expand_term(curie, direction="descendants_inclusive")` walks the ontology DAG
and filters expansions to terms actually present in the pinned Census version.

Expansion width is capped at `CXG_CENSUS_MCP_MAX_EXPANSION_TERMS` (default 256).
Over-cap expansions refuse rather than truncate, because silent truncation
would produce wrong cell counts.

## tissue routing

The tissue router picks one of three strategies:

| Strategy | When | Column used |
|---|---|---|
| `tissue_general` | Queried term is a roll-up; or all expansions roll up cleanly | `tissue_general_ontology_term_id` |
| `tissue` | Specific anatomy term, no general parent | `tissue_ontology_term_id` |
| `dual_column` | Expansion spans both general and specific representations | OR of both columns |

The chosen strategy is reported in every response's `query_provenance.tissue_strategy`.
