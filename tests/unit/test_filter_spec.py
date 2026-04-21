import pytest
from pydantic import ValidationError

from cxg_census_mcp.models.filters import FilterSpec, MultiTermFilter, TermFilter


def test_term_filter_requires_one_of_term_or_text():
    with pytest.raises(ValidationError):
        TermFilter()
    with pytest.raises(ValidationError):
        TermFilter(term="CL:1", text="t cell")


def test_term_filter_accepts_term_only():
    tf = TermFilter(term="CL:0000236")
    assert tf.term == "CL:0000236" and tf.expand == "exact"


def test_multi_term_filter_requires_min_length():
    with pytest.raises(ValidationError):
        MultiTermFilter(any_of=[])


def test_filter_spec_default_organism_and_primary_data():
    spec = FilterSpec()
    assert spec.organism == "homo_sapiens"
    assert spec.is_primary_data is True


def test_filter_spec_extra_fields_rejected():
    with pytest.raises(ValidationError):
        FilterSpec.model_validate({"organism": "homo_sapiens", "bogus": True})


def test_filter_spec_dataset_id_accepts_list():
    spec = FilterSpec(dataset_id=["a", "b"])
    assert spec.dataset_id == ["a", "b"]


def test_is_empty_true_for_default():
    assert FilterSpec().is_empty()


def test_is_empty_false_when_filter_set():
    spec = FilterSpec(cell_type=TermFilter(term="CL:0000236"))
    assert not spec.is_empty()
