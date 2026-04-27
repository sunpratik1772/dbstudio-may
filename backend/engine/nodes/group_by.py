"""
GROUP_BY — partition a dataset into one DataFrame per distinct value.

Paired with MAP to form the fan-out pattern. Example: group orders
by book, then MAP runs a sub-workflow (summary, LLM narrative, ...)
once per book.

We publish each group as its own ctx.datasets[f"{output_prefix}_{key}"]
entry rather than a dict-of-dataframes so downstream collectors / MAP
can address each slice by name with no new port type.
"""
from __future__ import annotations

from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_group_by(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "")
    column: str = cfg.get("group_by_column", "")
    prefix: str = cfg.get("output_prefix", "")
    keys_output: str = cfg.get("keys_output_name") or f"{input_name}_keys"
    dropna = bool(cfg.get("dropna", True))
    order: str = (cfg.get("order") or "first_seen").lower()

    if not input_name or not column or not prefix:
        raise ValueError(
            "GROUP_BY requires input_name, group_by_column, and output_prefix"
        )

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found for GROUP_BY")
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in dataset '{input_name}'")

    working = df.dropna(subset=[column]) if dropna else df

    # Collect keys in the requested order.
    if order == "sort":
        keys = sorted(working[column].unique().tolist())
    elif order == "desc":
        keys = sorted(working[column].unique().tolist(), reverse=True)
    else:  # first_seen
        seen: set = set()
        keys = []
        for v in working[column].tolist():
            if v in seen:
                continue
            seen.add(v)
            keys.append(v)

    def _norm(v):
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            try:
                return v.item()
            except (AttributeError, ValueError):
                return v
        return v

    keys = [_norm(k) for k in keys]

    # Publish one dataset per key.
    for key in keys:
        subset = working[working[column] == key].reset_index(drop=True)
        ctx.datasets[f"{prefix}_{key}"] = subset

    ctx.set(keys_output, {"values": keys})


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_group_by)
