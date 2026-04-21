"""Tier-2 aggregation: the per-group denominator must not be summed across chunks."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cxg_census_mcp.execution.tier2_expression import run_tier2_expression
from cxg_census_mcp.models.expression import ExpressionAggregate


class _MultiChunkClient:
    """Stub: 3 chunks, same per-group n_cells (like live sparse X tiling)."""

    def __init__(self) -> None:
        self.is_mock = False

    def read_var(self, **_: object):
        import pyarrow as pa

        return pa.Table.from_pylist(
            [
                {"feature_id": "ENSG00000100453", "feature_name": "GZMB"},
                {"feature_id": "ENSG00000180644", "feature_name": "PRF1"},
            ]
        )

    def aggregate_expression_chunks(
        self, **_: object
    ) -> Iterator[tuple[dict[tuple[str, str], dict[str, float]], int]]:
        for _ in range(3):
            yield (
                {
                    ("ds-A", "ENSG00000100453"): {
                        "sum": 10.0,
                        "sum_sq": 100.0,
                        "n_nonzero": 5,
                        "n_cells": 100.0,
                    },
                    ("ds-A", "ENSG00000180644"): {
                        "sum": 6.0,
                        "sum_sq": 36.0,
                        "n_nonzero": 3,
                        "n_cells": 100.0,
                    },
                },
                40,
            )


@pytest.mark.asyncio
async def test_n_cells_denominator_taken_max_not_sum() -> None:
    result: ExpressionAggregate = await run_tier2_expression(
        organism="homo_sapiens",
        census_version="stable",
        value_filter="dataset_id == 'ds-A'",
        gene_ids=["ENSG00000100453", "ENSG00000180644"],
        group_by="dataset_id",
        aggregations=["mean", "fraction_expressing"],
        client=_MultiChunkClient(),  # type: ignore[arg-type]
    )

    assert result.n_groups == 1
    rows = {r.gene_id: r for r in result.rows}
    assert rows["ENSG00000100453"].n_cells == 100
    assert rows["ENSG00000180644"].n_cells == 100
    assert rows["ENSG00000100453"].mean == pytest.approx(30.0 / 100, rel=1e-6)
    assert rows["ENSG00000100453"].fraction_expressing == pytest.approx(15 / 100, rel=1e-6)
