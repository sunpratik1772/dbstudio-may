"""Port-level schema checks in :mod:`engine.dag_runner` (single runtime path)."""
from __future__ import annotations

import pandas as pd
import pytest

from engine.context import RunContext
from engine.dag_runner import check_input_port_schema, check_output_contract, execute_nodes
from engine.registry import get_spec


def test_decision_rule_input_ok_when_flag_present():
    assert get_spec("DECISION_RULE") is not None
    ctx = RunContext(alert_payload={})
    ctx.datasets["sig"] = pd.DataFrame({"_signal_flag": [True, False], "a": [1, 2]})
    node = {"type": "DECISION_RULE", "config": {"input_name": "sig"}}
    assert check_input_port_schema(node, ctx) == []


def test_decision_rule_input_skips_when_no_dataframe():
    assert get_spec("DECISION_RULE") is not None
    ctx = RunContext(alert_payload={})
    node = {"type": "DECISION_RULE", "config": {"input_name": "missing_ds"}}
    assert check_input_port_schema(node, ctx) == []


def test_decision_rule_input_fails_when_dataframe_missing_column():
    assert get_spec("DECISION_RULE") is not None
    ctx = RunContext(alert_payload={})
    ctx.datasets["sig"] = pd.DataFrame({"wrong": [1]})
    node = {"type": "DECISION_RULE", "config": {"input_name": "sig"}}
    issues = check_input_port_schema(node, ctx)
    assert len(issues) == 1
    assert "_signal_flag" in issues[0]


def test_execute_nodes_enforces_input_schema_before_handler():
    """Input port checks must be part of the production runner path, not
    merely a helper that tests call directly."""
    ctx = RunContext(alert_payload={})
    ctx.datasets["sig"] = pd.DataFrame({"wrong": [1]})
    nodes = [
        {
            "id": "n01",
            "type": "DECISION_RULE",
            "label": "Rule",
            "config": {"input_name": "sig"},
        }
    ]

    with pytest.raises(ValueError, match="input contract"):
        execute_nodes(nodes, [], ctx)


def test_signal_calculator_output_ok():
    assert get_spec("SIGNAL_CALCULATOR") is not None
    ctx = RunContext(alert_payload={})
    ctx.datasets["out"] = pd.DataFrame(
        {
            "_signal_flag": [False],
            "_signal_score": [0.0],
            "_signal_reason": [""],
            "_signal_type": ["X"],
            "_signal_window": ["1m"],
        }
    )
    node = {"type": "SIGNAL_CALCULATOR", "config": {"output_name": "out"}}
    assert check_output_contract(node, ctx) == []


def test_signal_calculator_output_fails_missing_signal_column():
    assert get_spec("SIGNAL_CALCULATOR") is not None
    ctx = RunContext(alert_payload={})
    ctx.datasets["out"] = pd.DataFrame({"_signal_flag": [False]})
    node = {"type": "SIGNAL_CALCULATOR", "config": {"output_name": "out"}}
    issues = check_output_contract(node, ctx)
    assert issues and "_signal_score" in issues[0]


def test_signal_scores_are_normalized_to_unit_interval():
    from engine.nodes.signal_calculator import _front_running, _layering, _spoofing, _wash_trade

    exec_df = pd.DataFrame({
        "exec_time": pd.date_range("2024-01-01", periods=3, freq="min"),
        "exec_price": [1.0, 2.0, 4.0],
        "side": ["BUY", "SELL", "BUY"],
        "exec_quantity": [100, 100, 100],
        "status": ["CANCELLED", "CANCELLED", "FILLED"],
        "order_type": ["LIMIT", "LIMIT", "MARKET"],
    })
    order_df = pd.DataFrame({
        "order_type": ["LIMIT"] * 10,
        "side": ["BUY"] * 10,
    })

    outputs = [
        _front_running(exec_df, {"price_move_threshold": 0.1}),
        _wash_trade(exec_df, {}),
        _spoofing(exec_df, {}),
        _layering(order_df, {"min_layers": 1}),
    ]
    for out in outputs:
        assert out["_signal_score"].between(0, 1).all()


def test_section_summary_object_output_ok():
    n = get_spec("SECTION_SUMMARY")
    assert n is not None
    sn = "analysis"
    ctx = RunContext(alert_payload={})
    ctx.sections[sn] = {
        "name": sn,
        "stats": {},
        "narrative": "x",
        "dataset": "execution_data",
    }
    node = {
        "type": "SECTION_SUMMARY",
        "config": {"section_name": sn, "input_name": "execution_data"},
    }
    assert check_output_contract(node, ctx) == []


def test_section_summary_object_output_missing_key():
    n = get_spec("SECTION_SUMMARY")
    assert n is not None
    sn = "analysis"
    ctx = RunContext(alert_payload={})
    ctx.sections[sn] = {"name": sn, "stats": {}}
    node = {
        "type": "SECTION_SUMMARY",
        "config": {"section_name": sn, "input_name": "execution_data"},
    }
    issues = check_output_contract(node, ctx)
    assert any("narrative" in s or "dataset" in s for s in issues)


def test_execution_collector_output_matches_hs_client_order():
    from engine.dag_runner import _output_dataframe_required_columns
    from engine.registry import get_spec

    sp = get_spec("EXECUTION_DATA_COLLECTOR")
    assert sp is not None
    p = [x for x in sp.output_ports if x.name == "executions"][0]
    node = {"type": "EXECUTION_DATA_COLLECTOR", "config": {"source": "hs_client_order"}}
    req = _output_dataframe_required_columns(p, sp, node)
    assert "order_id" in req and "trader_id" in req


def test_execution_collector_output_matches_hs_execution():
    from engine.dag_runner import _output_dataframe_required_columns
    from engine.registry import get_spec

    sp = get_spec("EXECUTION_DATA_COLLECTOR")
    assert sp is not None
    p = [x for x in sp.output_ports if x.name == "executions"][0]
    node = {"type": "EXECUTION_DATA_COLLECTOR", "config": {"source": "hs_execution"}}
    req = _output_dataframe_required_columns(p, sp, node)
    assert "exec_id" in req and "trade_version" in req


def test_alert_context_keys_object_materialised():
    from engine import registry

    h = registry.NODE_HANDLERS["ALERT_TRIGGER"]
    ctx = RunContext(
        alert_payload={"trader_id": "T1", "currency_pair": "EUR/USD"},
    )
    h({"type": "ALERT_TRIGGER", "config": {}}, ctx)
    node = {"type": "ALERT_TRIGGER", "config": {}}
    assert check_output_contract(node, ctx) == []
