"""Validators for non-CURIE identifiers used by Census."""

from __future__ import annotations

import re
from collections.abc import Iterable

from cxg_census_mcp.errors import InvalidFilterError

ENSEMBL_HUMAN = re.compile(r"^ENSG\d{11}(\.\d+)?$")
ENSEMBL_MOUSE = re.compile(r"^ENSMUSG\d{11}(\.\d+)?$")
DATASET_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_ensembl_gene(value: str, organism: str = "homo_sapiens") -> bool:
    pat = ENSEMBL_HUMAN if organism == "homo_sapiens" else ENSEMBL_MOUSE
    return bool(pat.match(value or ""))


def validate_gene_ids(values: Iterable[str], organism: str) -> list[str]:
    out: list[str] = []
    bad: list[str] = []
    for v in values:
        if is_ensembl_gene(v, organism):
            out.append(v)
        else:
            bad.append(v)
    if bad:
        raise InvalidFilterError(
            f"Not valid Ensembl IDs for {organism}: {bad[:5]}"
            + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""),
            action_hint="Pass Ensembl gene IDs (ENSG... for human, ENSMUSG... for mouse).",
        )
    return out


def is_dataset_id(value: str) -> bool:
    return bool(DATASET_ID.match(value or ""))
