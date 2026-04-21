# Error model

Every tool error is returned as a structured payload:

```json
{
  "code": "TERM_AMBIGUOUS",
  "message": "Multiple ontology terms match 'MS'; please confirm.",
  "action_hint": "Pick a CURIE from `candidates` and re-call with confirm_ambiguous=true.",
  "retry_with": {"term": "MONDO:0005301", "confirm_ambiguous": true},
  "candidates": [
    {"curie": "MONDO:0005301", "label": "multiple sclerosis", "score": 1.0},
    {"curie": "MONDO:0019513", "label": "Marfan syndrome", "score": 0.65}
  ],
  "call_id": null
}
```

## Codes you'll see

| Code | Meaning | Fix |
|---|---|---|
| `TERM_NOT_FOUND` | No ontology term matches the input | Try a synonym or `list_available_values` |
| `TERM_AMBIGUOUS` | Multiple plausible matches | Pick a CURIE from `candidates`, set `confirm_ambiguous=true` |
| `ONTOLOGY_UNAVAILABLE` | OLS unreachable, hint fallback also failed | Retry shortly |
| `EXPANSION_TOO_WIDE` | Term expanded to > `MAX_EXPANSION_TERMS` | Use a more specific term or `expand="exact"` |
| `QUERY_TOO_LARGE` | Estimated cells / runtime exceeds caps | Call `export_snippet(call_id)` |
| `GROUP_CARDINALITY_TOO_HIGH` | `group_by` yields too many groups | Use a coarser `group_by` |
| `TOO_MANY_GENES` | Gene list exceeds `MAX_EXPRESSION_GENES` | Batch the call |
| `INVALID_FILTER` | Pydantic validation failure | Fix the offending field |
| `INVALID_CURIE` | Input doesn't match `^[A-Z]+:[0-9]+$` | Pass a valid CURIE |
| `UNKNOWN_COLUMN` | Column not in summary_cell_counts | See `census_summary` |
| `CENSUS_UNAVAILABLE` | No Census handle | Install `[census]` extras or set `CXG_CENSUS_MCP_MOCK_MODE=1` |
| `CALL_ID_NOT_FOUND` | `export_snippet(call_id)` after TTL expiry | Re-run the originating tool |
| `CANCELLED` | Client cancelled the request | No remediation needed |
