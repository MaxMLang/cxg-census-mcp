"""Cardinality estimator: short-circuit when group key is pinned."""

from __future__ import annotations

import pyarrow as pa

from cxg_census_mcp.planner.cardinality_estimator import estimate_group_count


class _Client:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls = 0

    def summary_cell_counts(self, version: str, organism: str) -> pa.Table:
        self.calls += 1
        return pa.Table.from_pylist(self._rows)


def test_pinned_group_returns_exact_count_without_table_read() -> None:
    client = _Client([])
    n = estimate_group_count(
        organism="homo_sapiens",
        census_version="stable",
        group_by="dataset_id",
        resolved_filters={"dataset_id": ["a", "b", "c"]},
        client=client,  # type: ignore[arg-type]
    )
    assert n == 3
    assert client.calls == 0


def test_pinned_group_dedupes_repeated_ids() -> None:
    client = _Client([])
    n = estimate_group_count(
        organism="homo_sapiens",
        census_version="stable",
        group_by="dataset_id",
        resolved_filters={"dataset_id": ["a", "b", "a"]},
        client=client,  # type: ignore[arg-type]
    )
    assert n == 2


def test_unpinned_group_falls_back_to_summary_table() -> None:
    rows = [
        {
            "organism": "homo_sapiens",
            "category": "cell_type",
            "label": "B cell",
            "ontology_term_id": "CL:0000236",
            "unique_cell_count": 100,
            "total_cell_count": 100,
        },
        {
            "organism": "homo_sapiens",
            "category": "cell_type",
            "label": "T cell",
            "ontology_term_id": "CL:0000084",
            "unique_cell_count": 50,
            "total_cell_count": 50,
        },
    ]
    client = _Client(rows)
    n = estimate_group_count(
        organism="homo_sapiens",
        census_version="stable",
        group_by="cell_type_ontology_term_id",
        resolved_filters={},
        client=client,  # type: ignore[arg-type]
    )
    assert n == 2
    assert client.calls == 1
