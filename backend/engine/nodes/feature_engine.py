"""
FEATURE_ENGINE — one node, many ops. Replaces the urge to add a new
node every time a scenario needs to bucket time, pivot a side, or
derive a column.

Config:

    {
      "input_name":  "executions",
      "output_name": "executions_features",
      "ops": [
        { "op": "window_bucket", "time_col": "ts", "interval_ms": 1000, "out_col": "bucket" },
        { "op": "time_slice",   "time_col": "ts",
          "windows": [{name: "before", start: "{context.fr_start}", end: "{context.fr_end}", on_miss: "outside"}],
          "out_col": "phase" },
        { "op": "groupby_agg", "by": ["bucket","side"], "aggs": {"qty":"sum","px":"mean"}, "as": "ladder" },
        { "op": "pivot",       "index": "bucket", "columns": "side", "values": "qty", "as": "ladder_pivot" },
        { "op": "rolling",     "window": 5, "col": "px", "agg": "mean", "out_col": "px_ma5" },
        { "op": "derive",      "out_col": "signed_qty", "expr": "qty * (1 if side=='B' else -1)" }
      ]
    }

Ops mutate the working DataFrame in place by default; specifying `as`
publishes the result of that op as a new dataset (so a single
FEATURE_ENGINE run can emit the ladder pivot AND keep the raw rows).

The final working DataFrame is published to ctx.datasets[output_name].
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..refs import resolve_template


# ---------------------------------------------------------------------------
# Op registry — one function per op. Each takes (df, op_cfg, ctx) and
# returns (new_df, optional_published_pair). Adding an op = adding one
# entry. NOT a generic expression engine — only ship ops with a real
# scenario justifying them.
# ---------------------------------------------------------------------------
def _op_window_bucket(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    time_col = cfg["time_col"]
    interval_ms = int(cfg["interval_ms"])
    out_col = cfg.get("out_col", "bucket")
    series = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    df = df.copy()
    df[out_col] = (series.astype("int64") // (interval_ms * 1_000_000)).astype("int64")
    return df


def _op_time_slice(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    time_col = cfg["time_col"]
    out_col = cfg.get("out_col", "phase")
    on_miss = cfg.get("on_miss", "outside")
    windows = cfg.get("windows") or []
    df = df.copy()
    series = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    df[out_col] = on_miss
    for w in windows:
        name = w["name"]
        start = pd.Timestamp(resolve_template(str(w["start"]), ctx), tz="UTC") if w.get("start") else None
        end = pd.Timestamp(resolve_template(str(w["end"]), ctx), tz="UTC") if w.get("end") else None
        mask = pd.Series(True, index=df.index)
        if start is not None:
            mask &= series >= start
        if end is not None:
            mask &= series <= end
        df.loc[mask, out_col] = name
    return df


def _op_groupby_agg(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    by = cfg["by"] if isinstance(cfg["by"], list) else [cfg["by"]]
    aggs = cfg.get("aggs") or {}
    grouped = df.groupby(by, dropna=False).agg(aggs).reset_index()
    return grouped


def _op_pivot(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    index = cfg["index"]
    columns = cfg["columns"]
    values = cfg["values"]
    aggfunc = cfg.get("aggfunc", "sum")
    pivot = df.pivot_table(index=index, columns=columns, values=values, aggfunc=aggfunc, fill_value=0)
    pivot.columns = [str(c) for c in pivot.columns]
    return pivot.reset_index()


def _op_rolling(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    window = int(cfg["window"])
    col = cfg["col"]
    agg = cfg.get("agg", "mean")
    out_col = cfg.get("out_col", f"{col}_roll{window}_{agg}")
    df = df.copy()
    rolling = df[col].rolling(window=window, min_periods=1)
    df[out_col] = getattr(rolling, agg)()
    return df


def _op_derive(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    """Single-column derivation via DataFrame.eval (safe vectorised
    expression). For per-row Python expressions, use `apply_expr`."""
    out_col = cfg["out_col"]
    expr = cfg["expr"]
    df = df.copy()
    df[out_col] = df.eval(expr)
    return df


def _op_apply_expr(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    """Per-row Python expression evaluated with the row dict as locals.
    Use sparingly (slower than `derive`). Useful for branchy logic like
    `qty * (1 if side=='B' else -1)`."""
    out_col = cfg["out_col"]
    expr = cfg["expr"]
    df = df.copy()
    df[out_col] = df.apply(lambda row: eval(expr, {"__builtins__": {}}, row.to_dict()), axis=1)  # noqa: S307
    return df


def _op_rename(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    """Rename columns: cfg `mapping: {old_name: new_name}`. Missing
    source columns are silently ignored — pandas behaviour."""
    mapping = cfg.get("mapping") or {}
    return df.rename(columns=mapping)


def _op_lifecycle_event(df: pd.DataFrame, cfg: dict, ctx: RunContext) -> pd.DataFrame:
    """Tag each row with the status transition (`PLACED → FILLED`)
    that produced it, by grouping rows by `group_by` (e.g. order_id),
    sorting by `sort_by` (e.g. order_time), and diffing `status_col`
    within each group. Useful for surveillance lifecycle narratives.
    """
    group_by = cfg["group_by"]
    sort_by = cfg.get("sort_by")
    status_col = cfg.get("status_col", "status")
    out_col = cfg.get("out_col", "_lifecycle_event")
    df = df.copy()
    sort_cols = [group_by] + ([sort_by] if sort_by and sort_by in df.columns else [])
    df = df.sort_values(sort_cols)
    prev = df.groupby(group_by)[status_col].shift(1)
    df[out_col] = [
        f"{p} → {c}" if pd.notna(p) and p != c else ""
        for p, c in zip(prev, df[status_col])
    ]
    return df


_OPS: dict[str, Callable[..., pd.DataFrame]] = {
    "window_bucket":    _op_window_bucket,
    "time_slice":       _op_time_slice,
    "groupby_agg":      _op_groupby_agg,
    "pivot":            _op_pivot,
    "rolling":          _op_rolling,
    "derive":           _op_derive,
    "apply_expr":       _op_apply_expr,
    "rename":           _op_rename,
    "lifecycle_event":  _op_lifecycle_event,
}


def handle_feature_engine(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name") or ""
    output_name: str = cfg.get("output_name") or input_name
    ops: list[dict] = cfg.get("ops") or []

    src = ctx.datasets.get(input_name)
    if src is None:
        raise ValueError(f"FEATURE_ENGINE: input dataset '{input_name}' not found")

    df = src
    for op_cfg in ops:
        op_name = op_cfg.get("op")
        if op_name not in _OPS:
            raise ValueError(f"FEATURE_ENGINE: unknown op '{op_name}'")
        result = _OPS[op_name](df, op_cfg, ctx)
        publish_as = op_cfg.get("as")
        if publish_as:
            ctx.datasets[publish_as] = result
        else:
            df = result

    ctx.datasets[output_name] = df


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_feature_engine)
