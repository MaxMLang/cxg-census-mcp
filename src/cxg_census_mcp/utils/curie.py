"""CURIE parsing and validation."""

from __future__ import annotations

import re

from cxg_census_mcp.errors import InvalidCurieError

CURIE_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]*):([0-9]+)$")


def is_curie(value: str) -> bool:
    return bool(CURIE_PATTERN.match(value or ""))


def parse_curie(value: str) -> tuple[str, str]:
    """Return ``(prefix, local_id)``. Raises ``InvalidCurieError`` on bad input."""
    m = CURIE_PATTERN.match(value or "")
    if not m:
        raise InvalidCurieError(f"Not a valid CURIE: {value!r}")
    return m.group(1), m.group(2)


def prefix_of(value: str) -> str:
    return parse_curie(value)[0]


def normalize_curie(value: str) -> str:
    """Uppercase the prefix; leave the local id alone. Raises on invalid."""
    prefix, local = parse_curie(value.strip())
    return f"{prefix.upper()}:{local}"
