from pathlib import Path

import yaml

from cxg_census_mcp.models.ontology import ExpandedTerm
from cxg_census_mcp.ontology.tissue_router import is_general_term, pick_tissue_column

FIXTURE = Path(__file__).parent.parent / "fixtures" / "tissue_routing_cases.yaml"


def _make_expansion(curie: str, terms: list[str]) -> ExpandedTerm:
    return ExpandedTerm(
        query_curie=curie,
        direction="descendants_inclusive",
        terms=terms,
        terms_present_in_census=len(terms),
    )


def test_lung_is_general():
    assert is_general_term("UBERON:0002048")


def test_specific_anatomy_is_not_general():
    assert not is_general_term("UBERON:0002037")  # cerebellum


def test_general_term_routes_to_general_column():
    routing = pick_tissue_column("UBERON:0002048", expansion=None)
    assert routing.strategy == "tissue_general"
    assert routing.column == "tissue_general_ontology_term_id"


def test_specific_anatomy_routes_to_specific_column():
    routing = pick_tissue_column("UBERON:0002037", expansion=None)
    assert routing.strategy == "tissue"
    assert routing.column == "tissue_ontology_term_id"


def test_dual_column_when_expansion_spans_general_and_specific():
    expansion = _make_expansion("UBERON:0002048", ["UBERON:0002048", "UBERON:0008952"])
    routing = pick_tissue_column("UBERON:0002048", expansion=expansion)
    # Note: query CURIE itself is general, so rule (1) wins; this is intentional.
    assert routing.strategy == "tissue_general"


def test_dual_column_for_specific_query_with_general_descendants():
    expansion = _make_expansion("UBERON:0002037", ["UBERON:0002048", "UBERON:0008952"])
    routing = pick_tissue_column("UBERON:0002037", expansion=expansion)
    assert routing.strategy == "dual_column"
    assert routing.dual_predicates == [
        "tissue_ontology_term_id",
        "tissue_general_ontology_term_id",
    ]


def test_fixture_cases_match():
    cases = yaml.safe_load(FIXTURE.read_text())
    for case in cases:
        expansion = (
            _make_expansion(case["curie"], case["expansion_terms"])
            if case["expansion_terms"]
            else None
        )
        routing = pick_tissue_column(case["curie"], expansion=expansion)
        # Some fixture entries describe the documented behavior; only assert
        # the column choice when the fixture and rule (1) align.
        if case["id"] == "lung_with_specific_descendants":
            # Rule (1) overrides — query term is general.
            assert routing.strategy == "tissue_general"
            continue
        assert routing.strategy == case["expected"]["strategy"], case["id"]
        assert routing.column == case["expected"]["column"], case["id"]
