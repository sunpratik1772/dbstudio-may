"""Tests for engine/refs.py — the cross-dataset reference resolver."""
from __future__ import annotations

import pandas as pd
import pytest

from engine.context import RunContext
from engine.refs import ResolveError, resolve_ref, resolve_template, resolve_vars
from engine.prompt_context import build_dataset_block


@pytest.fixture
def ctx() -> RunContext:
    c = RunContext()
    c.datasets["executions"] = pd.DataFrame({
        "notional": [100.0, 200.0, 300.0],
        "side":     ["B", "S", "B"],
        "_signal_flag": [0, 1, 1],
    })
    c.datasets["empty"] = pd.DataFrame(columns=["x"])
    c.set("disposition", "ESCALATE")
    c.set("alert", {"trader_id": "T1", "book": "FX-SPOT"})
    return c


def test_resolve_dataset(ctx):
    df = resolve_ref("executions", ctx)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3


def test_resolve_column_series(ctx):
    s = resolve_ref("executions.notional", ctx)
    assert isinstance(s, pd.Series)
    assert s.tolist() == [100.0, 200.0, 300.0]


def test_resolve_aggs(ctx):
    assert resolve_ref("executions.notional.sum", ctx) == 600.0
    assert resolve_ref("executions.notional.mean", ctx) == 200.0
    assert resolve_ref("executions.notional.max", ctx) == 300.0
    assert resolve_ref("executions.notional.min", ctx) == 100.0
    assert resolve_ref("executions.notional.count", ctx) == 3
    assert resolve_ref("executions.side.nunique", ctx) == 2
    assert resolve_ref("executions._signal_flag.sum", ctx) == 2.0
    assert resolve_ref("executions._signal_flag.any", ctx) is True


def test_resolve_row_count(ctx):
    assert resolve_ref("executions.@row_count", ctx) == 3
    assert resolve_ref("empty.@row_count", ctx) == 0


def test_resolve_ctx_simple(ctx):
    assert resolve_ref("context.disposition", ctx) == "ESCALATE"


def test_resolve_ctx_nested_dict(ctx):
    assert resolve_ref("context.alert.trader_id", ctx) == "T1"


def test_unknown_dataset_raises(ctx):
    with pytest.raises(ResolveError):
        resolve_ref("nope", ctx)


def test_unknown_column_raises(ctx):
    with pytest.raises(ResolveError):
        resolve_ref("executions.missing_col", ctx)


def test_unknown_agg_raises(ctx):
    with pytest.raises(ResolveError):
        resolve_ref("executions.notional.median", ctx)


def test_template_substitutes(ctx):
    out = resolve_template("Total: {executions.notional.sum} ({executions.@row_count} rows)", ctx)
    assert out == "Total: 600.0 (3 rows)"


def test_template_leaves_unresolvable_in_place(ctx):
    out = resolve_template("Known {context.disposition}, unknown {nope.col}", ctx)
    assert out == "Known ESCALATE, unknown {nope.col}"


def test_resolve_vars_native_types(ctx):
    vars_ = resolve_vars({
        "total":     "{executions.notional.sum}",
        "rows":      "{executions.@row_count}",
        "literal":   42,
        "narrative": "Total is {executions.notional.sum} across {executions.@row_count} rows",
    }, ctx)
    assert vars_["total"] == 600.0
    assert vars_["rows"] == 3
    assert vars_["literal"] == 42
    assert vars_["narrative"] == "Total is 600.0 across 3 rows"


def test_markdown_dataset_block_falls_back_without_tabulate(monkeypatch):
    df = pd.DataFrame({"a": [1], "b": ["x"]})

    def fail_to_markdown(*args, **kwargs):
        raise ImportError("Missing optional dependency 'tabulate'")

    monkeypatch.setattr(pd.DataFrame, "to_markdown", fail_to_markdown)

    out = build_dataset_block(df, fmt="markdown")

    assert out == "a,b\n1,x\n"
