"""Diff two Census releases (schema, summary_cell_counts columns/facets). Not for mock mode."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from cxg_census_mcp.clients.census import get_census_client
from cxg_census_mcp.logging_setup import configure_logging, get_logger

log = get_logger(__name__)

ORGANISMS_DEFAULT = ("homo_sapiens", "mus_musculus")
SAMPLE_LIMIT = 10


def _facet_snapshot(version: str, organisms: tuple[str, ...]) -> dict[str, Any]:
    client = get_census_client()
    if client.is_mock:
        raise RuntimeError("diff_schema_versions requires a live Census handle.")

    summary = client.summary(version=version)
    out: dict[str, Any] = {
        "schema_version": summary.get("schema_version"),
        "organisms": {},
    }
    for organism in organisms:
        try:
            tbl = client.summary_cell_counts(version, organism)
        except Exception as exc:
            log.warning("organism_unavailable", version=version, organism=organism, error=str(exc))
            continue
        cols: dict[str, list[Any]] = {}
        for col in tbl.column_names:
            distinct = sorted({v for v in tbl.column(col).to_pylist() if v is not None and v != ""})
            cols[col] = distinct
        out["organisms"][organism] = cols
    return out


def _diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {
        "schema_version": {
            "left": left.get("schema_version"),
            "right": right.get("schema_version"),
        },
        "organisms_added": sorted(set(right["organisms"]) - set(left["organisms"])),
        "organisms_removed": sorted(set(left["organisms"]) - set(right["organisms"])),
        "by_organism": {},
    }
    for organism in sorted(set(left["organisms"]) | set(right["organisms"])):
        l_cols = left["organisms"].get(organism, {})
        r_cols = right["organisms"].get(organism, {})
        added_cols = sorted(set(r_cols) - set(l_cols))
        removed_cols = sorted(set(l_cols) - set(r_cols))
        per_facet: dict[str, Any] = {}
        for col in sorted(set(l_cols) & set(r_cols)):
            l_vals = set(l_cols[col])
            r_vals = set(r_cols[col])
            added = sorted(r_vals - l_vals)
            removed = sorted(l_vals - r_vals)
            if not added and not removed:
                continue
            per_facet[col] = {
                "added_count": len(added),
                "removed_count": len(removed),
                "added_sample": added[:SAMPLE_LIMIT],
                "removed_sample": removed[:SAMPLE_LIMIT],
            }
        diff["by_organism"][organism] = {
            "columns_added": added_cols,
            "columns_removed": removed_cols,
            "facets": per_facet,
        }
    return diff


def _render_markdown(diff: dict[str, Any], left_version: str, right_version: str) -> str:
    lines: list[str] = []
    sv = diff["schema_version"]
    lines.append(f"# Census diff: `{left_version}` → `{right_version}`")
    lines.append("")
    lines.append(f"- Schema: `{sv['left']}` → `{sv['right']}`")
    if diff["organisms_added"]:
        lines.append(f"- Organisms added: {', '.join(diff['organisms_added'])}")
    if diff["organisms_removed"]:
        lines.append(f"- Organisms removed: {', '.join(diff['organisms_removed'])}")

    for organism, payload in diff["by_organism"].items():
        lines.append("")
        lines.append(f"## `{organism}`")
        if payload["columns_added"]:
            lines.append(
                f"- Columns added: {', '.join(f'`{c}`' for c in payload['columns_added'])}"
            )
        if payload["columns_removed"]:
            lines.append(
                f"- Columns removed: {', '.join(f'`{c}`' for c in payload['columns_removed'])}"
            )
        facets = payload["facets"]
        if not facets:
            lines.append("- No facet value changes.")
            continue
        for col, info in facets.items():
            lines.append("")
            lines.append(f"### `{col}` (+{info['added_count']} / -{info['removed_count']})")
            if info["added_sample"]:
                lines.append("- Added sample:")
                for v in info["added_sample"]:
                    lines.append(f"  - `{v}`")
            if info["removed_sample"]:
                lines.append("- Removed sample:")
                for v in info["removed_sample"]:
                    lines.append(f"  - `{v}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="left", required=True, help="Older Census version")
    parser.add_argument("--to", dest="right", required=True, help="Newer Census version")
    parser.add_argument(
        "--organisms",
        nargs="+",
        default=list(ORGANISMS_DEFAULT),
        help="Organisms to inspect.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    args = parser.parse_args(argv)

    configure_logging()
    organisms = tuple(args.organisms)

    try:
        left = _facet_snapshot(args.left, organisms)
        right = _facet_snapshot(args.right, organisms)
    except Exception as exc:
        log.error("snapshot_failed", error=str(exc))
        return 2

    diff = _diff(left, right)
    if args.json:
        sys.stdout.write(json.dumps(diff, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(_render_markdown(diff, args.left, args.right))
    return 0


if __name__ == "__main__":
    sys.exit(main())
