"""Cross-dataset / context refs in DATA_HIGHLIGHTER conditions."""
from __future__ import annotations

import pandas as pd

from engine.context import RunContext
from engine.nodes.data_highlighter import handle_data_highlighter


def test_highlight_uses_context_threshold():
    ctx = RunContext()
    ctx.datasets["execs"] = pd.DataFrame({"notional": [10, 100, 500, 1000]})
    ctx.set("peak_threshold", 200)
    cfg = {"id": "h", "type": "DATA_HIGHLIGHTER", "config": {
        "input_name": "execs",
        "output_name": "execs_hl",
        "rules": [{"condition": "notional > {context.peak_threshold}", "colour": "#FF0000", "label": "PEAK"}],
    }}
    handle_data_highlighter(cfg, ctx)
    out = ctx.datasets["execs_hl"]
    assert out["_highlight_label"].tolist() == ["", "", "PEAK", "PEAK"]


def test_highlight_uses_cross_dataset_scalar():
    ctx = RunContext()
    ctx.datasets["execs"] = pd.DataFrame({"bucket": [1, 2, 3, 4], "qty": [10, 20, 30, 40]})
    ctx.datasets["ladder"] = pd.DataFrame({"bucket": [1, 2, 3, 4], "qty": [50, 80, 30, 200]})
    cfg = {"id": "h", "type": "DATA_HIGHLIGHTER", "config": {
        "input_name": "execs",
        "output_name": "execs_hl",
        "rules": [{"condition": "qty >= {ladder.qty.max}", "colour": "#FF0000", "label": "TOP"}],
    }}
    handle_data_highlighter(cfg, ctx)
    out = ctx.datasets["execs_hl"]
    # ladder.qty.max == 200; only execs.qty >= 200 highlights — none in this data
    assert out["_highlight_label"].tolist() == ["", "", "", ""]


def test_unresolved_ref_skips_rule_no_crash():
    ctx = RunContext()
    ctx.datasets["execs"] = pd.DataFrame({"qty": [1, 2, 3]})
    cfg = {"id": "h", "type": "DATA_HIGHLIGHTER", "config": {
        "input_name": "execs",
        "output_name": "execs_hl",
        "rules": [
            {"condition": "qty > {missing.col.sum}", "colour": "#FF0000", "label": "BROKEN"},
            {"condition": "qty > 1", "colour": "#00FF00", "label": "OK"},
        ],
    }}
    handle_data_highlighter(cfg, ctx)
    out = ctx.datasets["execs_hl"]
    # Broken rule skipped; second rule applies
    assert out["_highlight_label"].tolist() == ["", "OK", "OK"]
