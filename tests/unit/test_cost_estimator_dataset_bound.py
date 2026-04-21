"""Cost estimator: dataset_id-aware upper bound."""

from __future__ import annotations

import pyarrow as pa
import pytest

from cxg_census_mcp.planner import cost_estimator
from cxg_census_mcp.planner.cost_estimator import estimate_cost


class _StubClient:

    def __init__(
        self,
        summary_rows: list[dict],
        dataset_meta: dict[str, dict],
    ) -> None:
        self._rows = summary_rows
        self._meta = dataset_meta
        self.dataset_metadata_calls: list[list[str] | None] = []

    def summary_cell_counts(self, version: str, organism: str) -> pa.Table:
        return pa.Table.from_pylist(self._rows)

    def dataset_metadata(
        self, *, version: str | None, dataset_ids: list[str] | None = None
    ) -> dict[str, dict]:
        self.dataset_metadata_calls.append(dataset_ids)
        if dataset_ids is None:
            return self._meta
        return {ds: self._meta[ds] for ds in dataset_ids if ds in self._meta}


def _long_row(category: str, label: str, n: int, organism: str = "homo_sapiens") -> dict:
    """A row in the live ``summary_cell_counts`` long-format shape."""
    return {
        "organism": organism,
        "category": category,
        "label": label,
        "ontology_term_id": "" if category in {"all", "is_primary_data"} else label,
        "unique_cell_count": n,
        "total_cell_count": n,
    }


def test_dataset_id_filter_tightens_estimate_below_facet_total() -> None:
    rows = [
        _long_row("all", "", 1_000_000_000),
        _long_row("cell_type", "CL:0000625", 5_000_000),
    ]
    meta = {
        "ds-A": {"dataset_id": "ds-A", "n_cells_total": 110_000},
        "ds-B": {"dataset_id": "ds-B", "n_cells_total": 35_000},
        "ds-C": {"dataset_id": "ds-C", "n_cells_total": 28_000},
    }
    client = _StubClient(rows, meta)

    est = estimate_cost(
        organism="homo_sapiens",
        census_version="stable",
        resolved_filters={
            "cell_type": ["CL:0000625"],
            "dataset_id": ["ds-A", "ds-B", "ds-C"],
        },
        client=client,  # type: ignore[arg-type]
    )

    assert est.estimated_cells == 173_000
    assert client.dataset_metadata_calls == [["ds-A", "ds-B", "ds-C"]]


def test_dataset_id_only_uses_dataset_bound() -> None:
    rows = [_long_row("all", "", 1_000_000_000)]
    meta = {"ds-A": {"dataset_id": "ds-A", "n_cells_total": 50_000}}
    client = _StubClient(rows, meta)

    est = estimate_cost(
        organism="homo_sapiens",
        census_version="stable",
        resolved_filters={"dataset_id": ["ds-A"]},
        client=client,  # type: ignore[arg-type]
    )

    assert est.estimated_cells == 50_000


def test_no_dataset_id_keeps_facet_only_estimate() -> None:
    rows = [
        _long_row("all", "", 1_000_000_000),
        _long_row("cell_type", "CL:0000625", 5_000_000),
    ]
    client = _StubClient(rows, {})
    est = estimate_cost(
        organism="homo_sapiens",
        census_version="stable",
        resolved_filters={"cell_type": ["CL:0000625"]},
        client=client,  # type: ignore[arg-type]
    )
    assert est.estimated_cells == 5_000_000
    assert client.dataset_metadata_calls == []


def test_dataset_meta_failure_falls_back_to_facet_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        _long_row("all", "", 1_000_000_000),
        _long_row("cell_type", "CL:0000625", 5_000_000),
    ]

    class _BrokenClient(_StubClient):
        def dataset_metadata(self, **_: object) -> dict[str, dict]:
            raise RuntimeError("metadata table unreachable")

    client = _BrokenClient(rows, {})
    est = estimate_cost(
        organism="homo_sapiens",
        census_version="stable",
        resolved_filters={
            "cell_type": ["CL:0000625"],
            "dataset_id": ["ds-A"],
        },
        client=client,  # type: ignore[arg-type]
    )
    assert est.estimated_cells == 5_000_000


def test_get_census_client_used_when_none_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    class _Sentinel:
        def summary_cell_counts(self, *_: object, **__: object) -> pa.Table:
            seen.append("summary")
            return pa.Table.from_pylist([_long_row("all", "", 7)])

        def dataset_metadata(self, *_: object, **__: object) -> dict[str, dict]:
            seen.append("meta")
            return {}

    monkeypatch.setattr(cost_estimator, "get_census_client", lambda: _Sentinel())
    est = estimate_cost(
        organism="homo_sapiens",
        census_version="stable",
        resolved_filters={},
    )
    assert est.estimated_cells == 7
    assert seen == ["summary"]
