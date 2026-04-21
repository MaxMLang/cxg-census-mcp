"""MCP prompt templates exposed to clients."""

from cxg_census_mcp.prompts.census_workflow import CENSUS_WORKFLOW_PROMPT
from cxg_census_mcp.prompts.disambiguation_workflow import DISAMBIGUATION_PROMPT

__all__ = ["CENSUS_WORKFLOW_PROMPT", "DISAMBIGUATION_PROMPT"]
