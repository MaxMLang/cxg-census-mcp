"""Re-check hint CURIEs against OLS (conservative; CI exit 0/1/2 = unchanged / diff / error)."""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from cxg_census_mcp.clients.ols import OLSTerm, get_ols_client
from cxg_census_mcp.logging_setup import configure_logging, get_logger

log = get_logger(__name__)


def _hint_path() -> Path:
    return Path(str(resources.files("cxg_census_mcp.data").joinpath("ontology_hints.json")))


def _load() -> dict[str, Any]:
    return json.loads(_hint_path().read_text())


async def _refresh_section(section: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Refresh labels for one top-level section, returning (new, warnings)."""
    client = get_ols_client()
    out: dict[str, Any] = {}
    warnings: list[str] = []
    seen: dict[str, OLSTerm | None] = {}
    for key, entry in section.items():
        if not isinstance(entry, dict) or "canonical" not in entry:
            out[key] = entry
            continue
        curie = entry["canonical"]
        term = seen.get(curie)
        if curie not in seen:
            try:
                term = await client.get_term(curie)
            except Exception as exc:  # pragma: no cover - network/transient
                warnings.append(f"{curie}: {exc}")
                term = None
            seen[curie] = term

        new = dict(entry)
        if term is None:
            warnings.append(f"{key} → {curie}: not found in OLS")
        else:
            if term.is_obsolete:
                warnings.append(f"{key} → {curie}: marked obsolete by OLS")
                new["obsolete"] = True
            if term.label and term.label != entry.get("label"):
                warnings.append(
                    f"{key} → {curie}: label drift {entry.get('label')!r} -> {term.label!r}"
                )
                new["label"] = term.label
        out[key] = new
    return out, warnings


async def _refresh(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    new = {"_meta": dict(data.get("_meta") or {})}
    new["_meta"]["last_refreshed"] = _dt.date.today().isoformat()
    all_warnings: list[str] = []
    for section, entries in data.items():
        if section == "_meta":
            continue
        if not isinstance(entries, dict):
            new[section] = entries
            continue
        refreshed, warnings = await _refresh_section(entries)
        new[section] = refreshed
        all_warnings.extend(f"[{section}] {w}" for w in warnings)
    return new, all_warnings


def _normalize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write changes in place.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the file would change (CI mode). Implies dry-run.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    try:
        existing = _load()
    except Exception as exc:
        log.error("load_failed", error=str(exc))
        return 2

    refreshed, warnings = asyncio.run(_refresh(existing))
    for w in warnings:
        log.warning("hint_refresh", message=w)

    new_text = _normalize(refreshed)
    old_text = _hint_path().read_text()

    if new_text == old_text:
        log.info("hints_unchanged")
        return 0

    if args.write:
        _hint_path().write_text(new_text)
        log.info("hints_written", path=str(_hint_path()))
        return 0

    if args.check:
        log.info("hints_would_change")
        return 1

    sys.stdout.write(new_text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
