"""CI: validate shipped ``data/*`` JSON and ``tests/fixtures`` parse + basic shape rules."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from cxg_census_mcp.logging_setup import configure_logging, get_logger
from cxg_census_mcp.utils.curie import is_curie

log = get_logger(__name__)


def _data_text(name: str) -> str:
    return resources.files("cxg_census_mcp.data").joinpath(name).read_text()


def _check_ontology_hints(errors: list[str]) -> None:
    data = json.loads(_data_text("ontology_hints.json"))
    if not isinstance(data, dict):
        errors.append("ontology_hints.json: top-level must be an object")
        return
    for section, entries in data.items():
        if section == "_meta":
            continue
        if not isinstance(entries, dict):
            errors.append(f"ontology_hints.json: section {section!r} must be object")
            continue
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                errors.append(f"ontology_hints.json: {section}.{key!r} must be object")
                continue
            curie = entry.get("canonical")
            if not curie or not isinstance(curie, str) or ":" not in curie:
                errors.append(
                    f"ontology_hints.json: {section}.{key!r} missing/invalid canonical CURIE"
                )
            if not entry.get("label"):
                errors.append(f"ontology_hints.json: {section}.{key!r} missing label")


def _check_tissue_general(errors: list[str]) -> None:
    data = json.loads(_data_text("tissue_general_terms.json"))
    terms = data.get("terms") if isinstance(data, dict) else data
    if not isinstance(terms, list):
        errors.append("tissue_general_terms.json: 'terms' must be a list")
        return
    for t in terms:
        curie = t.get("curie") if isinstance(t, dict) else t
        if not isinstance(curie, str) or not curie.startswith("UBERON:"):
            errors.append(f"tissue_general_terms.json: invalid UBERON CURIE: {t!r}")


def _check_schema_drift(errors: list[str]) -> None:
    try:
        from cxg_census_mcp.ontology.rewrites import _load_rules

        _load_rules()
    except Exception as exc:
        errors.append(f"schema_drift.json: {exc}")


def _check_assay_aliases(errors: list[str]) -> None:
    data = json.loads(_data_text("assay_aliases.json"))
    aliases = data.get("aliases") if isinstance(data, dict) else data
    if not isinstance(aliases, dict):
        errors.append("assay_aliases.json: 'aliases' must be an object")
        return
    for label, curie in aliases.items():
        if not isinstance(curie, str) or not curie.startswith("EFO:"):
            errors.append(f"assay_aliases.json: {label!r} → {curie!r} must be EFO CURIE")


def _check_facet_catalog(errors: list[str]) -> None:
    data = json.loads(_data_text("facet_catalog.json"))
    versions = data.get("versions")
    if not isinstance(versions, dict):
        errors.append("facet_catalog.json: 'versions' must be an object")
        return
    for vname, vobj in versions.items():
        if not isinstance(vobj, dict):
            errors.append(f"facet_catalog.json: version {vname!r} must be object")
            continue
        if "schema_version" not in vobj:
            errors.append(f"facet_catalog.json: version {vname!r} missing schema_version")
        facets = vobj.get("facets") or {}
        for organism, cols in facets.items():
            if not isinstance(cols, dict):
                errors.append(f"facet_catalog.json: {vname}.{organism}: facets must be object")
                continue
            for col, values in cols.items():
                if not isinstance(values, list):
                    errors.append(f"facet_catalog.json: {vname}.{organism}.{col} must be a list")


def _check_seed(errors: list[str]) -> None:
    data = json.loads(_data_text("ols_seed_terms.json"))
    curies = data.get("curies") if isinstance(data, dict) else data
    if not isinstance(curies, list):
        errors.append("ols_seed_terms.json: 'curies' must be a list")
        return
    for c in curies:
        if not isinstance(c, str) or ":" not in c:
            errors.append(f"ols_seed_terms.json: invalid CURIE: {c!r}")


def _check_fixtures(root: Path, errors: list[str]) -> None:
    if not root.exists():
        log.warning("fixtures_dir_missing", path=str(root))
        return

    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None  # type: ignore

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text()
        try:
            if path.suffix == ".json":
                json.loads(text)
            elif path.suffix in {".yaml", ".yml"}:
                if yaml is None:
                    errors.append(f"{path}: PyYAML not installed; cannot validate")
                    continue
                yaml.safe_load(text)
        except Exception as exc:
            errors.append(f"{path}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures",
        help="Path to test fixtures (relative to cwd).",
    )
    args = parser.parse_args(argv)
    configure_logging()

    errors: list[str] = []
    _check_ontology_hints(errors)
    _check_tissue_general(errors)
    _check_schema_drift(errors)
    _check_assay_aliases(errors)
    _check_facet_catalog(errors)
    _check_seed(errors)
    _check_fixtures(Path(args.fixtures), errors)

    # Lightweight sanity check: every CURIE in seed list is shape-valid for OLS
    # consumption (contains a colon). We do not enforce ``is_curie`` because
    # CURIE prefixes like ``HsapDv`` violate that stricter regex by design.
    seed = json.loads(_data_text("ols_seed_terms.json")).get("curies") or []
    for c in seed:
        if isinstance(c, str) and is_curie(c):
            continue  # passes the strict regex; nothing further to check

    if errors:
        for e in errors:
            log.error("fixture_invalid", error=e)
        return 1
    log.info("fixtures_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
