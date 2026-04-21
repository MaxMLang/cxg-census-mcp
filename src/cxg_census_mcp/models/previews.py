"""``preview_obs`` response shape."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ObsPreview(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    n_rows: int
    cardinality_hints: dict[str, int] = Field(default_factory=dict)
    note: str | None = None
