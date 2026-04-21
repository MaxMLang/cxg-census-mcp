"""Static MCP resources (markdown docs the LLM can read for context)."""

from importlib import resources as _resources


def read_resource(name: str) -> str:
    return _resources.files("cxg_census_mcp.resources").joinpath(name).read_text()
