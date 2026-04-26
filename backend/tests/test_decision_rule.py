"""Tests for the extended DECISION_RULE node (threshold + rule modes)."""
from __future__ import annotations

import pandas as pd
import pytest

from engine.context import RunContext
from engine.nodes.decision_rule import handle_decision_rule


def _ctx_with_signals(flag_count: int = 0) -> RunContext:
    c = RunContext()
    c.datasets["signals"] = pd.DataFrame({
        "_signal_flag": [1] * flag_count + [0] * 5,
        "score":        [0.9] * flag_count + [0.1] * 5,
    })
    return c


def _node(**cfg) -> dict:
    cfg.setdefault("input_name", "signals")
    return {"id": "d1", "type": "DECISION_RULE", "config": cfg}


# Threshold mode -------------------------------------------------------

def test_threshold_escalate():
    ctx = _ctx_with_signals(flag_count=6)
    handle_decision_rule(_node(escalate_threshold=5, review_threshold=1), ctx)
    assert ctx.disposition == "ESCALATE"
    assert ctx.get("severity") == "HIGH"
    assert ctx.get("flag_count") == 6
    assert ctx.get("score") == 1.0


def test_threshold_review():
    ctx = _ctx_with_signals(flag_count=2)
    handle_decision_rule(_node(escalate_threshold=5, review_threshold=1), ctx)
    assert ctx.disposition == "REVIEW"
    assert ctx.get("severity") == "MEDIUM"
    assert ctx.get("score") == 0.4


def test_threshold_dismiss():
    ctx = _ctx_with_signals(flag_count=0)
    handle_decision_rule(_node(escalate_threshold=5, review_threshold=1), ctx)
    assert ctx.disposition == "DISMISS"
    assert ctx.get("severity") == "LOW"
    assert ctx.get("score") == 0.0


# Rule mode ------------------------------------------------------------

def test_rule_mode_first_match_wins():
    ctx = _ctx_with_signals(flag_count=8)
    cfg = _node(
        rules=[
            {"name": "critical_burst", "when": "{signals._signal_flag.sum} >= 10", "severity": "CRITICAL", "disposition": "ESCALATE"},
            {"name": "spike",          "when": "{signals._signal_flag.sum} >= 5",  "severity": "HIGH",     "disposition": "ESCALATE"},
        ],
    )
    handle_decision_rule(cfg, ctx)
    assert ctx.get("matched_rule") == "spike"
    assert ctx.get("severity") == "HIGH"


def test_rule_mode_critical_branch():
    ctx = _ctx_with_signals(flag_count=12)
    cfg = _node(
        rules=[
            {"name": "critical_burst", "when": "{signals._signal_flag.sum} >= 10", "severity": "CRITICAL", "disposition": "ESCALATE"},
        ],
    )
    handle_decision_rule(cfg, ctx)
    assert ctx.get("matched_rule") == "critical_burst"
    assert ctx.get("severity") == "CRITICAL"
    assert ctx.disposition == "ESCALATE"


def test_rule_mode_no_match_falls_back_to_thresholds():
    ctx = _ctx_with_signals(flag_count=2)
    cfg = _node(
        escalate_threshold=5, review_threshold=1,
        rules=[{"name": "burst", "when": "{signals._signal_flag.sum} >= 10", "severity": "CRITICAL"}],
    )
    handle_decision_rule(cfg, ctx)
    assert ctx.get("matched_rule") == ""
    assert ctx.disposition == "REVIEW"
    assert ctx.get("severity") == "MEDIUM"


def test_rule_mode_truthy_bare_ref():
    ctx = _ctx_with_signals(flag_count=3)
    cfg = _node(
        rules=[{"name": "any_signal", "when": "{signals._signal_flag.any}", "severity": "HIGH", "disposition": "REVIEW"}],
    )
    handle_decision_rule(cfg, ctx)
    assert ctx.get("matched_rule") == "any_signal"
    assert ctx.disposition == "REVIEW"


def test_severity_map_override():
    ctx = _ctx_with_signals(flag_count=6)
    handle_decision_rule(_node(escalate_threshold=5, severity_map={"ESCALATE": "CRITICAL"}), ctx)
    assert ctx.get("severity") == "CRITICAL"


def test_output_branches():
    ctx = _ctx_with_signals(flag_count=6)
    handle_decision_rule(_node(escalate_threshold=5, output_branches={"ESCALATE": "soc_pager"}), ctx)
    assert ctx.output_branch == "soc_pager"
