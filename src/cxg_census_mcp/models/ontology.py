"""Resolver / expander Pydantic models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["exact", "label_match", "synonym_match", "fuzzy", "hint_fallback"]
RefusalCode = Literal["TERM_NOT_FOUND", "TERM_AMBIGUOUS", "ONTOLOGY_UNAVAILABLE"]
ExpandDirection = Literal["exact", "descendants_inclusive", "ancestors_inclusive"]


class TermCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    curie: str
    label: str
    score: float
    definition: str | None = None
    is_obsolete: bool = False
    cells_in_census: int | None = None


class ResolvedTerm(BaseModel):
    input: str
    curie: str
    label: str
    ontology: str
    confidence: Confidence
    similarity_score: float | None = None
    alternatives: list[TermCandidate] = Field(default_factory=list)
    definition: str | None = None
    requires_confirmation: bool = False
    resolution_path: str
    present_in_census: bool = True
    census_presence_count: int | None = None


class ResolutionRefusal(BaseModel):
    code: RefusalCode
    message: str
    ontology: str | None = None
    candidates: list[TermCandidate] = Field(default_factory=list)
    action_hint: str
    retry_with: dict | None = None


class ExpandedTerm(BaseModel):
    query_curie: str
    query_label: str | None = None
    direction: ExpandDirection
    terms: list[str] = Field(default_factory=list)
    terms_present_in_census: int = 0
    terms_missing_from_census: list[str] = Field(default_factory=list)
    terms_truncated: bool = False
    truncation_reason: str | None = None
    cells_by_term: list[dict] | None = None
    total_cells: int | None = None


class TermDefinition(BaseModel):
    curie: str
    label: str
    ontology: str
    definition: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    is_obsolete: bool = False
    iri: str | None = None
