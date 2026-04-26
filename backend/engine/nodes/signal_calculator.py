from pathlib import Path
import os

import numpy as np
import pandas as pd

from ..column_guards import require_columns
from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..signal_contract import (
    get_signal_output_columns,
    signal_flag_column_name,
    signal_score_column_name,
)


# ── built-in signal implementations ──────────────────────────────────────────

def _front_running(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    window_min = params.get("window_minutes", 5)
    threshold = params.get("price_move_threshold", 0.0003)

    df = df.copy()
    df["exec_time"] = pd.to_datetime(df["exec_time"])
    df = df.sort_values("exec_time").reset_index(drop=True)
    df["_price_move"] = df["exec_price"].diff().abs().fillna(0)
    df["_signal_flag"] = df["_price_move"] > threshold
    df["_signal_score"] = (df["_price_move"] / threshold).clip(0, 1).round(2)
    df["_signal_reason"] = df.apply(
        lambda r: f"Price moved {r['_price_move']:.5f} (>{threshold}) within {window_min}m"
        if r["_signal_flag"] else "",
        axis=1,
    )
    df = df.drop(columns=["_price_move"])

    df["_signal_type"] = "FRONT_RUNNING"
    df["_signal_window"] = f"{window_min}m"
    return df


def _wash_trade(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    window_min = params.get("window_minutes", 10)
    threshold = params.get("ratio_threshold", 0.8)
    qty_col = "exec_quantity" if "exec_quantity" in df.columns else "quantity"
    if qty_col not in df.columns:
        raise ValueError(
            "SIGNAL_CALCULATOR(WASH_TRADE): need exec_quantity or quantity column. "
            f"Got: {list(df.columns)}"
        )

    df = df.copy()
    buy_qty = df.loc[df["side"] == "BUY", qty_col].sum()
    sell_qty = df.loc[df["side"] == "SELL", qty_col].sum()
    denom = max(buy_qty, sell_qty, 1)
    ratio = min(buy_qty, sell_qty) / denom
    flag = ratio > threshold
    df["_signal_flag"] = flag
    df["_signal_score"] = round(ratio, 2)
    df["_signal_reason"] = f"Buy/Sell qty ratio {ratio:.2%} exceeds {threshold:.0%}" if flag else ""

    df["_signal_type"] = "WASH_TRADE"
    df["_signal_window"] = f"{window_min}m"
    return df


def _spoofing(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = params.get("cancel_ratio_threshold", 0.7)

    df = df.copy()
    total = len(df)
    cancelled = (df["status"] == "CANCELLED").sum()
    ratio = cancelled / total if total else 0
    flag = ratio > threshold
    df["_signal_flag"] = flag
    df["_signal_score"] = round(ratio, 2)
    df["_signal_reason"] = f"Cancel ratio {ratio:.2%} exceeds {threshold:.0%}" if flag else ""

    df["_signal_type"] = "SPOOFING"
    df["_signal_window"] = params.get("window", "1d")
    return df


def _layering(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    min_layers = params.get("min_layers", 5)

    df = df.copy()
    buy_limits = ((df["order_type"] == "LIMIT") & (df["side"] == "BUY")).sum()
    sell_limits = ((df["order_type"] == "LIMIT") & (df["side"] == "SELL")).sum()
    imbalance = int(abs(buy_limits - sell_limits))
    flag = imbalance >= min_layers
    df["_signal_flag"] = flag
    df["_signal_score"] = min(round(imbalance / min_layers, 2), 1)
    df["_signal_reason"] = f"Limit order imbalance: {imbalance} orders on one side" if flag else ""

    df["_signal_type"] = "LAYERING"
    df["_signal_window"] = params.get("window", "30m")
    return df


BUILT_IN = {
    "FRONT_RUNNING": _front_running,
    "WASH_TRADE": _wash_trade,
    "SPOOFING": _spoofing,
    "LAYERING": _layering,
}


def _built_in_required_columns(signal_type: str) -> tuple[str, ...]:
    from ..registry import get_spec

    m = (get_spec("SIGNAL_CALCULATOR").contract or {}).get("built_in_required_columns") or {}
    raw = m.get(signal_type)
    if not raw:
        return tuple()
    return tuple(str(x) for x in raw)


# ── handler ───────────────────────────────────────────────────────────────────

def handle_signal_calculator(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    mode: str = cfg.get("mode", "configure")
    input_name: str = cfg.get("input_name", "execution_data")
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
        if signal_type == "WASH_TRADE":
            needw = _built_in_required_columns("WASH_TRADE")
            if needw:
                require_columns(
                    df, list(needw), context="SIGNAL_CALCULATOR(WASH_TRADE)"
                )
            if "exec_quantity" not in df.columns and "quantity" not in df.columns:
                raise ValueError(
                    "SIGNAL_CALCULATOR(WASH_TRADE): missing both exec_quantity and quantity. "
                    f"DataFrame has: {list(df.columns)}"
                )
        else:
            need = _built_in_required_columns(signal_type)
            if need:
                require_columns(
                    df,
                    list(need),
                    context=f"SIGNAL_CALCULATOR({signal_type})",
                )
        df = fn(df, params)

    elif mode == "upload_script":
        if os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() not in {"1", "true", "yes"}:
            raise PermissionError(
                "SIGNAL_CALCULATOR upload_script mode is disabled. "
                "Set DBSHERPA_ALLOW_UPLOAD_SCRIPT=true to enable it."
            )
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

    # Hard contract: ensure exact signal columns from node YAML
    flag_col = signal_flag_column_name()
    score_col = signal_score_column_name()
    for col in get_signal_output_columns():
        if col not in df.columns:
            if col == flag_col:
                df[col] = False
            elif col == score_col:
                df[col] = 0.0
            else:
                df[col] = ""

    ctx.datasets[output_name] = df
    prov = ctx.dataset_provenance.get(input_name)
    if prov:
        ctx.dataset_provenance[output_name] = prov
    ctx.set(f"{output_name}_flag_count", int(df[flag_col].sum()))


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_signal_calculator)
