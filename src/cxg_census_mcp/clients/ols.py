"""OLS4 HTTP client (search, term, DAG); responses disk-cached."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel

from cxg_census_mcp.caches.ols_cache import get_ols_cache
from cxg_census_mcp.clients.http import get_http_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import OntologyUnavailableError
from cxg_census_mcp.logging_setup import get_logger
from cxg_census_mcp.utils.curie import normalize_curie, parse_curie

log = get_logger(__name__)


class OLSHit(BaseModel):
    curie: str
    label: str
    ontology: str
    is_obsolete: bool = False
    iri: str | None = None
    score: float | None = None
    synonyms: list[str] = []


class OLSTerm(BaseModel):
    curie: str
    label: str
    ontology: str
    definition: str | None = None
    synonyms: list[str] = []
    is_obsolete: bool = False
    iri: str | None = None


@dataclass
class OLSClient:
    base: str

    async def search(
        self,
        query: str,
        *,
        ontology: str | None = None,
        exact: bool = False,
        limit: int = 10,
    ) -> list[OLSHit]:
        cache = get_ols_cache()
        args = {"q": query, "ontology": ontology, "exact": exact, "limit": limit}
        cached = cache.get(ontology, "search", args)
        if cached is not None:
            return [OLSHit(**h) for h in cached]
        if cache.is_negative(ontology, "search", args):
            return []

        params: dict[str, Any] = {
            "q": query,
            "rows": limit,
            "exact": "true" if exact else "false",
        }
        if ontology:
            params["ontology"] = ontology.lower()

        try:
            payload = await get_http_client().get_json(f"{self.base}/search", params=params)
        except OntologyUnavailableError:
            raise

        docs = (payload.get("response") or {}).get("docs") or []
        hits = [_doc_to_hit(d) for d in docs if d.get("obo_id")]
        cache.set(ontology, "search", args, [h.model_dump() for h in hits])
        if not hits:
            cache.set_negative(ontology, "search", args)
        return hits

    async def get_term(self, curie: str) -> OLSTerm | None:
        curie = normalize_curie(curie)
        prefix, _ = parse_curie(curie)
        cache = get_ols_cache()
        args = {"curie": curie}
        cached = cache.get(prefix, "get_term", args)
        if cached is not None:
            return OLSTerm(**cached)
        if cache.is_negative(prefix, "get_term", args):
            return None

        # OLS4 search by exact obo_id is the most robust lookup path.
        params = {"q": curie, "exact": "true", "rows": 1, "ontology": prefix.lower()}
        payload = await get_http_client().get_json(f"{self.base}/search", params=params)
        docs = (payload.get("response") or {}).get("docs") or []
        if not docs:
            cache.set_negative(prefix, "get_term", args)
            return None
        d = docs[0]
        term = OLSTerm(
            curie=curie,
            label=d.get("label") or curie,
            ontology=prefix,
            definition=_first(d.get("description")),
            synonyms=list(d.get("synonym") or []),
            is_obsolete=bool(d.get("is_obsolete", False)),
            iri=d.get("iri"),
        )
        cache.set(prefix, "get_term", args, term.model_dump())
        return term

    async def get_descendants(self, curie: str, *, ontology: str | None = None) -> list[str]:
        return await self._dag(curie, ontology, "hierarchicalDescendants")

    async def get_ancestors(self, curie: str, *, ontology: str | None = None) -> list[str]:
        return await self._dag(curie, ontology, "hierarchicalAncestors")

    async def _dag(self, curie: str, ontology: str | None, kind: str) -> list[str]:
        curie = normalize_curie(curie)
        prefix, _ = parse_curie(curie)
        ont = (ontology or prefix).lower()
        cache = get_ols_cache()
        args = {"curie": curie, "kind": kind, "ontology": ont}
        cached = cache.get(prefix, "dag", args)
        if cached is not None:
            return list(cached)

        # Two-step: resolve IRI from CURIE, then fetch DAG endpoint paginated.
        term = await self.get_term(curie)
        if term is None or not term.iri:
            cache.set_negative(prefix, "dag", args)
            return []
        iri_enc = quote(quote(term.iri, safe=""), safe="")
        url = f"{self.base}/ontologies/{ont}/terms/{iri_enc}/{kind}"

        out: list[str] = []
        params: dict[str, int] | None = {"size": 200}
        next_url: str | None = url
        while next_url:
            try:
                payload = await get_http_client().get_json(next_url, params=params)
            except OntologyUnavailableError:
                break
            for t in (payload.get("_embedded") or {}).get("terms", []) or []:
                obo_id = t.get("obo_id") or t.get("short_form")
                if obo_id and ":" in obo_id:
                    out.append(obo_id)
            next_link = (payload.get("_links") or {}).get("next")
            next_url = next_link.get("href") if next_link else None
            params = None  # subsequent links carry their own query

        cache.set(prefix, "dag", args, out)
        return out

    async def get_synonyms(self, curie: str) -> list[str]:
        term = await self.get_term(curie)
        return list(term.synonyms) if term else []


def _doc_to_hit(d: dict[str, Any]) -> OLSHit:
    return OLSHit(
        curie=d["obo_id"],
        label=d.get("label") or d["obo_id"],
        ontology=(d.get("ontology_prefix") or d.get("ontology_name", "")).upper(),
        is_obsolete=bool(d.get("is_obsolete", False)),
        iri=d.get("iri"),
        score=d.get("score"),
        synonyms=list(d.get("synonym") or []),
    )


def _first(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, list):
        return v[0] if v else None
    return str(v)


@lru_cache(maxsize=1)
def get_ols_client() -> OLSClient:
    return OLSClient(base=get_settings().ols_base.rstrip("/"))
