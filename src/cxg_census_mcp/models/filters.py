"""Tool filter models (FilterSpec, TermFilter, MultiTermFilter)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExpandDirection = Literal["exact", "descendants_inclusive", "ancestors_inclusive"]


class TermFilter(BaseModel):
    """One of ``term`` (CURIE) or ``text`` (label)."""

    model_config = ConfigDict(extra="forbid")

    term: str | None = Field(default=None, description="Exact CURIE, e.g. 'CL:0000236'.")
    text: str | None = Field(default=None, description="Free-text label to resolve.")
    expand: ExpandDirection = "exact"
    confirm_ambiguous: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> TermFilter:
        if (self.term is None) == (self.text is None):
            raise ValueError("Provide exactly one of {'term', 'text'}.")
        return self


class MultiTermFilter(BaseModel):
    """OR of CURIEs/strings in ``any_of``."""

    model_config = ConfigDict(extra="forbid")

    any_of: list[str] = Field(min_length=1)
    expand: ExpandDirection = "exact"
    confirm_ambiguous: bool = False


Sex = Literal["male", "female", "unknown"]
SuspensionType = Literal["cell", "nucleus", "na"]
Organism = Literal["homo_sapiens", "mus_musculus"]


class FilterSpec(BaseModel):
    """Structured filters for count/preview/expression tools."""

    model_config = ConfigDict(extra="forbid")

    organism: Organism = "homo_sapiens"

    cell_type: TermFilter | MultiTermFilter | None = None
    tissue: TermFilter | MultiTermFilter | None = None
    disease: TermFilter | MultiTermFilter | None = None
    assay: TermFilter | MultiTermFilter | None = None
    development_stage: TermFilter | None = None
    self_reported_ethnicity: TermFilter | MultiTermFilter | None = None

    sex: Sex | None = None
    suspension_type: SuspensionType | None = None
    is_primary_data: bool = True
    dataset_id: str | list[str] | None = None
    donor_id: str | list[str] | None = None

    preview_only: bool = False

    def is_empty(self) -> bool:
        for k, v in self.model_dump(exclude_defaults=True).items():
            if k in {"organism", "is_primary_data", "preview_only"}:
                continue
            if v not in (None, [], "", False):
                return False
        return True
