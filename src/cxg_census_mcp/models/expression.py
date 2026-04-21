"""Aggregate expression response payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExpressionRow(BaseModel):
    group: str
    group_label: str | None = Field(
        default=None,
        description="Label for group if CURIE/dataset_id; else None (e.g. donor_id).",
    )
    gene_id: str
    gene_symbol: str | None = None
    n_cells: int
    mean: float | None = None
    std: float | None = None
    fraction_expressing: float | None = None
    median: float | None = None
    sum: float | None = None


class ExpressionAggregate(BaseModel):
    group_by: str
    gene_ids: list[str]
    aggregations: list[str]
    rows: list[ExpressionRow] = Field(default_factory=list)
    n_cells_total: int
    n_groups: int
