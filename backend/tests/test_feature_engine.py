"""Tests for the FEATURE_ENGINE node — one node, six ops."""
from __future__ import annotations

import pandas as pd
import pytest

from engine.context import RunContext
from engine.nodes.feature_engine import handle_feature_engine


def _ctx(df: pd.DataFrame, name: str = "src") -> RunContext:
    c = RunContext()
    c.datasets[name] = df
    return c


def _node(**cfg) -> dict:
    cfg.setdefault("input_name", "src")
    cfg.setdefault("output_name", "out")
    return {"id": "fe", "type": "FEATURE_ENGINE", "config": cfg}


def test_window_bucket_floors_to_interval():
    df = pd.DataFrame({"ts": ["2024-01-15T10:00:00Z", "2024-01-15T10:00:00.500Z", "2024-01-15T10:00:01Z"]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[{"op": "window_bucket", "time_col": "ts", "interval_ms": 1000, "out_col": "b"}]), ctx)
    out = ctx.datasets["out"]
    assert out["b"].nunique() == 2  # first two collapse, third is new bucket


def test_time_slice_labels_phases():
    df = pd.DataFrame({"ts": [
        "2024-01-15T09:00:00Z",
        "2024-01-15T10:15:00Z",
        "2024-01-15T11:00:00Z",
    ]})
    ctx = _ctx(df)
    ctx.set("fr_start", "2024-01-15T10:00:00Z")
    ctx.set("fr_end",   "2024-01-15T10:30:00Z")
    cfg = _node(ops=[{
        "op": "time_slice", "time_col": "ts", "out_col": "phase", "on_miss": "outside",
        "windows": [{"name": "during", "start": "{context.fr_start}", "end": "{context.fr_end}"}],
    }])
    handle_feature_engine(cfg, ctx)
    out = ctx.datasets["out"]
    assert out["phase"].tolist() == ["outside", "during", "outside"]


def test_groupby_agg():
    df = pd.DataFrame({"side": ["B", "B", "S"], "qty": [10, 20, 5]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "groupby_agg", "by": ["side"], "aggs": {"qty": "sum"}},
    ]), ctx)
    out = ctx.datasets["out"]
    assert dict(zip(out["side"], out["qty"])) == {"B": 30, "S": 5}


def test_pivot_creates_side_columns():
    df = pd.DataFrame({"bucket": [1, 1, 2, 2], "side": ["B", "S", "B", "S"], "qty": [10, 5, 20, 8]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "pivot", "index": "bucket", "columns": "side", "values": "qty"},
    ]), ctx)
    out = ctx.datasets["out"]
    assert set(out.columns) >= {"bucket", "B", "S"}
    assert out.set_index("bucket").loc[1, "B"] == 10


def test_rolling_window():
    df = pd.DataFrame({"px": [1.0, 2.0, 3.0, 4.0, 5.0]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "rolling", "col": "px", "window": 3, "agg": "mean", "out_col": "px_ma3"},
    ]), ctx)
    out = ctx.datasets["out"]
    assert out["px_ma3"].iloc[-1] == 4.0  # mean(3,4,5)


def test_derive_vectorised():
    df = pd.DataFrame({"qty": [10, 20], "px": [1.5, 2.5]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "derive", "out_col": "notional", "expr": "qty * px"},
    ]), ctx)
    out = ctx.datasets["out"]
    assert out["notional"].tolist() == [15.0, 50.0]


def test_apply_expr_branchy():
    df = pd.DataFrame({"qty": [10, 20], "side": ["B", "S"]})
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "apply_expr", "out_col": "signed", "expr": "qty * (1 if side == 'B' else -1)"},
    ]), ctx)
    out = ctx.datasets["out"]
    assert out["signed"].tolist() == [10, -20]


def test_chained_ops_with_publish_intermediate():
    """Bucket -> pivot, publishing pivot as a separate dataset."""
    df = pd.DataFrame({
        "ts":   ["2024-01-15T10:00:00Z", "2024-01-15T10:00:00.500Z", "2024-01-15T10:00:01Z", "2024-01-15T10:00:01.5Z"],
        "side": ["B", "S", "B", "S"],
        "qty":  [10, 5, 20, 8],
    })
    ctx = _ctx(df)
    handle_feature_engine(_node(ops=[
        {"op": "window_bucket", "time_col": "ts", "interval_ms": 1000, "out_col": "bucket"},
        {"op": "groupby_agg", "by": ["bucket", "side"], "aggs": {"qty": "sum"}, "as": "ladder_long"},
        {"op": "pivot", "index": "bucket", "columns": "side", "values": "qty"},
    ]), ctx)
    assert "ladder_long" in ctx.datasets       # intermediate published via `as`
    assert "out" in ctx.datasets               # final pivot
    pivot = ctx.datasets["out"]
    assert set(pivot.columns) >= {"bucket", "B", "S"}


def test_unknown_op_raises():
    ctx = _ctx(pd.DataFrame({"x": [1]}))
    with pytest.raises(ValueError, match="unknown op"):
        handle_feature_engine(_node(ops=[{"op": "frobnicate"}]), ctx)


def test_missing_input_raises():
    ctx = RunContext()
    with pytest.raises(ValueError, match="not found"):
        handle_feature_engine(_node(ops=[]), ctx)
