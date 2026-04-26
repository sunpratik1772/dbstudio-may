"""Apply explicit feature operations to a DataFrame.

This replaces legacy enrichment booleans with a small ordered list
of named operations. The contract is easier to extend: add a new operation
handler here and document it in the YAML instead of growing one node with more
flags.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _rename(df: pd.DataFrame, op: dict) -> pd.DataFrame:
    mapping = op.get("columns") or op.get("field_renames") or {}
    return df.rename(columns=mapping) if mapping else df


def _lifecycle_event(df: pd.DataFrame, op: dict) -> pd.DataFrame:
    id_col = op.get("id_col", "order_id")
    status_col = op.get("status_col", "status")
    time_col = op.get("time_col") or ("order_time" if "order_time" in df.columns else df.columns[0])
    if id_col not in df.columns or status_col not in df.columns:
        return df
    out = df.sort_values([id_col, time_col]).copy()
    out["_prev_status"] = out.groupby(id_col)[status_col].shift(1)
    out["_status_changed"] = out[status_col] != out["_prev_status"]
    out["_lifecycle_event"] = out.apply(
        lambda r: f"{r['_prev_status']} -> {r[status_col]}"
        if r["_status_changed"] and pd.notna(r["_prev_status"])
        else "",
        axis=1,
    )
    return out


def _derive_signed_notional(df: pd.DataFrame, op: dict) -> pd.DataFrame:
    qty_col = op.get("quantity_col") or next((c for c in ("exec_quantity", "quantity") if c in df.columns), None)
    price_col = op.get("price_col") or next((c for c in ("exec_price", "limit_price") if c in df.columns), None)
    side_col = op.get("side_col", "side")
    output_col = op.get("output_col", "signed_notional")
    if not (qty_col and price_col and side_col in df.columns):
        raise ValueError(
            "FEATURE_ENGINE derive_signed_notional requires a quantity column "
            "(exec_quantity or quantity), a price column (exec_price or limit_price), and side. "
            f"Found columns: {list(df.columns)}"
        )
    out = df.copy()
    out[output_col] = out.apply(
        lambda r: r[qty_col] * r[price_col] * (1 if r[side_col] == "BUY" else -1),
        axis=1,
    )
    return out


_OPS = {
    "rename": _rename,
    "lifecycle_event": _lifecycle_event,
    "derive_signed_notional": _derive_signed_notional,
}


def handle_feature_engine(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "execution_data")
    output_name: str = cfg.get("output_name", input_name)
    operations: list[dict] = cfg.get("operations", [])

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found in context")

    out = df.copy()
    for op in operations:
        op_name = op.get("op") or op.get("type")
        handler = _OPS.get(op_name)
        if handler is None:
            raise ValueError(f"FEATURE_ENGINE unknown operation '{op_name}'")
        out = handler(out, op)

    ctx.datasets[output_name] = out
    src = ctx.dataset_provenance.get(input_name)
    if src:
        ctx.dataset_provenance[output_name] = src


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_feature_engine)
