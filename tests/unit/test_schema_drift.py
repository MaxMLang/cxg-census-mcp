from pathlib import Path

import pytest
import yaml

from cxg_census_mcp.ontology.rewrites import (
    RewriteContext,
    SchemaDriftRule,
    apply_rewrites,
    rules_for,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "schema_drift_cases.yaml"


@pytest.mark.parametrize("case", yaml.safe_load(FIXTURE.read_text()), ids=lambda c: c["id"])
def test_schema_drift_cases(case):
    ctx = RewriteContext(census_version="stable", schema_version=case["schema_version"])
    operator = case["operator"]
    value = case["value"]
    pred, applied = apply_rewrites(ctx, column=case["column"], operator=operator, value=value)
    assert case["expected_predicate_contains"] in pred
    if case["expected_rule_id"] is None:
        assert applied == []
    else:
        assert case["expected_rule_id"] in applied


def test_rules_for_returns_empty_when_schema_unparseable():
    ctx = RewriteContext(census_version="stable", schema_version="not-a-version")
    assert rules_for(ctx, column="disease_ontology_term_id") == []


def test_schema_drift_rule_validates_specifier():
    rule = SchemaDriftRule(
        id="x",
        schema_range=">=8.0.0",
        column="foo",
        rewrite_kind="eq_to_contains",
    )
    assert rule.id == "x"


def test_apply_rewrites_eq_passthrough_below_range():
    ctx = RewriteContext(census_version="stable", schema_version="5.4.0")
    pred, applied = apply_rewrites(
        ctx,
        column="disease_ontology_term_id",
        operator="eq",
        value="MONDO:0100096",
    )
    assert pred.startswith("disease_ontology_term_id == ")
    assert applied == []
