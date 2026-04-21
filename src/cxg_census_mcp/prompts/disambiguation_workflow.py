"""Prompt template for handling ambiguous-term refusals."""

DISAMBIGUATION_PROMPT = """\
The previous tool call returned a `TERM_AMBIGUOUS` error. Do not retry
silently — the resolver could not pick between several candidates.

Walk the user through the candidates list and ask which they meant.
Each candidate has:
  * `curie`: the unique ontology identifier
  * `label`: the canonical ontology label
  * `score`: the resolver's confidence (higher = more likely)

Once the user picks (or is silent for too long and the highest-score candidate
is clearly the intended one), re-call the tool with the chosen CURIE and
`confirm_ambiguous: true`.

If the candidates all look implausible, the user's term may not exist in the
ontology at all — try `list_available_values` to surface what's actually
present in this Census version.
"""
