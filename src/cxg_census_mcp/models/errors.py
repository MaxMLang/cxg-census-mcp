"""Wire-format error envelope returned to MCP clients."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MCPToolError(BaseModel):
    code: str
    message: str
    action_hint: str
    retry_with: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] | None = None
    call_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
