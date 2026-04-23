from pathlib import Path

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml

# These 5 columns are the contract — always present, no exceptions
SIGNAL_COLUMNS = ["_signal_flag", "_signal_score", "_signal_reason", "_signal_type", "_signal_window"]


# ── built-in signal implementations ──────────────────────────────────────────

def _front_running(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    window_min = params.get("window_minutes", 5)
    threshold = params.get("price_move_threshold", 0.0003)

    df = df.copy()
    if "exec_time" in df.columns and "exec_price" in df.columns:
        df["exec_time"] = pd.to_datetime(df["exec_time"])
        df = df.sort_values("exec_time").reset_index(drop=True)
        df["_price_move"] = df["exec_price"].diff().abs().fillna(0)
        df["_signal_flag"] = df["_price_move"] > threshold
        df["_signal_score"] = (df["_price_move"] / threshold).clip(0, 10).round(2)
        df["_signal_reason"] = df.apply(
            lambda r: f"Price moved {r['_price_move']:.5f} (>{threshold}) within {window_min}m"
            if r["_signal_flag"] else "",
            axis=1,
        )
        df = df.drop(columns=["_price_move"])
    else:
        df["_signal_flag"] = False
        df["_signal_score"] = 0.0
        df["_signal_reason"] = ""

    df["_signal_type"] = "FRONT_RUNNING"
    df["_signal_window"] = f"{window_min}m"
    return df


def _wash_trade(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    window_min = params.get("window_minutes", 10)
    threshold = params.get("ratio_threshold", 0.8)

    df = df.copy()
    if "side" in df.columns and "exec_quantity" in df.columns:
        buy_qty = df.loc[df["side"] == "BUY", "exec_quantity"].sum()
        sell_qty = df.loc[df["side"] == "SELL", "exec_quantity"].sum()
        denom = max(buy_qty, sell_qty, 1)
        ratio = min(buy_qty, sell_qty) / denom
        flag = ratio > threshold
        df["_signal_flag"] = flag
        df["_signal_score"] = round(ratio * 10, 2)
        df["_signal_reason"] = f"Buy/Sell qty ratio {ratio:.2%} exceeds {threshold:.0%}" if flag else ""
    else:
        df["_signal_flag"] = False
        df["_signal_score"] = 0.0
        df["_signal_reason"] = ""

    df["_signal_type"] = "WASH_TRADE"
    df["_signal_window"] = f"{window_min}m"
    return df


def _spoofing(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = params.get("cancel_ratio_threshold", 0.7)

    df = df.copy()
    if "status" in df.columns:
        total = len(df)
        cancelled = (df["status"] == "CANCELLED").sum()
        ratio = cancelled / total if total else 0
        flag = ratio > threshold
        df["_signal_flag"] = flag
        df["_signal_score"] = round(ratio * 10, 2)
        df["_signal_reason"] = f"Cancel ratio {ratio:.2%} exceeds {threshold:.0%}" if flag else ""
    else:
        df["_signal_flag"] = False
        df["_signal_score"] = 0.0
        df["_signal_reason"] = ""

    df["_signal_type"] = "SPOOFING"
    df["_signal_window"] = params.get("window", "1d")
    return df


def _layering(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    min_layers = params.get("min_layers", 5)

    df = df.copy()
    if "order_type" in df.columns and "side" in df.columns:
        buy_limits = ((df["order_type"] == "LIMIT") & (df["side"] == "BUY")).sum()
        sell_limits = ((df["order_type"] == "LIMIT") & (df["side"] == "SELL")).sum()
        imbalance = int(abs(buy_limits - sell_limits))
        flag = imbalance >= min_layers
        df["_signal_flag"] = flag
        df["_signal_score"] = min(round(imbalance / min_layers * 5, 2), 10)
        df["_signal_reason"] = f"Limit order imbalance: {imbalance} orders on one side" if flag else ""
    else:
        df["_signal_flag"] = False
        df["_signal_score"] = 0.0
        df["_signal_reason"] = ""

    df["_signal_type"] = "LAYERING"
    df["_signal_window"] = params.get("window", "30m")
    return df


BUILT_IN = {
    "FRONT_RUNNING": _front_running,
    "WASH_TRADE": _wash_trade,
    "SPOOFING": _spoofing,
    "LAYERING": _layering,
}


# ── handler ───────────────────────────────────────────────────────────────────

def handle_signal_calculator(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    mode: str = cfg.get("mode", "configure")
    input_name: str = cfg.get("input_name", "trade_data")
    output_name: str = cfg.get("output_name", "signal_data")

    df = ctx.datasets.get(input_name)
    if df is None:
        raise KeyError(f"Dataset '{input_name}' not found")

    if mode == "configure":
        signal_type: str = cfg.get("signal_type", "FRONT_RUNNING")
        params: dict = cfg.get("params", {})
        fn = BUILT_IN.get(signal_type)
        if not fn:
            raise ValueError(f"Unknown built-in signal type: '{signal_type}'")
        df = fn(df, params)

    elif mode == "upload_script":
        # Prefer inline script_content if the caller supplied it (LLM-generated workflows
        # commonly do this). Otherwise fall back to reading from script_path on disk.
        script: str = cfg.get("script_content", "")
        if not script:
            script_path: str = cfg.get("script_path", "")
            if not script_path:
                raise ValueError("upload_script mode requires either 'script_content' or 'script_path'")
            with open(script_path) as f:
                script = f.read()
        local_ns: dict = {"df": df.copy(), "params": cfg.get("params", {}), "pd": pd, "np": np}
        exec(script, local_ns)  # noqa: S102
        df = local_ns.get("df", df)

    # Hard contract: ensure exactly the 5 signal columns exist — no exceptions
    for col in SIGNAL_COLUMNS:
        if col not in df.columns:
            df[col] = False if col == "_signal_flag" else (0.0 if col == "_signal_score" else "")

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_flag_count", int(df["_signal_flag"].sum()))


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_signal_calculator)
