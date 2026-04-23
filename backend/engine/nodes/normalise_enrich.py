from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_normalise_enrich(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "trade_data")
    output_name: str = cfg.get("output_name", input_name)
    field_renames: dict = cfg.get("field_renames", {})
    track_lifecycle: bool = cfg.get("track_lifecycle", False)
    compute_signed_notional: bool = cfg.get("compute_signed_notional", False)

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found in context")

    df = df.copy()

    if field_renames:
        df = df.rename(columns=field_renames)

    if track_lifecycle and "status" in df.columns and "order_id" in df.columns:
        sort_col = "order_time" if "order_time" in df.columns else df.columns[0]
        df = df.sort_values(["order_id", sort_col])
        df["_prev_status"] = df.groupby("order_id")["status"].shift(1)
        df["_status_changed"] = df["status"] != df["_prev_status"]
        df["_lifecycle_event"] = df.apply(
            lambda r: f"{r['_prev_status']} → {r['status']}"
            if r["_status_changed"] and pd.notna(r["_prev_status"])
            else "",
            axis=1,
        )

    if compute_signed_notional:
        qty_col = next((c for c in ("exec_quantity", "quantity") if c in df.columns), None)
        price_col = next((c for c in ("exec_price", "limit_price") if c in df.columns), None)
        if qty_col and price_col and "side" in df.columns:
            df["signed_notional"] = df.apply(
                lambda r: r[qty_col] * r[price_col] * (1 if r["side"] == "BUY" else -1),
                axis=1,
            )

    ctx.datasets[output_name] = df


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_normalise_enrich)
