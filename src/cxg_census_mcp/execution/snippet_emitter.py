"""Build a deterministic local-replay Python snippet from a stored QueryPlan."""

from __future__ import annotations

import textwrap
from typing import Literal

from cxg_census_mcp.planner.query_plan import QueryPlan

Intent = Literal["anndata", "obs_only", "aggregate"]


def emit_snippet(plan: QueryPlan, *, intent: Intent = "anndata") -> str:
    """intent: anndata | obs_only | aggregate."""
    columns_used = sorted(set(plan.columns_used))
    columns_repr = repr(columns_used)
    value_filter_repr = repr(plan.value_filter)
    rewrites_comment = ""
    if plan.schema_rewrites_applied:
        rewrites_comment = (
            "\n# Schema-drift rewrites applied (see docs/schema-drift-format.md):\n# - "
            + "\n# - ".join(plan.schema_rewrites_applied)
        )

    if intent == "obs_only":
        body = f"""
            import cellxgene_census

            with cellxgene_census.open_soma(census_version={plan.census_version!r}) as census:
                obs = cellxgene_census.get_obs(
                    census=census,
                    organism={plan.organism!r},
                    value_filter={value_filter_repr},
                    column_names={columns_repr},
                )
            print(obs.shape)
        """
    elif intent == "aggregate":
        gene_ids_repr = repr(plan.gene_ids)
        group_by_repr = repr((plan.group_by or ["cell_type_ontology_term_id"])[0])
        body = f"""
            import numpy as np
            import pandas as pd
            import cellxgene_census
            import tiledbsoma as soma

            GROUP_BY = {group_by_repr}
            GENE_IDS = {gene_ids_repr}

            with cellxgene_census.open_soma(census_version={plan.census_version!r}) as census:
                exp = census["census_data"][{plan.organism!r}]
                with exp.axis_query(
                    measurement_name="RNA",
                    obs_query=soma.AxisQuery(value_filter={value_filter_repr}),
                    var_query=soma.AxisQuery(value_filter=f"feature_id in {{GENE_IDS!r}}"),
                ) as q:
                    obs = q.obs(column_names=["soma_joinid", GROUP_BY]).concat().to_pandas()
                    var = q.var(column_names=["soma_joinid", "feature_id", "feature_name"]).concat().to_pandas()
                    obs_groups = obs.set_index("soma_joinid")[GROUP_BY]
                    gene_by_jid = var.set_index("soma_joinid")["feature_id"]

                    sums: dict[tuple, float] = {{}}
                    nz: dict[tuple, int] = {{}}
                    cells_per_group: dict[str, set] = {{}}

                    for x in q.X("normalized").tables():
                        o = x["soma_dim_0"].to_numpy()
                        v = x["soma_dim_1"].to_numpy()
                        d = x["soma_data"].to_numpy()
                        for oi, vi, di in zip(o, v, d):
                            grp = obs_groups.get(oi)
                            gid = gene_by_jid.get(vi)
                            if grp is None or gid is None:
                                continue
                            cells_per_group.setdefault(grp, set()).add(int(oi))
                            sums[(grp, gid)] = sums.get((grp, gid), 0.0) + float(di)
                            if di > 0:
                                nz[(grp, gid)] = nz.get((grp, gid), 0) + 1

                    rows = []
                    for (grp, gid), s in sums.items():
                        n = len(cells_per_group.get(grp, set())) or 1
                        rows.append({{
                            "group": grp,
                            "gene_id": gid,
                            "n_cells": n,
                            "mean": s / n,
                            "fraction_expressing": nz.get((grp, gid), 0) / n,
                        }})
                    df = pd.DataFrame(rows).sort_values(["group", "gene_id"])
                    print(df)
        """
    else:  # anndata
        body = f"""
            import cellxgene_census

            with cellxgene_census.open_soma(census_version={plan.census_version!r}) as census:
                # For very large reads, prefer chunked iteration via experiment.axis_query.
                adata = cellxgene_census.get_anndata(
                    census=census,
                    organism={plan.organism!r},
                    obs_value_filter={value_filter_repr},
                    column_names={{"obs": {columns_repr}}},
                )
            print(adata)
        """

    header = f"""
        # Reproduces an MCP query against Census version {plan.census_version!r}
        # Schema version: {plan.schema_version}
        # Tier: {plan.execution_tier}
        # is_primary_data filter applied: {plan.is_primary_data_applied}
        # Estimated cells (pre-query): {plan.estimated_cell_count}
        {rewrites_comment}
    """

    return textwrap.dedent(header).strip() + "\n\n" + textwrap.dedent(body).strip() + "\n"
