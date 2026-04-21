"""stdio MCP server: tools, progress, cancel, resources, prompts."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl, ValidationError

from cxg_census_mcp import __version__
from cxg_census_mcp.cancellation import CancellationToken
from cxg_census_mcp.errors import CancelledError, CensusMCPError
from cxg_census_mcp.logging_setup import get_logger
from cxg_census_mcp.metrics import (
    inc_cancellation,
    inc_tool_call,
    inc_tool_error,
)
from cxg_census_mcp.models.errors import MCPToolError
from cxg_census_mcp.progress import ProgressReporter
from cxg_census_mcp.prompts import CENSUS_WORKFLOW_PROMPT, DISAMBIGUATION_PROMPT
from cxg_census_mcp.resources import read_resource
from cxg_census_mcp.tools import (
    aggregate_expression,
    census_summary,
    count_cells,
    expand_term,
    export_snippet,
    gene_coverage,
    get_census_versions,
    get_server_limits,
    list_available_values,
    list_datasets,
    preview_obs_tool,
    resolve_term,
    term_definition,
)

log = get_logger(__name__)


# --- schema helpers ----------------------------------------------------------


def _term_filter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "term": {"type": ["string", "null"], "description": "Exact CURIE."},
            "text": {"type": ["string", "null"], "description": "Free text to resolve."},
            "expand": {
                "type": "string",
                "enum": ["exact", "descendants_inclusive", "ancestors_inclusive"],
                "default": "exact",
            },
            "confirm_ambiguous": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }


def _multi_term_filter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "any_of": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "expand": {
                "type": "string",
                "enum": ["exact", "descendants_inclusive", "ancestors_inclusive"],
                "default": "exact",
            },
            "confirm_ambiguous": {"type": "boolean", "default": False},
        },
        "required": ["any_of"],
        "additionalProperties": False,
    }


def _filter_spec_schema() -> dict[str, Any]:
    one_of_term = {"oneOf": [_term_filter_schema(), _multi_term_filter_schema(), {"type": "null"}]}
    return {
        "type": "object",
        "properties": {
            "organism": {
                "type": "string",
                "enum": ["homo_sapiens", "mus_musculus"],
                "default": "homo_sapiens",
            },
            "cell_type": one_of_term,
            "tissue": one_of_term,
            "disease": one_of_term,
            "assay": one_of_term,
            "development_stage": {
                "oneOf": [_term_filter_schema(), {"type": "null"}],
            },
            "self_reported_ethnicity": one_of_term,
            "sex": {"type": ["string", "null"], "enum": ["male", "female", "unknown", None]},
            "suspension_type": {
                "type": ["string", "null"],
                "enum": ["cell", "nucleus", "na", None],
            },
            "is_primary_data": {"type": "boolean", "default": True},
            "dataset_id": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ]
            },
            "donor_id": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ]
            },
            "preview_only": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }


def _count_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filters": _filter_spec_schema(),
            "group_by": {"type": ["string", "null"], "default": None},
        },
        "required": ["filters"],
        "additionalProperties": False,
    }


def _list_datasets_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filters": _filter_spec_schema(),
            "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000},
        },
        "required": ["filters"],
        "additionalProperties": False,
    }


def _preview_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filters": _filter_spec_schema(),
            "columns": {"type": ["array", "null"], "items": {"type": "string"}},
            "limit": {"type": ["integer", "null"]},
        },
        "required": ["filters"],
        "additionalProperties": False,
    }


def _aggregate_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filters": _filter_spec_schema(),
            "gene_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "group_by": {"type": "string", "default": "cell_type"},
            "aggregations": {
                "type": ["array", "null"],
                "items": {
                    "type": "string",
                    "enum": ["mean", "std", "median", "sum", "fraction_expressing"],
                },
                "default": None,
            },
        },
        "required": ["filters", "gene_ids"],
        "additionalProperties": False,
    }


# --- tool registry -----------------------------------------------------------

server: Server = Server("cxg-census-mcp", version=__version__)

TOOL_DESCRIPTORS: list[types.Tool] = [
    types.Tool(
        name="census_summary",
        description="Pinned Census summary: cells, schema, build date.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="get_census_versions",
        description="List available Census versions visible to this server.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="list_available_values",
        description="Distinct values for an obs column (discovery before resolve_term).",
        inputSchema={
            "type": "object",
            "properties": {
                "column": {"type": "string"},
                "organism": {"type": "string", "default": "homo_sapiens"},
                "prefix": {"type": ["string", "null"], "default": None},
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
            },
            "required": ["column"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="resolve_term",
        description="Resolve text or CURIE to one term; typed refusal if ambiguous.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "ontology": {"type": ["string", "null"], "default": None},
                "facet": {"type": ["string", "null"], "default": None},
                "confirm_ambiguous": {"type": "boolean", "default": False},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="expand_term",
        description="Expand a CURIE to descendants/ancestors filtered to Census presence.",
        inputSchema={
            "type": "object",
            "properties": {
                "curie": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["exact", "descendants_inclusive", "ancestors_inclusive"],
                    "default": "descendants_inclusive",
                },
                "in_census_only": {"type": "boolean", "default": True},
                "include_counts": {"type": "boolean", "default": False},
                "facet": {"type": ["string", "null"], "default": None},
            },
            "required": ["curie"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="term_definition",
        description="Return label, definition, synonyms, IRI for a CURIE.",
        inputSchema={
            "type": "object",
            "properties": {"curie": {"type": "string"}},
            "required": ["curie"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="count_cells",
        description="Count cells (filters + optional group_by); tier 0.",
        inputSchema=_count_schema(),
    ),
    types.Tool(
        name="list_datasets",
        description="List datasets matching a structured filter, sorted by cell count.",
        inputSchema=_list_datasets_schema(),
    ),
    types.Tool(
        name="gene_coverage",
        description="Report whether a list of Ensembl gene IDs is present in Census var.",
        inputSchema={
            "type": "object",
            "properties": {
                "gene_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "organism": {"type": "string", "default": "homo_sapiens"},
            },
            "required": ["gene_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="preview_obs",
        description="Small obs slice + column cardinality (before a big scan).",
        inputSchema=_preview_schema(),
    ),
    types.Tool(
        name="aggregate_expression",
        description="Per-gene expression stats by group; caps → export_snippet if over.",
        inputSchema=_aggregate_schema(),
    ),
    types.Tool(
        name="export_snippet",
        description="Runnable Python for a stored plan; pass call_id from a prior response.",
        inputSchema={
            "type": "object",
            "properties": {
                "call_id": {"type": "string"},
                "intent": {
                    "type": "string",
                    "enum": ["anndata", "obs_only", "aggregate"],
                    "default": "anndata",
                },
            },
            "required": ["call_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="get_server_limits",
        description="Report cap configuration so clients can size their requests.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
]


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return TOOL_DESCRIPTORS


# --- resources channel -------------------------------------------------------

_RESOURCE_DOCS: dict[str, tuple[str, str]] = {
    # uri-suffix -> (filename, human_title)
    "schema": ("docs_schema.md", "Census schema overview"),
    "ontology": ("docs_ontology.md", "Ontology resolution rules"),
    "limitations": ("docs_limitations.md", "Server limitations and non-goals"),
    "workflow": ("docs_workflow.md", "Recommended agent workflow"),
    "errors": ("docs_errors.md", "Structured error model"),
    "progress": ("docs_progress.md", "Progress and cancellation"),
}


@server.list_resources()
async def _list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=AnyUrl(f"cxg-census-mcp://docs/{slug}"),
            name=title,
            description=title,
            mimeType="text/markdown",
        )
        for slug, (_, title) in _RESOURCE_DOCS.items()
    ]


@server.read_resource()
async def _read_resource(uri: AnyUrl) -> str:
    s = str(uri)
    if not s.startswith("cxg-census-mcp://docs/"):
        raise CensusMCPError(f"Unknown resource URI: {s}")
    slug = s.removeprefix("cxg-census-mcp://docs/").rstrip("/")
    entry = _RESOURCE_DOCS.get(slug)
    if entry is None:
        raise CensusMCPError(f"Unknown resource: {slug}")
    filename, _title = entry
    return read_resource(filename)


# --- prompts channel ---------------------------------------------------------

_PROMPTS: dict[str, tuple[str, str]] = {
    "census_workflow": (
        "Default workflow guidance for Census exploration.",
        CENSUS_WORKFLOW_PROMPT,
    ),
    "disambiguation": (
        "How to handle TERM_AMBIGUOUS responses.",
        DISAMBIGUATION_PROMPT,
    ),
}


@server.list_prompts()
async def _list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(name=name, description=desc, arguments=[])
        for name, (desc, _body) in _PROMPTS.items()
    ]


@server.get_prompt()
async def _get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    entry = _PROMPTS.get(name)
    if entry is None:
        raise CensusMCPError(f"Unknown prompt: {name}")
    desc, body = entry
    return types.GetPromptResult(
        description=desc,
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=body),
            )
        ],
    )


# --- dispatcher --------------------------------------------------------------


@server.call_tool()
async def _dispatch(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    args = arguments or {}
    inc_tool_call(name)

    progress_cb = _make_progress_callback()
    cancel = CancellationToken()
    progress = ProgressReporter(cb=progress_cb)

    try:
        envelope = await _route(name, args, progress=progress, cancel=cancel)
    except asyncio.CancelledError:
        cancel.cancel("client cancelled")
        inc_cancellation()
        inc_tool_error(name, "CANCELLED")
        err = MCPToolError(
            code="CANCELLED",
            message="Request cancelled by client.",
            action_hint="Re-issue the request when ready.",
        )
        return [types.TextContent(type="text", text=json.dumps({"error": err.model_dump()}))]
    except CancelledError as exc:
        inc_cancellation()
        inc_tool_error(name, "CANCELLED")
        err = MCPToolError(
            code="CANCELLED",
            message=str(exc) or "cancelled",
            action_hint="Re-issue the request when ready.",
        )
        return [types.TextContent(type="text", text=json.dumps({"error": err.model_dump()}))]
    except CensusMCPError as exc:
        inc_tool_error(name, exc.code)
        err = MCPToolError(**exc.to_dict())
        return [types.TextContent(type="text", text=json.dumps({"error": err.model_dump()}))]
    except ValidationError as exc:
        inc_tool_error(name, "INVALID_FILTER")
        err = MCPToolError(
            code="INVALID_FILTER",
            message=str(exc),
            action_hint="Fix the offending field per `message` and retry.",
        )
        return [types.TextContent(type="text", text=json.dumps({"error": err.model_dump()}))]
    except Exception as exc:
        log.exception("tool_unexpected_error", tool=name)
        inc_tool_error(name, "INTERNAL_ERROR")
        err = MCPToolError(
            code="INTERNAL_ERROR",
            message=str(exc),
            action_hint="Retry the request later.",
        )
        return [types.TextContent(type="text", text=json.dumps({"error": err.model_dump()}))]

    payload = envelope.model_dump(mode="json")
    return [types.TextContent(type="text", text=json.dumps(payload))]


def _make_progress_callback():
    """Return a progress cb for the active MCP request, or None (tests / no token)."""
    try:
        ctx = server.request_context
    except LookupError:
        return None
    meta = getattr(ctx, "meta", None)
    token = getattr(meta, "progressToken", None) if meta is not None else None
    if token is None:
        return None
    session = ctx.session

    async def _cb(fraction: float, message: str | None) -> None:
        try:
            await session.send_progress_notification(
                progress_token=token,
                progress=float(fraction),
                total=1.0,
                message=message,
            )
        except Exception as exc:
            log.warning("progress_notification_failed", error=str(exc))

    return _cb


async def _route(
    name: str,
    args: dict[str, Any],
    *,
    progress: ProgressReporter | None = None,
    cancel: CancellationToken | None = None,
):
    if name == "census_summary":
        return await census_summary()
    if name == "get_census_versions":
        return await get_census_versions()
    if name == "list_available_values":
        return await list_available_values(**args)
    if name == "resolve_term":
        return await resolve_term(**args)
    if name == "expand_term":
        return await expand_term(**args)
    if name == "term_definition":
        return await term_definition(**args)
    if name == "count_cells":
        return await count_cells(
            filters=args.get("filters", {}),
            group_by=args.get("group_by"),
            progress=progress,
            cancel=cancel,
        )
    if name == "list_datasets":
        return await list_datasets(filters=args.get("filters", {}), limit=args.get("limit", 100))
    if name == "gene_coverage":
        return await gene_coverage(args["gene_ids"], organism=args.get("organism", "homo_sapiens"))
    if name == "preview_obs":
        return await preview_obs_tool(
            filters=args.get("filters", {}),
            columns=args.get("columns"),
            limit=args.get("limit"),
            progress=progress,
            cancel=cancel,
        )
    if name == "aggregate_expression":
        return await aggregate_expression(
            filters=args.get("filters", {}),
            gene_ids=args.get("gene_ids", []),
            group_by=args.get("group_by", "cell_type"),
            aggregations=args.get("aggregations"),
            progress=progress,
            cancel=cancel,
        )
    if name == "export_snippet":
        return await export_snippet(args["call_id"], intent=args.get("intent", "anndata"))
    if name == "get_server_limits":
        return await get_server_limits()
    raise CensusMCPError(f"Unknown tool: {name}", action_hint="Check tool name spelling.")


def tool_accepts_progress(tool_name: str) -> bool:
    """Introspection helper used by the contract tests."""
    fns: dict[str, Any] = {
        "count_cells": count_cells,
        "list_datasets": list_datasets,
        "preview_obs": preview_obs_tool,
        "aggregate_expression": aggregate_expression,
    }
    fn = fns.get(tool_name)
    if fn is None:
        return False
    sig = inspect.signature(fn)
    return "progress" in sig.parameters and "cancel" in sig.parameters


async def run_stdio() -> None:
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options(),
        )
