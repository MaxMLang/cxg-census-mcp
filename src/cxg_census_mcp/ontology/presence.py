"""Which ontology values exist in Census (facet_catalog + summary fallbacks)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from cxg_census_mcp.caches.facet_cache import get_facet_cache


def _load_catalog() -> dict[str, Any]:
    raw = resources.files("cxg_census_mcp.data").joinpath("facet_catalog.json").read_text()
    return json.loads(raw)


@dataclass
class PresenceIndex:
    catalog: dict[str, Any] = field(default_factory=_load_catalog)

    def known_terms(
        self,
        *,
        column: str,
        census_version: str = "stable",
        organism: str = "homo_sapiens",
    ) -> set[str]:
        fc = get_facet_cache()
        cached = fc.get(census_version, organism, column)
        if cached is not None:
            return set(cached)

        # Fall back to shipped catalog.
        v = self.catalog["versions"].get(census_version) or self.catalog["versions"].get("stable")
        if not v:
            return set()
        facets = v["facets"].get(organism) or {}
        values = set(facets.get(column) or [])
        if values:
            fc.set(census_version, organism, column, list(values))
        return values

    def is_present(
        self,
        curie: str,
        *,
        column: str,
        census_version: str = "stable",
        organism: str = "homo_sapiens",
    ) -> bool:
        return curie in self.known_terms(
            column=column, census_version=census_version, organism=organism
        )

    def filter_present(
        self,
        curies: list[str],
        *,
        column: str,
        census_version: str = "stable",
        organism: str = "homo_sapiens",
    ) -> tuple[list[str], list[str]]:
        known = self.known_terms(column=column, census_version=census_version, organism=organism)
        if not known:
            return list(curies), []
        present = [c for c in curies if c in known]
        missing = [c for c in curies if c not in known]
        return present, missing


_singleton: PresenceIndex | None = None


def get_presence_index() -> PresenceIndex:
    global _singleton
    if _singleton is None:
        _singleton = PresenceIndex()
    return _singleton
