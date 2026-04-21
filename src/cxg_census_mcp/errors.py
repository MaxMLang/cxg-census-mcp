"""MCP-facing errors: stable ``code``, ``action_hint``, optional ``retry_with``."""

from __future__ import annotations

from typing import Any


class CensusMCPError(Exception):
    """Base for typed tool errors."""

    code: str = "INTERNAL_ERROR"
    action_hint: str = "Retry the request later."

    def __init__(
        self,
        message: str,
        *,
        action_hint: str | None = None,
        retry_with: dict[str, Any] | None = None,
        candidates: list[dict[str, Any]] | None = None,
        call_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if action_hint is not None:
            self.action_hint = action_hint
        self.retry_with = retry_with
        self.candidates = candidates
        self.call_id = call_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "action_hint": self.action_hint,
            "retry_with": self.retry_with,
            "candidates": self.candidates,
            "call_id": self.call_id,
        }


# --- Resolver / ontology -------------------------------------------------------


class TermNotFoundError(CensusMCPError):
    code = "TERM_NOT_FOUND"
    action_hint = "Check spelling, try a synonym, or call list_available_values."


class TermAmbiguousError(CensusMCPError):
    code = "TERM_AMBIGUOUS"
    action_hint = "Pick a CURIE from `candidates` and re-call with confirm_ambiguous=True."


class OntologyUnavailableError(CensusMCPError):
    code = "ONTOLOGY_UNAVAILABLE"
    action_hint = "Retry shortly; OLS may be temporarily unreachable."


class TermNotInCensusError(CensusMCPError):
    code = "TERM_NOT_IN_CENSUS"
    action_hint = "Choose a different Census version or a related term that has cells."


class ExpansionTooWideError(CensusMCPError):
    code = "EXPANSION_TOO_WIDE"
    action_hint = "Narrow the term, set expand='exact', or use export_snippet."


# --- Planner / caps ------------------------------------------------------------


class QueryTooLargeError(CensusMCPError):
    code = "QUERY_TOO_LARGE"
    action_hint = "Use export_snippet to run this locally."


class GroupCardinalityTooHighError(CensusMCPError):
    code = "GROUP_CARDINALITY_TOO_HIGH"
    action_hint = "Choose a coarser group_by or filter further before grouping."


class TooManyGenesError(CensusMCPError):
    code = "TOO_MANY_GENES"
    action_hint = "Reduce the gene_ids list or call aggregate_expression in batches."


# --- Validation ----------------------------------------------------------------


class InvalidFilterError(CensusMCPError):
    code = "INVALID_FILTER"
    action_hint = "Fix the offending field per `message` and retry."


class InvalidCurieError(CensusMCPError):
    code = "INVALID_CURIE"
    action_hint = "Pass a CURIE matching ^[A-Z]+:[0-9]+$."


class UnknownColumnError(CensusMCPError):
    code = "UNKNOWN_COLUMN"
    action_hint = "Pick a column listed in census_summary().columns."


# --- Execution -----------------------------------------------------------------


class CensusUnavailableError(CensusMCPError):
    code = "CENSUS_UNAVAILABLE"
    action_hint = (
        "The Census handle is not available. Install the optional 'census' extras "
        "or set CXG_CENSUS_MCP_MOCK_MODE=1 for development."
    )


class CallIdNotFoundError(CensusMCPError):
    code = "CALL_ID_NOT_FOUND"
    action_hint = "Re-run the originating tool to obtain a fresh call_id."


class CancelledError(CensusMCPError):
    code = "CANCELLED"
    action_hint = "Cancellation requested by client; no remediation needed."


__all__ = [
    "CallIdNotFoundError",
    "CancelledError",
    "CensusMCPError",
    "CensusUnavailableError",
    "ExpansionTooWideError",
    "GroupCardinalityTooHighError",
    "InvalidCurieError",
    "InvalidFilterError",
    "OntologyUnavailableError",
    "QueryTooLargeError",
    "TermAmbiguousError",
    "TermNotFoundError",
    "TermNotInCensusError",
    "TooManyGenesError",
    "UnknownColumnError",
]
