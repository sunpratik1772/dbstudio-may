"""
Phase 4 — SECTION_SUMMARY modes: templated (legacy), fact_pack_llm,
event_narrative.

The LLM seam is `engine.nodes.section_summary._llm_narrative`. Tests
monkeypatch it with a recorder so we can assert what reached the LLM
and what came back.
"""
from __future__ import annotations

import json

import pandas as pd

from engine.context import RunContext
from engine.nodes import section_summary as ss


def _install_llm(monkeypatch, responses, record: list[str]):
    """Patch the LLM seam with a scripted response list."""
    iterator = iter(responses)

    def fake(prompt: str) -> str:
        record.append(prompt)
        try:
            return next(iterator)
        except StopIteration:
            return responses[-1]

    monkeypatch.setattr(ss, "_llm_narrative", fake)


# ---------------------------------------------------------------------------
# Legacy "templated" mode still works (backwards compat)
# ---------------------------------------------------------------------------
def test_templated_mode_backwards_compat(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["narrative-A"], prompts)

    ctx = RunContext()
    ctx.datasets["trades"] = pd.DataFrame({
        "qty": [10, 20, 30],
        "side": ["BUY", "SELL", "BUY"],
    })
    ss.handle_section_summary({"config": {
        "section_name": "exec", "input_name": "trades",
        "field_bindings": [{"field": "qty", "agg": "sum"}],
        "llm_prompt_template": "Summarise {section}: {stats}",
    }}, ctx)

    assert ctx.sections["exec"]["narrative"] == "narrative-A"
    assert ctx.sections["exec"]["stats"]["qty"] == 60.0
    assert ctx.sections["exec"]["stats"]["row_count"] == 3
    assert "qty: 60.0" in prompts[0]


def test_templated_mode_supports_dotted_stats_aliases(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["narrative-B"], prompts)

    ctx = RunContext()
    ctx.datasets["orders"] = pd.DataFrame({
        "order_id": ["o1", "o2", "o3"],
        "quantity": [10, 20, 30],
        "side": ["BUY", "SELL", "BUY"],
    })
    ss.handle_section_summary({"config": {
        "section_name": "orders", "input_name": "orders",
        "field_bindings": [
            {"field": "order_id", "agg": "count"},
            {"field": "quantity", "agg": "sum"},
            {"field": "side", "agg": "nunique"},
        ],
        "llm_prompt_template": (
            "Total orders: {stats.order_id_count}. "
            "Total quantity: {stats.quantity_sum}. "
            "Sides: {stats.side_nunique}."
        ),
    }}, ctx)

    assert "Total orders: 3." in prompts[0]
    assert "Total quantity: 60.0." in prompts[0]
    assert "Sides: 2." in prompts[0]
    assert ctx.sections["orders"]["stats"]["order_id_count"] == 3
    assert ctx.sections["orders"]["stats"]["quantity_sum"] == 60.0


# ---------------------------------------------------------------------------
# fact_pack_llm mode
# ---------------------------------------------------------------------------
def _fro_like_df():
    return pd.DataFrame({
        "side": ["BUY", "BUY", "SELL", "BUY"],
        "quantity": [1_000_000, 2_000_000, 1_500_000, 500_000],
        "status": ["FILLED", "FILLED", "CANCELLED", "FILLED"],
    })


def test_fact_pack_computes_named_facts_and_injects_json(monkeypatch):
    prompts: list[str] = []
    _install_llm(
        monkeypatch,
        ["The trader placed 3 buys and 1 sell totalling 5000000."],
        prompts,
    )

    ctx = RunContext()
    ctx.datasets["trades"] = _fro_like_df()
    ss.handle_section_summary({"config": {
        "section_name": "exec", "input_name": "trades",
        "mode": "fact_pack_llm",
        "facts": [
            {"name": "buy_count", "column": "side", "agg": "count_where_buy"},
            {"name": "sell_count", "column": "side", "agg": "count_where_sell"},
            {"name": "total_qty", "column": "quantity", "agg": "sum"},
            {"name": "distinct_statuses", "column": "status", "agg": "nunique"},
        ],
        "llm_prompt_template": "Write a section narrative.\nFacts: {facts}",
    }}, ctx)

    assert len(prompts) == 1
    payload = prompts[0]
    # Facts arrive as JSON in the prompt
    assert '"buy_count": 3' in payload
    assert '"sell_count": 1' in payload
    assert '"total_qty": 5000000' in payload
    assert '"distinct_statuses": 2' in payload

    # Stats persist on the section record
    stats = ctx.sections["exec"]["stats"]
    assert stats["buy_count"] == 3
    assert stats["sell_count"] == 1
    assert stats["total_qty"] == 5_000_000.0
    assert stats["row_count"] == 4


def test_fact_pack_retries_when_required_fact_missing(monkeypatch):
    prompts: list[str] = []
    # First response omits buy_count=3; second includes it.
    _install_llm(monkeypatch, [
        "The trader executed aggressively across the window.",
        "Three buys happened in the window — buy_count=3, total=5000000.",
    ], prompts)

    ctx = RunContext()
    ctx.datasets["trades"] = _fro_like_df()
    ss.handle_section_summary({"config": {
        "section_name": "exec", "input_name": "trades",
        "mode": "fact_pack_llm",
        "facts": [
            {"name": "buy_count", "column": "side", "agg": "count_where_buy"},
            {"name": "total_qty", "column": "quantity", "agg": "sum"},
        ],
        "required_facts": ["buy_count"],
        "llm_prompt_template": "Write a narrative with these facts: {facts}",
    }}, ctx)

    assert len(prompts) == 2  # retry kicked in
    assert "previous response omitted" in prompts[1]
    assert "buy_count" in prompts[1]
    assert "3" in ctx.sections["exec"]["narrative"]


def test_fact_pack_no_retry_when_all_required_present(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, [
        "Trader placed 3 buys (buy_count=3) yielding total_qty=5000000.",
    ], prompts)

    ctx = RunContext()
    ctx.datasets["trades"] = _fro_like_df()
    ss.handle_section_summary({"config": {
        "section_name": "exec", "input_name": "trades",
        "mode": "fact_pack_llm",
        "facts": [
            {"name": "buy_count", "column": "side", "agg": "count_where_buy"},
            {"name": "total_qty", "column": "quantity", "agg": "sum"},
        ],
        "required_facts": ["buy_count", "total_qty"],
        "llm_prompt_template": "Use these facts: {facts}",
    }}, ctx)

    assert len(prompts) == 1


def test_fact_pack_unique_values_and_row_count(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["ok"], prompts)
    ctx = RunContext()
    ctx.datasets["trades"] = _fro_like_df()
    ss.handle_section_summary({"config": {
        "section_name": "exec", "input_name": "trades",
        "mode": "fact_pack_llm",
        "facts": [
            {"name": "sides_used", "column": "side", "agg": "unique_values"},
            {"name": "n_rows", "column": "side", "agg": "row_count"},
        ],
        "llm_prompt_template": "{facts}",
    }}, ctx)
    stats = ctx.sections["exec"]["stats"]
    assert sorted(stats["sides_used"]) == ["BUY", "SELL"]
    assert stats["n_rows"] == 4


# ---------------------------------------------------------------------------
# event_narrative mode
# ---------------------------------------------------------------------------
def test_event_narrative_sorts_and_formats_events(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["chronological story"], prompts)

    ctx = RunContext()
    ctx.datasets["orders"] = pd.DataFrame({
        "timestamp": ["2024-01-15 09:05", "2024-01-15 09:02", "2024-01-15 09:10"],
        "side": ["BUY", "SELL", "BUY"],
        "quantity": [1_000_000, 500_000, 2_000_000],
    })
    ss.handle_section_summary({"config": {
        "section_name": "orders_story", "input_name": "orders",
        "mode": "event_narrative",
        "sort_by": "timestamp",
        "event_template": "{timestamp} {side} {quantity}",
        "max_events": 10,
        "llm_prompt_template": "Stitch these events:\n{events}",
    }}, ctx)

    payload = prompts[0]
    # Sorted chronologically: 09:02 first
    lines = [ln for ln in payload.splitlines() if "•" in ln]
    assert "09:02" in lines[0]
    assert "09:05" in lines[1]
    assert "09:10" in lines[2]
    assert ctx.sections["orders_story"]["stats"]["event_count"] == 3
    assert ctx.sections["orders_story"]["narrative"] == "chronological story"


def test_event_narrative_caps_at_max_events(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["ok"], prompts)

    ctx = RunContext()
    ctx.datasets["orders"] = pd.DataFrame({
        "ts": list(range(20)),
        "x": list(range(20)),
    })
    ss.handle_section_summary({"config": {
        "section_name": "s", "input_name": "orders",
        "mode": "event_narrative",
        "sort_by": "ts",
        "event_template": "{ts}:{x}",
        "max_events": 5,
        "llm_prompt_template": "{events}",
    }}, ctx)

    assert ctx.sections["s"]["stats"]["event_count"] == 5
    payload = prompts[0]
    assert "0:0" in payload and "4:4" in payload
    assert "5:5" not in payload


def test_event_narrative_empty_dataset(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["no events"], prompts)
    ctx = RunContext()
    ctx.datasets["empty"] = pd.DataFrame({"ts": [], "x": []})
    ss.handle_section_summary({"config": {
        "section_name": "s", "input_name": "empty",
        "mode": "event_narrative",
        "sort_by": "ts",
        "event_template": "{ts}:{x}",
        "llm_prompt_template": "{events}",
    }}, ctx)
    assert ctx.sections["s"]["stats"]["event_count"] == 0
    assert ctx.sections["s"]["stats"]["row_count"] == 0


# ---------------------------------------------------------------------------
# Mode dispatch — unknown mode falls back to templated
# ---------------------------------------------------------------------------
def test_unknown_mode_falls_back_to_templated(monkeypatch):
    prompts: list[str] = []
    _install_llm(monkeypatch, ["ok"], prompts)
    ctx = RunContext()
    ctx.datasets["d"] = pd.DataFrame({"x": [1, 2]})
    ss.handle_section_summary({"config": {
        "section_name": "s", "input_name": "d",
        "mode": "bogus",
        "llm_prompt_template": "{stats}",
    }}, ctx)
    assert ctx.sections["s"]["stats"]["row_count"] == 2
