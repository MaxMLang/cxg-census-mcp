import pytest

from cxg_census_mcp.errors import UnknownColumnError
from cxg_census_mcp.utils import soma_filter as sf


def test_eq_quotes_strings():
    assert sf.eq("cell_type", "B cell") == "cell_type == 'B cell'"


def test_eq_bool_unquoted():
    assert sf.eq("is_primary_data", True) == "is_primary_data == True"


def test_eq_int_unquoted():
    assert sf.eq("soma_joinid", 12) == "soma_joinid == 12"


def test_in_with_curies():
    out = sf.curie_in("disease_ontology_term_id", ["MONDO:0100096", "MONDO:0004975"])
    assert "MONDO:0100096" in out and "in [" in out


def test_in_rejects_non_curies():
    with pytest.raises(UnknownColumnError):
        sf.curie_in("disease_ontology_term_id", ["covid"])


def test_in_rejects_empty_list():
    with pytest.raises(UnknownColumnError):
        sf.in_("dataset_id", [])


def test_invalid_column_rejected():
    with pytest.raises(UnknownColumnError):
        sf.eq("Cell Type; DROP TABLE", "X")


def test_contains_for_multi_value_column():
    assert (
        sf.contains("disease_ontology_term_id", "MONDO:0100096")
        == "'MONDO:0100096' in disease_ontology_term_id"
    )


def test_and_or_compose():
    a = sf.eq("sex", "male")
    b = sf.eq("is_primary_data", True)
    assert sf.and_(a, b) == "(sex == 'male') and (is_primary_data == True)"
    assert sf.or_(a, b) == "(sex == 'male') or (is_primary_data == True)"


def test_and_with_single_part_is_unwrapped():
    assert sf.and_("a == 1") == "a == 1"


def test_and_filters_empty_strings():
    assert sf.and_("", "a == 1", "") == "a == 1"


def test_string_value_escapes_single_quote():
    out = sf.eq("dataset_id", "abc'def")
    assert "abc\\'def" in out
