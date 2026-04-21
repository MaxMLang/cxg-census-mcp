"""Discovery tools: census_summary, get_census_versions, list_available_values."""

from __future__ import annotations

from typing import Any

from cxg_census_mcp.caches.facet_cache import get_facet_cache
from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import CensusUnavailableError, UnknownColumnError
from cxg_census_mcp.models.counts import FacetValue
from cxg_census_mcp.models.provenance import QueryProvenance, ResponseEnvelope
from cxg_census_mcp.tools._envelope import TimedScope, build_envelope
from cxg_census_mcp.utils.stable_hash import stable_hash


async def census_summary() -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    client = get_census_client()
    summary = client.summary(s.census_version)
    schema_version = summary.get("schema_version", "unknown")
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version=str(schema_version),
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash("census_summary", s.census_version, length=20)
    return build_envelope(
        data=summary,
        provenance=provenance,
        call_id=call_id,
        timer=timer,
        defaults_applied={"is_primary_data": False},
    )


async def get_census_versions() -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    client = get_census_client()
    summary = client.summary(s.census_version)
    versions: list[dict[str, Any]] = [
        {
            "version": s.census_version,
            "schema_version": summary.get("schema_version"),
            "build_date": summary.get("build_date"),
            "is_default": True,
        }
    ]
    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version=str(summary.get("schema_version") or "unknown"),
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash("get_census_versions", s.census_version, length=20)
    return build_envelope(
        data={"versions": versions},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
    )


async def list_available_values(
    column: str,
    *,
    organism: str = "homo_sapiens",
    prefix: str | None = None,
    limit: int = 50,
) -> ResponseEnvelope:
    timer = TimedScope()
    s = get_settings()
    client = get_census_client()

    fc = get_facet_cache()
    cached = fc.get(s.census_version, organism, column)

    if cached is None:
        try:
            tbl = client.summary_cell_counts(s.census_version, organism)
        except CensusUnavailableError as exc:
            raise UnknownColumnError(f"Unable to read facet column: {exc}") from exc
        if column not in tbl.column_names:
            raise UnknownColumnError(f"Column {column!r} not present in summary_cell_counts.")
        seen: dict[str, int] = {}
        for r in tbl.to_pylist():
            v = r.get(column)
            if v is None:
                continue
            seen[str(v)] = seen.get(str(v), 0) + int(r.get("n_cells") or 0)
        cached = sorted(seen.items(), key=lambda kv: -kv[1])
        fc.set(s.census_version, organism, column, cached)
    else:
        if cached and isinstance(cached[0], str):
            cached = [(v, None) for v in cached]

    if prefix:
        cached = [(v, c) for v, c in cached if str(v).lower().startswith(prefix.lower())]
    cached = list(cached)[:limit]

    payload = [FacetValue(value=v, count=c).model_dump() for v, c in cached]

    provenance = QueryProvenance(
        census_version=s.census_version,
        schema_version="unknown",
        value_filter="",
        execution_tier=0,
        is_primary_data_applied=False,
    )
    call_id = stable_hash(
        "list_available_values", s.census_version, organism, column, prefix, limit, length=20
    )
    return build_envelope(
        data={"column": column, "organism": organism, "values": payload},
        provenance=provenance,
        call_id=call_id,
        timer=timer,
    )
