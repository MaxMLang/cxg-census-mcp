# Schema-drift rewrite format

`src/cxg_census_mcp/data/schema_drift.json` ships an ordered list of rules. Each
rule has these fields, validated by `SchemaDriftRule` on import:

| Field | Type | Purpose |
|---|---|---|
| `id` | string | Stable identifier surfaced in `schema_rewrites_applied` |
| `schema_range` | PEP 440 specifier | Which schema versions this rule applies to (e.g. `>=7.0.0`) |
| `column` | string | Census column the rule rewrites |
| `condition` | `value_is_curie` \| `always` | When to apply the rule |
| `rewrite_kind` | `eq_to_contains` \| `alias` \| `split_delimited` \| `column_swap` | How to rewrite |
| `notes` | string | Free-text rationale for reviewers |

Adding a rule should always be paired with a fixture in
`tests/fixtures/schema_drift/`.
