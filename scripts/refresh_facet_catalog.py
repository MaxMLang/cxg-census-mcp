"""Build facet_catalog.json from live ``summary_cell_counts`` (not mock). CI: exit 0/1/2 = unchanged / diff / error."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.logging_setup import configure_logging, get_logger

log = get_logger(__name__)

FACET_COLUMNS_BY_ORGANISM = {
    "homo_sapiens": [
        "cell_type_ontology_term_id",
        "tissue_ontology_term_id",
        "tissue_general_ontology_term_id",
        "disease_ontology_term_id",
        "assay_ontology_term_id",
        "self_reported_ethnicity_ontology_term_id",
        "sex",
        "suspension_type",
    ],
    "mus_musculus": [
        "cell_type_ontology_term_id",
        "tissue_ontology_term_id",
        "tissue_general_ontology_term_id",
        "assay_ontology_term_id",
        "sex",
        "suspension_type",
    ],
}

# census_info.summary_cell_counts is a long-format marginal table with columns
# (organism, category, label, ontology_term_id, ...). The category strings are
# the un-suffixed facet names (``cell_type``, ``tissue``, ``tissue_general``,
# ``disease``, ``assay``, ``self_reported_ethnicity``, ``sex``,
# ``suspension_type``). Map them to the column names the planner uses
# downstream so the on-disk catalog is keyed identically to the resolver's
# ``column_for(...)`` output.
_CATEGORY_TO_COLUMN: dict[str, str] = {
    "cell_type": "cell_type_ontology_term_id",
    "tissue": "tissue_ontology_term_id",
    "tissue_general": "tissue_general_ontology_term_id",
    "disease": "disease_ontology_term_id",
    "assay": "assay_ontology_term_id",
    "self_reported_ethnicity": "self_reported_ethnicity_ontology_term_id",
    "sex": "sex",
    "suspension_type": "suspension_type",
}
# Categories whose values live in the ``label`` column rather than the
# ``ontology_term_id`` column (the latter is "na" for non-ontology facets).
_LABEL_VALUED_CATEGORIES = {"sex", "suspension_type"}


def _facet_path() -> Path:
    return Path(str(resources.files("cxg_census_mcp.data").joinpath("facet_catalog.json")))


def _normalize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _extract_facets_from_long_table(tbl: Any, wanted_columns: list[str]) -> dict[str, list[str]]:
    """Pivot the long-format summary_cell_counts table into per-column value sets.

    The live ``census_info.summary_cell_counts`` table has columns
    ``category``, ``label``, ``ontology_term_id`` (and per-cell counts). For
    ontology categories (cell_type, tissue, ...) the value of interest is in
    ``ontology_term_id``; for the categorical facets (sex, suspension_type)
    it lives in ``label`` because ``ontology_term_id`` is the literal string
    ``"na"``.
    """
    schema_names = set(tbl.column_names)
    if "category" not in schema_names:
        return {}

    categories = tbl.column("category").to_pylist()
    ontology_ids = (
        tbl.column("ontology_term_id").to_pylist()
        if "ontology_term_id" in schema_names
        else [None] * len(categories)
    )
    labels = (
        tbl.column("label").to_pylist() if "label" in schema_names else [None] * len(categories)
    )

    bucket: dict[str, set[str]] = {col: set() for col in wanted_columns}
    for cat, oid, lab in zip(categories, ontology_ids, labels, strict=True):
        col = _CATEGORY_TO_COLUMN.get(cat)
        if col is None or col not in bucket:
            continue
        value = lab if cat in _LABEL_VALUED_CATEGORIES else oid
        if value is None or value == "" or value == "na":
            continue
        bucket[col].add(str(value))

    return {col: sorted(vs) for col, vs in bucket.items() if vs}


def _build(version: str, organisms: list[str]) -> dict[str, Any]:
    client = get_census_client()
    if client.is_mock:
        raise RuntimeError(
            "Refusing to refresh facet catalog in mock mode. "
            "Install the 'census' extra and unset CXG_CENSUS_MCP_MOCK_MODE."
        )

    summary = client.summary(version=version)
    schema_version = summary.get("schema_version") or summary.get("census_schema_version") or ""
    resolved_version = str(summary.get("census_version") or version)

    facets: dict[str, dict[str, Any]] = {}
    for organism in organisms:
        cols = FACET_COLUMNS_BY_ORGANISM.get(organism, [])
        tbl = client.summary_cell_counts(resolved_version, organism)
        per_org = _extract_facets_from_long_table(tbl, cols)
        log.info(
            "facet_catalog_organism_extracted",
            organism=organism,
            columns={k: len(v) for k, v in per_org.items()},
        )
        facets[organism] = per_org

    payload = {
        "schema_version": schema_version,
        "organisms": organisms,
        "facets": facets,
    }
    return {
        "_meta": {
            "schema": 1,
            "description": "Per-Census-version facet snapshot. Refreshed by scripts/refresh_facet_catalog.py.",
            "last_refreshed": _dt.date.today().isoformat(),
            "census_version": resolved_version,
        },
        "versions": {
            # Write under both the resolved date and ``stable`` so that callers
            # using either ``settings.census_version="stable"`` or the explicit
            # release tag get a hit. The planner's settings default to
            # ``stable`` so the alias matters in practice.
            resolved_version: payload,
            "stable": dict(payload, aliased_to=resolved_version),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=None, help="Census version (defaults to settings).")
    parser.add_argument(
        "--organisms",
        nargs="+",
        default=["homo_sapiens", "mus_musculus"],
        help="Organisms to enumerate.",
    )
    parser.add_argument("--write", action="store_true", help="Write changes in place.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if file would change.")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging()
    version = args.version or settings.census_version

    try:
        new_payload = _build(version, args.organisms)
    except Exception as exc:
        log.error("facet_refresh_failed", error=str(exc))
        return 2

    new_text = _normalize(new_payload)
    old_text = _facet_path().read_text()

    if new_text == old_text:
        log.info("facets_unchanged", version=version)
        return 0

    if args.write:
        _facet_path().write_text(new_text)
        log.info("facets_written", path=str(_facet_path()), version=version)
        return 0

    if args.check:
        log.info("facets_would_change", version=version)
        return 1

    sys.stdout.write(new_text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
