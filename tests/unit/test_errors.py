from cxg_census_mcp.errors import (
    CensusMCPError,
    OntologyUnavailableError,
    QueryTooLargeError,
    TermAmbiguousError,
)
from cxg_census_mcp.models.errors import MCPToolError


def test_to_dict_includes_typed_code():
    exc = TermAmbiguousError(
        "two matches",
        candidates=[{"curie": "CL:1", "label": "x", "score": 0.9}],
        retry_with={"term": "CL:1", "confirm_ambiguous": True},
    )
    payload = exc.to_dict()
    assert payload["code"] == "TERM_AMBIGUOUS"
    assert payload["candidates"]
    assert payload["retry_with"]["confirm_ambiguous"] is True


def test_envelope_round_trip():
    err = MCPToolError(
        code="ONTOLOGY_UNAVAILABLE",
        message="OLS unreachable",
        action_hint="Retry shortly.",
    )
    blob = err.model_dump()
    rebuilt = MCPToolError(**blob)
    assert rebuilt.code == "ONTOLOGY_UNAVAILABLE"


def test_default_codes_per_subclass():
    assert OntologyUnavailableError("x").code == "ONTOLOGY_UNAVAILABLE"
    assert QueryTooLargeError("x").code == "QUERY_TOO_LARGE"
    assert CensusMCPError("x").code == "INTERNAL_ERROR"


def test_action_hint_override():
    exc = CensusMCPError("boom", action_hint="Do thing.")
    assert exc.action_hint == "Do thing."
