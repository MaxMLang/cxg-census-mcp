"""Apply schema_drift.json rules when building SOMA value_filter strings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Literal

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, Field

from cxg_census_mcp.utils.curie import is_curie

RewriteKind = Literal["eq_to_contains", "alias", "split_delimited", "column_swap"]


class SchemaDriftRule(BaseModel):
    id: str
    schema_range: str = Field(description="PEP 440 specifier set, e.g. '>=7.0.0'")
    column: str
    condition: Literal["value_is_curie", "always"] = "always"
    rewrite_kind: RewriteKind
    notes: str = ""


def _load_rules() -> list[SchemaDriftRule]:
    raw = resources.files("cxg_census_mcp.data").joinpath("schema_drift.json").read_text()
    data = json.loads(raw)
    rules: list[SchemaDriftRule] = []
    for r in data.get("rules", []) or []:
        rules.append(SchemaDriftRule(**r))
    # Validate specifiers eagerly — fail fast on malformed config.
    for r in rules:
        SpecifierSet(r.schema_range)
    return rules


_RULES = _load_rules()


@dataclass
class RewriteContext:
    census_version: str
    schema_version: str

    @property
    def parsed_schema(self) -> Version | None:
        try:
            return Version(self.schema_version)
        except InvalidVersion:
            return None


def rules_for(ctx: RewriteContext, *, column: str) -> list[SchemaDriftRule]:
    parsed = ctx.parsed_schema
    if parsed is None:
        return []
    matched: list[SchemaDriftRule] = []
    for r in _RULES:
        if r.column != column:
            continue
        if parsed in SpecifierSet(r.schema_range):
            matched.append(r)
    return matched


def apply_rewrites(
    ctx: RewriteContext,
    *,
    column: str,
    operator: Literal["eq", "in"],
    value: str | list[str],
) -> tuple[str, list[str]]:
    """Return ``(predicate, applied_rule_ids)`` for the given column/value.

    The caller passes a logical operator ("eq" or "in") with raw CURIE(s);
    this function emits a SOMA-compatible predicate string after applying any
    schema-drift rewrites that match. The predicate is suitable for
    interpolation into ``soma_filter.and_/or_``.
    """
    from cxg_census_mcp.utils import soma_filter as sf

    matched = rules_for(ctx, column=column)
    applied: list[str] = []

    if operator == "eq":
        assert isinstance(value, str)
        for r in matched:
            if r.rewrite_kind == "eq_to_contains" and (
                r.condition == "always" or (r.condition == "value_is_curie" and is_curie(value))
            ):
                applied.append(r.id)
                return sf.contains(column, value), applied
        return sf.eq(column, value), applied

    # operator == "in"
    assert isinstance(value, list)
    for r in matched:
        if r.rewrite_kind == "eq_to_contains":
            applied.append(r.id)
            parts = [sf.contains(column, v) for v in value if is_curie(v)]
            if parts:
                return sf.or_(*parts), applied
    return sf.curie_in(column, value), applied
