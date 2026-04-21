"""Resources/prompts channel registration tests."""

from __future__ import annotations

import pytest
from pydantic import AnyUrl

from cxg_census_mcp.errors import CensusMCPError
from cxg_census_mcp.server import (
    _RESOURCE_DOCS,
    _list_prompts,
    _list_resources,
    _read_resource,
)
from cxg_census_mcp.server import (
    _get_prompt as _get_prompt_handler,
)

pytestmark = pytest.mark.asyncio


async def test_list_resources_advertises_all_docs():
    res = await _list_resources()
    uris = {str(r.uri) for r in res}
    for slug in _RESOURCE_DOCS:
        assert f"cxg-census-mcp://docs/{slug}" in uris


async def test_read_resource_returns_markdown_for_each_doc():
    for slug in _RESOURCE_DOCS:
        body = await _read_resource(AnyUrl(f"cxg-census-mcp://docs/{slug}"))
        assert isinstance(body, str)
        assert len(body) > 0


async def test_read_resource_rejects_unknown_uri():
    with pytest.raises(CensusMCPError):
        await _read_resource(AnyUrl("cxg-census-mcp://docs/does-not-exist"))


async def test_list_prompts_includes_workflow_and_disambiguation():
    prompts = await _list_prompts()
    names = {p.name for p in prompts}
    assert "census_workflow" in names
    assert "disambiguation" in names


async def test_get_prompt_returns_message_body():
    res = await _get_prompt_handler("census_workflow", None)
    assert res.messages
    msg = res.messages[0]
    assert msg.role == "user"
    assert msg.content.text
    assert "Census" in msg.content.text


async def test_get_prompt_rejects_unknown_name():
    with pytest.raises(CensusMCPError):
        await _get_prompt_handler("nope", None)
