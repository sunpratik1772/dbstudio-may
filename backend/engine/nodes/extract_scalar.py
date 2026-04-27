"""
EXTRACT_SCALAR — cascade primitive.

Reduces a column of an upstream dataset to a single value published in
ctx.values. Powers patterns like:

    EXECUTION_DATA_COLLECTOR(source=hs_client_order, all orders in window)
       → EXTRACT_SCALAR(column=trader_id, reducer=unique_single, output=selected_trader)
       → EXECUTION_COLLECTOR(trader_filter_key=selected_trader)

Keeps the graph declarative — no "grab this field inside the collector"
coupling, no Python glue. Every 60 scenarios that cascade one source
into the next use this node.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_extract_scalar(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "")
    column: str = cfg.get("column", "")
    reducer: str = (cfg.get("reducer") or "unique_single").lower()
    output_name: str = cfg.get("output_name", "")
    fail_on_ambiguous = bool(cfg.get("fail_on_ambiguous", False))

    if not input_name or not column or not output_name:
        raise ValueError(
            "EXTRACT_SCALAR requires input_name, column, and output_name"
        )

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found for EXTRACT_SCALAR")
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in dataset '{input_name}'")

    series = df[column]
    value: object

    if reducer == "first":
        value = None if series.empty else series.iloc[0]
    elif reducer == "unique_single":
        uniques = series.dropna().unique().tolist()
        if len(uniques) == 0:
            value = None
        elif len(uniques) == 1:
            value = uniques[0]
        else:
            if fail_on_ambiguous:
                raise ValueError(
                    f"EXTRACT_SCALAR(column='{column}', reducer='unique_single') "
                    f"found {len(uniques)} distinct values"
                )
            value = uniques[0]
    elif reducer == "max":
        value = None if series.empty else series.max()
    elif reducer == "min":
        value = None if series.empty else series.min()
    elif reducer == "count":
        value = int(series.count())
    elif reducer == "sum":
        value = float(series.sum()) if not series.empty else 0.0
    elif reducer == "mean":
        value = float(series.mean()) if not series.empty else 0.0
    else:
        raise ValueError(f"Unknown reducer '{reducer}'")

    # Normalise numpy / pandas scalars to plain Python types so downstream
    # serialisation stays clean.
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass

    ctx.set(output_name, value)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_extract_scalar)
