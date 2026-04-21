"""Counting / discovery response payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GroupCount(BaseModel):
    group: str
    count: int
    label: str | None = Field(
        default=None,
        description="Label for ontology CURIE or dataset_id groups; None e.g. for donor_id.",
    )


class CellCount(BaseModel):
    total: int
    group_by: str | None = None
    by_group: list[GroupCount] = Field(default_factory=list)
    n_groups: int = 0


class DatasetSummary(BaseModel):
    dataset_id: str
    collection_id: str | None = None
    collection_name: str | None = None
    collection_doi: str | None = None
    citation: str | None = None
    title: str | None = None
    n_cells: int | None = None
    n_cells_total: int | None = Field(
        default=None,
        description="Cells in whole dataset; n_cells is after the active filter.",
    )
    n_donors: int | None = None
    organism: str | None = None
    primary_disease: str | None = None


class GeneCoverage(BaseModel):
    gene_id: str
    gene_symbol: str | None = None
    organism: str
    n_cells_with_gene: int | None = None
    n_datasets_with_gene: int | None = None
    present_in_var: bool


class FacetValue(BaseModel):
    value: str
    count: int | None = None
