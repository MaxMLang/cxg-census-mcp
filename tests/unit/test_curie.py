import pytest

from cxg_census_mcp.errors import InvalidCurieError
from cxg_census_mcp.utils.curie import is_curie, normalize_curie, parse_curie, prefix_of


def test_is_curie_true_for_uppercase_prefix():
    assert is_curie("CL:0000236")


def test_is_curie_false_for_lowercase_prefix():
    # Strict regex ALL CAPS by design (HsapDv-style strings are handled
    # specially in the seed data validators, not via is_curie).
    assert not is_curie("HsapDv:0000087")


def test_parse_curie():
    assert parse_curie("MONDO:0100096") == ("MONDO", "0100096")


def test_parse_invalid_raises():
    with pytest.raises(InvalidCurieError):
        parse_curie("bad value")


def test_normalize_strips_whitespace():
    assert normalize_curie("  MONDO:0100096  ") == "MONDO:0100096"


def test_normalize_rejects_lowercase_prefix():
    with pytest.raises(InvalidCurieError):
        normalize_curie("mondo:0100096")


def test_prefix_of():
    assert prefix_of("UBERON:0002048") == "UBERON"
