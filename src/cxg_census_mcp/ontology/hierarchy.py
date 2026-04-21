"""Thin wrappers around OLS descendants/ancestors (cached)."""

from __future__ import annotations

from collections.abc import Iterable

from cxg_census_mcp.clients.ols import OLSClient, get_ols_client
from cxg_census_mcp.utils.curie import normalize_curie, parse_curie


async def descendants_of(
    curie: str, *, ontology: str | None = None, client: OLSClient | None = None
) -> set[str]:
    client = client or get_ols_client()
    curie = normalize_curie(curie)
    return set(await client.get_descendants(curie, ontology=ontology))


async def ancestors_of(
    curie: str, *, ontology: str | None = None, client: OLSClient | None = None
) -> set[str]:
    client = client or get_ols_client()
    curie = normalize_curie(curie)
    return set(await client.get_ancestors(curie, ontology=ontology))


async def all_descendants_of(
    leaves: Iterable[str], root: str, *, client: OLSClient | None = None
) -> bool:
    """True if every CURIE in ``leaves`` is a descendant of ``root`` (or equal to it)."""
    client = client or get_ols_client()
    leaves = {normalize_curie(c) for c in leaves}
    root = normalize_curie(root)
    if root in leaves and len(leaves) == 1:
        return True
    desc = await descendants_of(root, ontology=parse_curie(root)[0], client=client)
    desc.add(root)
    return leaves.issubset(desc)
