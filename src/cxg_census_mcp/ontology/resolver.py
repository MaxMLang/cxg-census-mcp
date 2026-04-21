"""Resolve free text or CURIEs to terms (exact / fuzzy) or typed refusals."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from rapidfuzz import fuzz

from cxg_census_mcp.clients.ols import OLSClient, OLSHit, get_ols_client
from cxg_census_mcp.errors import OntologyUnavailableError
from cxg_census_mcp.logging_setup import get_logger
from cxg_census_mcp.models.ontology import (
    ResolutionRefusal,
    ResolvedTerm,
    TermCandidate,
)
from cxg_census_mcp.ontology.presence import get_presence_index
from cxg_census_mcp.ontology.registry import column_for, ontology_for_facet
from cxg_census_mcp.utils.curie import is_curie, normalize_curie
from cxg_census_mcp.utils.text_norm import normalize_text

log = get_logger(__name__)

ResolverResult = ResolvedTerm | ResolutionRefusal

FUZZY_ACCEPT_THRESHOLD = 4.5


def _load_hints() -> dict[str, dict[str, Any]]:
    raw = resources.files("cxg_census_mcp.data").joinpath("ontology_hints.json").read_text()
    data = json.loads(raw)
    flat: dict[str, dict[str, Any]] = {}
    for section, entries in data.items():
        if section.startswith("_"):
            continue
        if not isinstance(entries, dict):
            continue
        for key, payload in entries.items():
            if not isinstance(payload, dict) or "canonical" not in payload:
                continue
            flat[normalize_text(key)] = payload
            for alias in payload.get("aliases", []) or []:
                flat[normalize_text(alias)] = payload
    return flat


_HINTS = _load_hints()


async def resolve(
    text: str,
    *,
    ontology: str | None = None,
    facet: str | None = None,
    confirm_ambiguous: bool = False,
    census_version: str = "stable",
    organism: str = "homo_sapiens",
    client: OLSClient | None = None,
) -> ResolverResult:
    """Resolve user text to an ontology term.

    Order of operations:

    1. **Exact CURIE.** If ``text`` matches the CURIE pattern, validate it via OLS.
    2. **Hint overlay.** Curated synonym map (skips OLS entirely).
    3. **Label match.** OLS exact-search scoped to ``ontology``.
    4. **Fuzzy.** OLS fuzzy search + rapidfuzz re-rank with presence penalties.
    """
    if not text or not text.strip():
        return ResolutionRefusal(
            code="TERM_NOT_FOUND",
            message="Empty term text.",
            ontology=ontology,
            action_hint="Provide a non-empty term.",
        )

    raw = text.strip()
    if ontology is None and facet is not None:
        ontology = ontology_for_facet(facet)

    client = client or get_ols_client()

    # 1) exact CURIE
    if is_curie(raw):
        try:
            curie = normalize_curie(raw)
            term = await client.get_term(curie)
        except OntologyUnavailableError as exc:
            return ResolutionRefusal(
                code="ONTOLOGY_UNAVAILABLE",
                message=str(exc),
                ontology=ontology,
                action_hint="Retry shortly; OLS may be temporarily unreachable.",
            )
        if term is None:
            return ResolutionRefusal(
                code="TERM_NOT_FOUND",
                message=f"CURIE not found in OLS: {curie}",
                ontology=ontology or curie.split(":", 1)[0],
                action_hint="Check the CURIE prefix and local id, or use list_available_values.",
            )
        column = _column_id_for_term(term.ontology, facet)
        present_count = _presence_count(curie, column, census_version, organism)
        return ResolvedTerm(
            input=raw,
            curie=curie,
            label=term.label,
            ontology=term.ontology,
            confidence="exact",
            similarity_score=1.0,
            alternatives=[],
            definition=term.definition,
            requires_confirmation=False,
            resolution_path="exact-curie",
            present_in_census=present_count is None or present_count > 0,
            census_presence_count=present_count,
        )

    norm = normalize_text(raw)

    # 2) hint overlay
    hint = _HINTS.get(norm)
    if hint is not None:
        canonical = hint["canonical"]
        column = _column_id_for_term(canonical.split(":", 1)[0], facet)
        present_count = _presence_count(canonical, column, census_version, organism)
        return ResolvedTerm(
            input=raw,
            curie=canonical,
            label=hint.get("label", canonical),
            ontology=canonical.split(":", 1)[0],
            confidence="exact",
            similarity_score=1.0,
            alternatives=[],
            definition=hint.get("note"),
            requires_confirmation=False,
            resolution_path="hint-overlay",
            present_in_census=present_count is None or present_count > 0,
            census_presence_count=present_count,
        )

    # 3) label match
    try:
        exact_hits = await client.search(raw, ontology=ontology, exact=True, limit=5)
    except OntologyUnavailableError as exc:
        return _try_hint_fallback(raw, norm, ontology, exc)

    if len(exact_hits) == 1:
        h = exact_hits[0]
        return _hit_to_resolved(
            raw,
            h,
            confidence="label_match",
            similarity=1.0,
            path="label-match",
            facet=facet,
            census_version=census_version,
            organism=organism,
        )
    if len(exact_hits) > 1:
        return _ambiguous(raw, exact_hits, ontology, facet, census_version, organism)

    # 4) fuzzy
    try:
        fuzzy_hits = await client.search(raw, ontology=ontology, exact=False, limit=10)
    except OntologyUnavailableError as exc:
        return _try_hint_fallback(raw, norm, ontology, exc)

    if not fuzzy_hits:
        return ResolutionRefusal(
            code="TERM_NOT_FOUND",
            message=f"No ontology term matches {raw!r}.",
            ontology=ontology,
            action_hint="Try a synonym, a more specific phrase, or list_available_values.",
        )

    scored = _rank_fuzzy(
        raw, fuzzy_hits, facet=facet, census_version=census_version, organism=organism
    )
    top = scored[0]
    if top.score >= FUZZY_ACCEPT_THRESHOLD and (
        len(scored) == 1 or (top.score - scored[1].score) >= 1.0
    ):
        column = _column_id_for_term(top.ontology, facet)
        present_count = _presence_count(top.curie, column, census_version, organism)
        return ResolvedTerm(
            input=raw,
            curie=top.curie,
            label=top.label,
            ontology=top.ontology,
            confidence="fuzzy",
            similarity_score=round(top.score, 3),
            alternatives=[
                TermCandidate(curie=h.curie, label=h.label, score=round(h.score, 3))
                for h in scored[1:5]
            ],
            definition=None,
            requires_confirmation=False,
            resolution_path=f"fuzzy@{round(top.score, 2)}",
            present_in_census=present_count is None or present_count > 0,
            census_presence_count=present_count,
        )

    if confirm_ambiguous and is_curie(raw):
        return await resolve(raw, ontology=ontology, facet=facet, client=client)

    return ResolutionRefusal(
        code="TERM_AMBIGUOUS",
        message=f"Multiple plausible matches for {raw!r}; please confirm a CURIE.",
        ontology=ontology,
        candidates=[
            TermCandidate(curie=h.curie, label=h.label, score=round(h.score, 3)) for h in scored[:5]
        ],
        action_hint="Re-call with `term=<CURIE>` and confirm_ambiguous=True.",
        retry_with={"term": scored[0].curie, "confirm_ambiguous": True},
    )


# --- helpers ----------------------------------------------------------------


class _Scored:
    __slots__ = ("curie", "is_obsolete", "label", "ontology", "score")

    def __init__(
        self, curie: str, label: str, ontology: str, score: float, is_obsolete: bool
    ) -> None:
        self.curie = curie
        self.label = label
        self.ontology = ontology
        self.score = score
        self.is_obsolete = is_obsolete


def _rank_fuzzy(
    query: str,
    hits: list[OLSHit],
    *,
    facet: str | None,
    census_version: str,
    organism: str,
) -> list[_Scored]:
    presence = get_presence_index()
    q = normalize_text(query)
    scored: list[_Scored] = []
    for h in hits:
        s = 0.0
        label_norm = normalize_text(h.label)
        label_sim = fuzz.token_sort_ratio(q, label_norm) / 100.0
        if label_norm == q:
            s += 3.0
        else:
            s += 1.0 * label_sim

        for syn in h.synonyms or []:
            syn_norm = normalize_text(syn)
            if syn_norm == q:
                s += 2.0
                break
            syn_sim = fuzz.token_sort_ratio(q, syn_norm) / 100.0
            s = max(s, s + 0.5 * syn_sim - 0.4)  # cap synonym contribution

        if h.is_obsolete:
            s -= 1.0

        try:
            column = _column_id_for_term(h.ontology, facet)
            if column and not presence.is_present(
                h.curie, column=column, census_version=census_version, organism=organism
            ):
                s -= 2.0
        except KeyError:
            pass

        scored.append(_Scored(h.curie, h.label, h.ontology, s, h.is_obsolete))
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def _hit_to_resolved(
    raw: str,
    hit: OLSHit,
    *,
    confidence: str,
    similarity: float,
    path: str,
    facet: str | None,
    census_version: str,
    organism: str,
) -> ResolvedTerm:
    column = _column_id_for_term(hit.ontology, facet)
    present_count = _presence_count(hit.curie, column, census_version, organism)
    return ResolvedTerm(
        input=raw,
        curie=hit.curie,
        label=hit.label,
        ontology=hit.ontology,
        confidence=confidence,
        similarity_score=similarity,
        alternatives=[],
        definition=None,
        requires_confirmation=False,
        resolution_path=path,
        present_in_census=present_count is None or present_count > 0,
        census_presence_count=present_count,
    )


def _ambiguous(
    raw: str,
    hits: list[OLSHit],
    ontology: str | None,
    facet: str | None,
    census_version: str,
    organism: str,
) -> ResolutionRefusal:
    cands = [
        TermCandidate(curie=h.curie, label=h.label, score=round(h.score or 0.0, 3)) for h in hits
    ]
    return ResolutionRefusal(
        code="TERM_AMBIGUOUS",
        message=f"{len(hits)} ontology terms have label {raw!r}; please confirm.",
        ontology=ontology,
        candidates=cands,
        action_hint="Pick a CURIE from `candidates` and re-call with confirm_ambiguous=True.",
        retry_with={"term": hits[0].curie, "confirm_ambiguous": True},
    )


def _try_hint_fallback(
    raw: str,
    norm: str,
    ontology: str | None,
    exc: Exception,
) -> ResolverResult:
    hint = _HINTS.get(norm)
    if hint is None:
        return ResolutionRefusal(
            code="ONTOLOGY_UNAVAILABLE",
            message=str(exc),
            ontology=ontology,
            action_hint="OLS unreachable and no local hint match; retry later.",
        )
    canonical = hint["canonical"]
    return ResolvedTerm(
        input=raw,
        curie=canonical,
        label=hint.get("label", canonical),
        ontology=canonical.split(":", 1)[0],
        confidence="hint_fallback",
        similarity_score=None,
        alternatives=[],
        definition=hint.get("note"),
        requires_confirmation=False,
        resolution_path="hint-fallback (OLS unavailable)",
        present_in_census=True,
        census_presence_count=None,
    )


def _column_id_for_term(prefix: str, facet: str | None) -> str:
    try:
        cols = column_for(prefix, facet=facet)
    except KeyError:
        return ""
    return cols.get("id_col", "")


def _presence_count(curie: str, column: str, census_version: str, organism: str) -> int | None:
    if not column:
        return None
    presence = get_presence_index()
    return (
        1
        if presence.is_present(
            curie, column=column, census_version=census_version, organism=organism
        )
        else None
    )
