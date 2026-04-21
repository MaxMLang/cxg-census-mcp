"""Build SOMA ``value_filter`` strings from validated columns + literals only."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from cxg_census_mcp.errors import UnknownColumnError
from cxg_census_mcp.utils.curie import is_curie

_ALLOWED_COLUMN = re.compile(r"^[a-z][a-z0-9_]*$")


def _quote(value: str | bool | int) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return str(value)
    # strings: SOMA tolerates either single or double quotes; escape any quotes
    safe = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{safe}'"


def _check_column(name: str) -> str:
    if not _ALLOWED_COLUMN.match(name):
        raise UnknownColumnError(f"Invalid column name: {name!r}")
    return name


def eq(column: str, value: str | bool | int) -> str:
    return f"{_check_column(column)} == {_quote(value)}"


def ne(column: str, value: str | bool | int) -> str:
    return f"{_check_column(column)} != {_quote(value)}"


def in_(column: str, values: Sequence[str | int]) -> str:
    if not values:
        # An empty `in` should refuse rather than silently match nothing.
        raise UnknownColumnError(
            f"Empty value list for {column!r}; refusing to build vacuous filter."
        )
    inner = ", ".join(_quote(v) for v in values)
    return f"{_check_column(column)} in [{inner}]"


def contains(column: str, value: str) -> str:
    """Substring match — used by schema-drift rewrites for delimited columns."""
    return f"{_quote(value)} in {_check_column(column)}"


def and_(*parts: str) -> str:
    parts = tuple(p for p in parts if p)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " and ".join(f"({p})" for p in parts)


def or_(*parts: str) -> str:
    parts = tuple(p for p in parts if p)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " or ".join(f"({p})" for p in parts)


def curie_in(column: str, curies: Sequence[str]) -> str:
    bad = [c for c in curies if not is_curie(c)]
    if bad:
        raise UnknownColumnError(f"Non-CURIE values supplied to {column}: {bad[:5]}")
    return in_(column, list(curies))


CombineMode = Literal["and", "or"]
