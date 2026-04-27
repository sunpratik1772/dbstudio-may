"""
EXTRACT_LIST — cascade primitive companion to EXTRACT_SCALAR.

Produces the distinct values of a column as an ordered list. Used as
the fan-out key source for GROUP_BY / MAP in scenarios where the set
of groups is derived at runtime (e.g. "whatever books the trader
touched in this alert's window").
"""
from __future__ import annotations

from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_extract_list(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "")
    column: str = cfg.get("column", "")
    output_name: str = cfg.get("output_name", "")
    order: str = (cfg.get("order") or "first_seen").lower()
    dropna = bool(cfg.get("dropna", True))

    if not input_name or not column or not output_name:
        raise ValueError("EXTRACT_LIST requires input_name, column, and output_name")

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found for EXTRACT_LIST")
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in dataset '{input_name}'")

    series = df[column]
    if dropna:
        series = series.dropna()

    if order == "sort":
        values = sorted(series.unique().tolist())
    elif order == "desc":
        values = sorted(series.unique().tolist(), reverse=True)
    else:  # first_seen
        seen: set = set()
        values = []
        for v in series.tolist():
            if v in seen:
                continue
            seen.add(v)
            values.append(v)

    # Normalise numpy scalars in the list to plain Python.
    def _norm(v):
        if hasattr(v, "item"):
            try:
                return v.item()
            except (AttributeError, ValueError):
                return v
        return v

    values = [_norm(v) for v in values]

    ctx.set(output_name, {"values": values})


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_extract_list)
