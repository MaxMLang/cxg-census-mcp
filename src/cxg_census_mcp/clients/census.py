"""Census SOMA reads; optional mock mode via facet catalog."""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Iterator
from functools import lru_cache
from importlib import resources
from typing import Any

import pyarrow as pa

from cxg_census_mcp.caches.census_handle import get_handle_pool
from cxg_census_mcp.config import get_settings
from cxg_census_mcp.errors import CensusUnavailableError
from cxg_census_mcp.logging_setup import get_logger

log = get_logger(__name__)


def _maybe_int(s: str | None) -> int | None:
    try:
        return int(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _facet_catalog() -> dict[str, Any]:
    raw = resources.files("cxg_census_mcp.data").joinpath("facet_catalog.json").read_text()
    return json.loads(raw)


class CensusClient:
    """Read-only Census / SOMA access (summary, counts, obs/var, X chunks)."""

    def __init__(self, *, mock: bool | None = None) -> None:
        self._settings = get_settings()
        self._mock = self._settings.mock_mode if mock is None else mock
        self._cellxgene_census = self._try_import()
        if not self._mock and self._cellxgene_census is None:
            log.warning(
                "cellxgene_census not installed; falling back to mock mode. "
                "Install with `uv sync --extra census`."
            )
            self._mock = True

    @staticmethod
    def _try_import():
        try:
            return importlib.import_module("cellxgene_census")
        except ImportError:
            return None

    @property
    def is_mock(self) -> bool:
        return self._mock

    # --- handle management ---------------------------------------------------

    def open(self, version: str | None = None):
        version = version or self._settings.census_version
        if self._mock:
            return _MockHandle(version=version, catalog=_facet_catalog())
        pool = get_handle_pool()
        existing = pool.get(version)
        if existing is not None:
            return existing
        handle = self._cellxgene_census.open_soma(census_version=version)
        return pool.put(version, handle)

    def close_all(self) -> None:
        get_handle_pool().close_all()

    # --- read APIs -----------------------------------------------------------

    def summary(self, version: str | None = None) -> dict[str, Any]:
        version = version or self._settings.census_version
        if self._mock:
            cat = _facet_catalog()
            v = cat["versions"].get(version) or cat["versions"]["stable"]
            # In mock mode we deliberately advertise a forward-looking schema
            # version so the schema-drift rewrite codepaths (which only kick
            # in at >=7.0.0 today) stay covered by the integration suite.
            # Live mode reports whatever the actual Census release returns.
            return {
                "census_version": version,
                "schema_version": "7.0.0",
                "organisms": v["organisms"],
                "total_cells": _mock_total_cells(v),
                "build_date": "2026-01-01",
                "source": "mock",
            }
        h = self.open(version)
        # The live census_info.summary table is a (label, value) key-value pair
        # store. We flatten it and normalise the canonical fields the rest of
        # the server expects.
        info = h["census_info"]["summary"].read().concat().to_pydict()
        kv = dict(zip(info.get("label", []), info.get("value", []), strict=False))
        return {
            "census_version": version,
            "schema_version": kv.get("census_schema_version", "unknown"),
            "dataset_schema_version": kv.get("dataset_schema_version"),
            "build_date": kv.get("census_build_date"),
            "organisms": list(h["census_data"].keys()),
            "total_cells": _maybe_int(kv.get("total_cell_count")),
            "unique_cells": _maybe_int(kv.get("unique_cell_count")),
            "source": "live",
        }

    def summary_cell_counts(self, version: str | None, organism: str) -> pa.Table:
        version = version or self._settings.census_version
        if self._mock:
            return _mock_summary_table(version, organism)
        h = self.open(version)
        try:
            tbl = (
                h["census_info"]["summary_cell_counts"]
                .read(value_filter=f"organism == '{organism}'")
                .concat()
            )
            return tbl
        except KeyError as e:  # pragma: no cover
            raise CensusUnavailableError(f"summary_cell_counts unavailable: {e}") from e

    def dataset_metadata(
        self,
        *,
        version: str | None,
        dataset_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Rows from ``census_info.datasets`` (subset or full)."""
        version = version or self._settings.census_version
        if self._mock:
            return _mock_dataset_metadata(dataset_ids)
        h = self.open(version)
        ds_table = h["census_info"]["datasets"]
        if dataset_ids:
            quoted = ", ".join(f"'{d}'" for d in dataset_ids)
            tbl = ds_table.read(value_filter=f"dataset_id in [{quoted}]").concat()
        else:
            tbl = ds_table.read().concat()

        cols = {name: tbl.column(name).to_pylist() for name in tbl.schema.names}
        ids = cols.get("dataset_id", [])
        empty: list[None] = [None] * len(ids)
        out: dict[str, dict[str, Any]] = {}
        for i, ds_id in enumerate(ids):
            out[ds_id] = {
                "dataset_id": ds_id,
                "title": cols.get("dataset_title", empty)[i],
                "collection_id": cols.get("collection_id", empty)[i],
                "collection_name": cols.get("collection_name", empty)[i],
                "collection_doi": cols.get("collection_doi", empty)[i],
                "citation": cols.get("citation", empty)[i],
                "n_cells_total": cols.get("dataset_total_cell_count", empty)[i],
            }
        return out

    def count_obs(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
    ) -> int:
        """Row count for ``value_filter`` via ``axis_query(...).n_obs``."""
        version = version or self._settings.census_version
        if self._mock:
            return _mock_count_obs(value_filter, organism)
        h = self.open(version)
        exp = h["census_data"][organism]
        soma = importlib.import_module("tiledbsoma")
        with exp.axis_query(
            measurement_name="RNA",
            obs_query=soma.AxisQuery(value_filter=value_filter or None),
        ) as q:
            return int(q.n_obs)

    def count_obs_grouped(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
        group_by: str,
    ) -> dict[str, int]:
        """Per-group counts from a single-column obs read."""
        version = version or self._settings.census_version
        if self._mock:
            return _mock_grouped_counts(value_filter, organism, group_by)
        h = self.open(version)
        exp = h["census_data"][organism]
        reader = exp.obs.read(
            value_filter=value_filter or None,
            column_names=[group_by],
        )
        out: dict[str, int] = {}
        chunks = reader.tables() if hasattr(reader, "tables") else iter(reader)
        for chunk in chunks:
            if not isinstance(chunk, pa.Table):
                chunk = (
                    pa.Table.from_batches([chunk]) if isinstance(chunk, pa.RecordBatch) else chunk
                )
            col = chunk.column(group_by).to_pylist()
            for v in col:
                key = str(v) if v is not None else "<unknown>"
                out[key] = out.get(key, 0) + 1
        return out

    def read_obs(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
        column_names: list[str] | None = None,
        limit: int | None = None,
    ) -> pa.Table:
        version = version or self._settings.census_version
        if self._mock:
            return _mock_obs_table(value_filter, column_names, limit, organism)
        h = self.open(version)
        exp = h["census_data"][organism]
        cols = column_names or [
            "soma_joinid",
            "cell_type_ontology_term_id",
            "tissue_ontology_term_id",
            "tissue_general_ontology_term_id",
            "disease_ontology_term_id",
            "assay_ontology_term_id",
            "is_primary_data",
            "dataset_id",
            "donor_id",
        ]
        reader = exp.obs.read(value_filter=value_filter or None, column_names=cols)
        tbl = reader.concat()
        if limit is not None and tbl.num_rows > limit:
            tbl = tbl.slice(0, limit)
        return tbl

    def stream_obs(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
        column_names: list[str] | None = None,
        chunk_rows: int = 50_000,
    ) -> Iterator[pa.Table]:
        """Chunked obs tables (SOMA ``read().tables()`` when available)."""
        version = version or self._settings.census_version
        if self._mock:
            yield _mock_obs_table(value_filter, column_names, chunk_rows, organism)
            return
        h = self.open(version)
        exp = h["census_data"][organism]
        cols = column_names or [
            "soma_joinid",
            "cell_type_ontology_term_id",
            "tissue_ontology_term_id",
            "tissue_general_ontology_term_id",
            "disease_ontology_term_id",
            "assay_ontology_term_id",
            "is_primary_data",
            "dataset_id",
            "donor_id",
        ]
        reader = exp.obs.read(value_filter=value_filter or None, column_names=cols)
        if hasattr(reader, "tables"):
            yield from reader.tables()
        else:
            for chunk in reader:
                if isinstance(chunk, pa.Table):
                    yield chunk
                else:
                    yield (
                        pa.Table.from_batches([chunk])
                        if isinstance(chunk, pa.RecordBatch)
                        else chunk
                    )

    def aggregate_expression_chunks(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
        gene_ids: list[str],
        group_by: str,
        chunk_rows: int = 200_000,
    ) -> Iterator[tuple[dict[tuple[str, str], dict[str, float]], int]]:
        """Yield ``(partial_acc, n_cells_with_x_values_this_chunk)`` from sparse X."""
        version = version or self._settings.census_version
        if self._mock:
            yield _mock_expression_chunk(value_filter, gene_ids, group_by, organism), 50
            return

        h = self.open(version)
        exp = h["census_data"][organism]
        soma = importlib.import_module("tiledbsoma")

        var_filter = f"feature_id in {gene_ids!r}"
        with exp.axis_query(
            measurement_name="RNA",
            obs_query=soma.AxisQuery(value_filter=value_filter or None),
            var_query=soma.AxisQuery(value_filter=var_filter),
        ) as q:
            obs_tbl = q.obs(column_names=["soma_joinid", group_by]).concat()
            var_tbl = q.var(column_names=["soma_joinid", "feature_id"]).concat()

            obs_groups: dict[int, str] = {}
            group_total_cells: dict[str, int] = {}
            for r in obs_tbl.to_pylist():
                grp_label = str(r.get(group_by) or "<unknown>")
                obs_groups[int(r["soma_joinid"])] = grp_label
                group_total_cells[grp_label] = group_total_cells.get(grp_label, 0) + 1

            gene_by_jid: dict[int, str] = {}
            for r in var_tbl.to_pylist():
                gene_by_jid[int(r["soma_joinid"])] = str(r["feature_id"])

            x_reader = q.X("normalized")
            chunks_iter = x_reader.tables() if hasattr(x_reader, "tables") else iter(x_reader)

            for x_chunk in chunks_iter:
                acc: dict[tuple[str, str], dict[str, float]] = {}
                obs_jids = x_chunk["soma_dim_0"].to_pylist()
                var_jids = x_chunk["soma_dim_1"].to_pylist()
                values = x_chunk["soma_data"].to_pylist()
                seen_obs: set[int] = set()
                for o, v, val in zip(obs_jids, var_jids, values, strict=False):
                    grp = obs_groups.get(o)
                    gid = gene_by_jid.get(v)
                    if grp is None or gid is None:
                        continue
                    seen_obs.add(o)
                    key = (grp, gid)
                    a = acc.setdefault(
                        key,
                        {
                            "sum": 0.0,
                            "sum_sq": 0.0,
                            "n_nonzero": 0,
                            "n_cells": float(group_total_cells.get(grp, 0)),
                        },
                    )
                    a["sum"] += float(val)
                    a["sum_sq"] += float(val) * float(val)
                    if val > 0:
                        a["n_nonzero"] += 1
                yield acc, len(seen_obs)

    def read_var(
        self,
        *,
        version: str | None,
        organism: str,
        value_filter: str,
        column_names: list[str] | None = None,
    ) -> pa.Table:
        version = version or self._settings.census_version
        if self._mock:
            return _mock_var_table(value_filter, column_names, organism)
        h = self.open(version)
        exp = h["census_data"][organism]
        ms = exp.ms["RNA"]
        cols = column_names or ["soma_joinid", "feature_id", "feature_name"]
        return ms.var.read(value_filter=value_filter or None, column_names=cols).concat()

    def gene_presence_summary(
        self, *, version: str | None, organism: str, gene_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Gene id → name, var membership, optional dataset presence counts."""
        version = version or self._settings.census_version
        var_tbl = self.read_var(
            version=version,
            organism=organism,
            value_filter=f"feature_id in {gene_ids!r}",
        )
        var_rows = var_tbl.to_pylist()
        by_id: dict[str, dict[str, Any]] = {}
        for r in var_rows:
            fid = r.get("feature_id")
            if fid:
                by_id[fid] = {
                    "feature_name": r.get("feature_name"),
                    "feature_jid": r.get("soma_joinid"),
                    "n_datasets": None,
                    "present_in_var": True,
                }
        out: dict[str, dict[str, Any]] = {}
        for gid in gene_ids:
            out[gid] = by_id.get(gid) or {
                "feature_name": None,
                "feature_jid": None,
                "n_datasets": None,
                "present_in_var": False,
            }

        if self._mock:
            for info in out.values():
                info["n_datasets"] = 3 if info["present_in_var"] else 0
            return out

        try:
            h = self.open(version)
            ms = h["census_data"][organism].ms["RNA"]
            presence = ms["feature_dataset_presence_matrix"]
            jid_to_id = {
                info["feature_jid"]: gid
                for gid, info in out.items()
                if info["feature_jid"] is not None
            }
            if not jid_to_id:
                return out
            tbl = presence.read(coords=(slice(None), list(jid_to_id.keys()))).tables().concat()
            counts: dict[int, int] = {}
            for jid in tbl["soma_dim_1"].to_pylist():
                counts[int(jid)] = counts.get(int(jid), 0) + 1
            for jid, gid in jid_to_id.items():
                out[gid]["n_datasets"] = counts.get(jid, 0)
        except Exception as exc:
            log.warning("gene_presence_summary_failed", error=str(exc))
        return out


# --- mock helpers ------------------------------------------------------------


class _MockHandle:
    def __init__(self, *, version: str, catalog: dict[str, Any]) -> None:
        self.version = version
        self.catalog = catalog
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _mock_total_cells(v: dict[str, Any]) -> int:
    return 60_000_000


def _mock_dataset_metadata(dataset_ids: list[str] | None) -> dict[str, dict[str, Any]]:
    ids = dataset_ids or [f"mock-{i:08d}-0000-0000-0000-000000000000" for i in range(3)]
    return {
        ds_id: {
            "dataset_id": ds_id,
            "title": f"Mock dataset {i}",
            "collection_id": f"mock-collection-{i}",
            "collection_name": f"Mock collection {i}",
            "collection_doi": f"10.0000/mock.{i}",
            "citation": f"Mock et al. ({2020 + i}). Mock Journal.",
            "n_cells_total": 100_000 * (i + 1),
        }
        for i, ds_id in enumerate(ids)
    }


def _mock_count_obs(value_filter: str, organism: str) -> int:
    """Deterministic small-but-nonzero count for mock-mode count_cells.

    Uses the filter string as a hash seed so repeated calls return the same
    number, but different filters return different numbers.
    """
    return 12_345 + (abs(hash((organism, value_filter))) % 90_000)


def _mock_groups_for(group_by: str, organism: str) -> list[str]:
    """Pick a representative set of group values for a given obs column.

    Mock mode honours the caller's requested ``group_by`` so heat-map style
    queries (e.g. expression by tissue or by dataset) don't always collapse
    onto the cell-type axis. Values are pinned where possible to CURIEs that
    already appear in the shipped facet catalog so any subsequent filter on
    a returned group key resolves cleanly.
    """
    pins = {
        "cell_type_ontology_term_id": [
            "CL:0000236",  # B cell
            "CL:0000084",  # T cell
            "CL:0000235",  # macrophage
            "CL:0000540",  # neuron
        ],
        "tissue_general_ontology_term_id": [
            "UBERON:0002048",  # lung
            "UBERON:0000955",  # brain
            "UBERON:0000178",  # blood
            "UBERON:0001155",  # colon
            "UBERON:0002107",  # liver
            "UBERON:0002106",  # spleen
        ],
        "tissue_ontology_term_id": [
            "UBERON:0002048",
            "UBERON:0000955",
            "UBERON:0000178",
        ],
        "disease_ontology_term_id": [
            "PATO:0000461",  # normal
            "MONDO:0100096",  # COVID-19
            "MONDO:0004975",  # Alzheimer disease
        ],
        "assay_ontology_term_id": [
            "EFO:0009922",  # 10x 3' v3
            "EFO:0010550",  # sci-RNA-seq3
        ],
        "dataset_id": [f"mock-{i:08d}-0000-0000-0000-000000000000" for i in range(4)],
        "donor_id": [f"mock-donor-{i}" for i in range(4)],
    }
    return pins.get(group_by, [f"mock-group-{i}" for i in range(3)])


def _mock_grouped_counts(value_filter: str, organism: str, group_by: str) -> dict[str, int]:
    base = _mock_count_obs(value_filter, organism)
    groups = _mock_groups_for(group_by, organism)
    return {g: max(1, base // (i + 2)) for i, g in enumerate(groups)}


def _mock_summary_table(version: str, organism: str) -> pa.Table:
    cat = _facet_catalog()
    v = cat["versions"].get(version) or cat["versions"]["stable"]
    facets = v["facets"].get(organism) or {}
    # The on-disk catalog now mirrors the live Census, which has 900+ cell
    # types and 70+ tissues. A naive Cartesian product over those is ~17M
    # rows and locks tests up for minutes. Cap each axis to a small slice;
    # mock-mode tests only need representative rows for assertion purposes.
    # We pin a few well-known CURIEs at the head of each axis so the
    # integration suite (which asserts on B cell, lung, COVID, etc.) keeps
    # working regardless of catalog refresh ordering.
    _MOCK_AXIS_CAP = 12
    _MOCK_PINS = {
        "cell_type_ontology_term_id": [
            "CL:0000236",  # B cell
            "CL:0000084",  # T cell
            "CL:0000235",  # macrophage
            "CL:0000540",  # neuron
            "CL:0000625",  # CD8-positive, alpha-beta T cell
        ],
        "tissue_general_ontology_term_id": [
            "UBERON:0002048",  # lung
            "UBERON:0000955",  # brain
            "UBERON:0000059",  # large intestine
            "UBERON:0001155",  # colon
            "UBERON:0000178",  # blood
        ],
        "disease_ontology_term_id": [
            "PATO:0000461",  # normal
            "MONDO:0100096",  # COVID-19
            "MONDO:0004975",  # Alzheimer disease
            "MONDO:0005148",  # type 2 diabetes
        ],
    }

    def _capped(col: str, fallback: list[str]) -> list[str]:
        all_values = facets.get(col) or fallback
        pinned = [
            v for v in _MOCK_PINS.get(col, []) if v in set(all_values) or all_values is fallback
        ]
        rest = [v for v in all_values if v not in set(pinned)]
        return (pinned + rest)[:_MOCK_AXIS_CAP]

    cell_types = _capped("cell_type_ontology_term_id", ["CL:0000236"])
    tissues = _capped("tissue_general_ontology_term_id", ["UBERON:0002048"])
    diseases = _capped("disease_ontology_term_id", ["PATO:0000461"])
    rows: list[dict[str, Any]] = []
    n = 0
    for ct in cell_types:
        for ts in tissues:
            for ds in diseases:
                n += 1
                rows.append(
                    {
                        "organism": organism,
                        "cell_type_ontology_term_id": ct,
                        "tissue_ontology_term_id": ts,
                        "tissue_general_ontology_term_id": ts,
                        "disease_ontology_term_id": ds,
                        "is_primary_data": True,
                        "n_cells": 1000 * n,
                    }
                )
    return pa.Table.from_pylist(rows)


def _mock_obs_table(
    value_filter: str,
    column_names: Iterable[str] | None,
    limit: int | None,
    organism: str,
) -> pa.Table:
    cols = (
        list(column_names)
        if column_names
        else [
            "soma_joinid",
            "cell_type_ontology_term_id",
            "tissue_general_ontology_term_id",
            "disease_ontology_term_id",
            "is_primary_data",
            "dataset_id",
        ]
    )
    n = min(limit or 50, 50)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        row: dict[str, Any] = {}
        for c in cols:
            if c == "soma_joinid":
                row[c] = i
            elif c == "is_primary_data":
                row[c] = True
            elif c == "dataset_id":
                row[c] = f"mock-{i % 3:08d}-0000-0000-0000-000000000000"
            elif c == "cell_type_ontology_term_id":
                row[c] = "CL:0000236"
            elif c == "tissue_general_ontology_term_id":
                row[c] = "UBERON:0002048"
            elif c == "disease_ontology_term_id":
                row[c] = "MONDO:0100096"
            else:
                row[c] = None
        rows.append(row)
    return pa.Table.from_pylist(rows)


def _mock_expression_chunk(
    value_filter: str,
    gene_ids: list[str],
    group_by: str,
    organism: str,
) -> dict[tuple[str, str], dict[str, float]]:
    """Synthetic per-(group, gene) sufficient stats that vary deterministically.

    The mock used to return a fixed CL:0000236 / CL:0000084 axis with uniform
    0.9 means regardless of the requested ``group_by``. That made anything
    other than cell-type grouping in mock mode look like censored placeholder
    data. Now: the group axis follows ``group_by`` (lung / brain / blood /
    … for tissue, dataset UUIDs for dataset_id, etc) and the per-cell mean
    is jittered by a stable hash of (group, gene) so heat-map style queries
    actually look heat-map-ish.
    """
    groups = _mock_groups_for(group_by, organism)
    acc: dict[tuple[str, str], dict[str, float]] = {}
    for grp in groups:
        for gid in gene_ids:
            seed = abs(hash((grp, gid, organism))) % 10_000
            n_cells = 60 + seed % 200
            fraction = 0.05 + (seed % 90) / 100.0  # 0.05 .. 0.94
            n_nonzero = max(1, int(n_cells * fraction))
            mean_per_expressing = 0.4 + (seed % 250) / 100.0  # 0.4 .. 2.9
            sum_v = mean_per_expressing * n_nonzero
            sum_sq = (mean_per_expressing**2) * n_nonzero
            acc[(grp, gid)] = {
                "sum": sum_v,
                "sum_sq": sum_sq,
                "n_nonzero": n_nonzero,
                "n_cells": float(n_cells),
            }
    return acc


def _mock_var_table(
    value_filter: str, column_names: Iterable[str] | None, organism: str
) -> pa.Table:
    cols = list(column_names) if column_names else ["soma_joinid", "feature_id", "feature_name"]
    sample_genes = (
        [("ENSG00000141510", "TP53"), ("ENSG00000146648", "EGFR"), ("ENSG00000133703", "KRAS")]
        if organism == "homo_sapiens"
        else [("ENSMUSG00000059552", "Trp53")]
    )
    rows = []
    for i, (gid, sym) in enumerate(sample_genes):
        rows.append(
            {c: ({"soma_joinid": i, "feature_id": gid, "feature_name": sym}.get(c)) for c in cols}
        )
    return pa.Table.from_pylist(rows)


@lru_cache(maxsize=1)
def get_census_client() -> CensusClient:
    return CensusClient()
