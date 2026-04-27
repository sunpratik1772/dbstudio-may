"""
Tests for the HardRule registry.

Split into two layers:

1. Registry mechanics — register, iterate, isolate failing rules.
2. End-to-end regression — the two built-in rules
   (`trade_version_pin`, `signal_calculator_script_presence`) that
   used to live inline in validator.py must still fire identically.
"""
from __future__ import annotations

import pytest

from engine.hard_rules import (
    HardRule,
    _REGISTRY,
    all_hard_rules,
    register_hard_rule,
    run_hard_rules,
)
from engine.validation_codes import ValidationErrorCode
from engine.validator import ValidationResult, validate_dag


# ---------------------------------------------------------------------------
# Registry mechanics
# ---------------------------------------------------------------------------
def test_registry_holds_built_in_rules() -> None:
    """Importing the module must have registered at least the two
    rules that were in-lined before the refactor."""
    names = {r.name for r in all_hard_rules()}
    assert "trade_version_pin" in names
    assert "signal_calculator_script_presence" in names


def test_register_returns_original_callable() -> None:
    """The decorator must not wrap the function — tests need to
    exercise the raw check directly."""

    def _probe(node: dict, dag: dict, result) -> None:  # pragma: no cover
        pass

    wrapped = register_hard_rule(
        name="_probe_rule",
        code=ValidationErrorCode.UNKNOWN_TYPE,
        node_type="ALERT_TRIGGER",
    )(_probe)
    try:
        assert wrapped is _probe
    finally:
        # Clean up so the global registry doesn't leak between tests.
        _REGISTRY[:] = [r for r in _REGISTRY if r.name != "_probe_rule"]


def test_run_hard_rules_filters_by_node_type() -> None:
    """A rule registered with `node_type="X"` must not fire against
    nodes of other types."""
    calls: list[str] = []

    def _check(node: dict, dag: dict, result) -> None:
        calls.append(node["id"])

    register_hard_rule(
        name="_type_filter",
        code=ValidationErrorCode.UNKNOWN_TYPE,
        node_type="ALERT_TRIGGER",
    )(_check)
    try:
        nodes = {
            "n01": {"id": "n01", "type": "ALERT_TRIGGER"},
            "n02": {"id": "n02", "type": "SIGNAL_CALCULATOR"},
        }
        run_hard_rules(nodes, dag={"nodes": list(nodes.values())}, result=ValidationResult())
        assert calls == ["n01"]
    finally:
        _REGISTRY[:] = [r for r in _REGISTRY if r.name != "_type_filter"]


def test_crashing_rule_does_not_abort_others() -> None:
    """A rule that raises must NOT stop subsequent rules from running."""
    survived: list[str] = []

    def _crash(node: dict, dag: dict, result) -> None:
        raise RuntimeError("boom")

    def _survives(node: dict, dag: dict, result) -> None:
        survived.append(node["id"])

    register_hard_rule(
        name="_crasher",
        code=ValidationErrorCode.UNKNOWN_TYPE,
        node_type="ALERT_TRIGGER",
    )(_crash)
    register_hard_rule(
        name="_survivor",
        code=ValidationErrorCode.UNKNOWN_TYPE,
        node_type="ALERT_TRIGGER",
    )(_survives)
    try:
        nodes = {"n01": {"id": "n01", "type": "ALERT_TRIGGER"}}
        run_hard_rules(nodes, dag={"nodes": list(nodes.values())}, result=ValidationResult())
        assert survived == ["n01"]
    finally:
        _REGISTRY[:] = [r for r in _REGISTRY if r.name not in {"_crasher", "_survivor"}]


def test_rule_metadata_is_frozen() -> None:
    """`HardRule` is a frozen dataclass — registry consumers (docs,
    admin endpoints) can safely cache references."""
    rule = next(iter(all_hard_rules()))
    with pytest.raises(Exception):
        rule.name = "anything-else"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# End-to-end regression — the two built-in rules
# ---------------------------------------------------------------------------
def _minimal_workflow(extra_nodes: list[dict]) -> dict:
    """Build the smallest DAG that passes structural validation so we
    exercise hard rules and nothing else fails noisily."""
    nodes = [
        {"id": "n01", "type": "ALERT_TRIGGER", "label": "trigger"},
        *extra_nodes,
        {"id": "n99", "type": "REPORT_OUTPUT", "label": "report", "config": {"tabs": []}},
    ]
    edges = [{"from": "n01", "to": extra_nodes[0]["id"]}] if extra_nodes else []
    if extra_nodes:
        edges.append({"from": extra_nodes[-1]["id"], "to": "n99"})
    else:
        edges.append({"from": "n01", "to": "n99"})
    return {"schema_version": "1.0", "nodes": nodes, "edges": edges}


def test_trade_version_pin_fires_without_pin() -> None:
    dag = _minimal_workflow([{
        "id": "n02",
        "type": "EXECUTION_DATA_COLLECTOR",
        "label": "Executions",
        "config": {
            "source": "hs_execution",
            "query_template": "region:EMEA",
            "output_name": "execution_data",
        },
    }])
    result = validate_dag(dag)
    codes = [i.code for i in result.issues]
    assert ValidationErrorCode.MISSING_TRADE_VERSION in codes


def test_trade_version_pin_passes_with_pin() -> None:
    dag = _minimal_workflow([{
        "id": "n02",
        "type": "EXECUTION_DATA_COLLECTOR",
        "label": "Executions",
        "config": {
            "source": "hs_execution",
            "query_template": "trade_version:1 AND region:EMEA",
            "output_name": "execution_data",
        },
    }])
    result = validate_dag(dag)
    codes = [i.code for i in result.issues]
    assert ValidationErrorCode.MISSING_TRADE_VERSION not in codes


def test_signal_script_missing_both_fires_error() -> None:
    dag = _minimal_workflow([{
        "id": "n02",
        "type": "SIGNAL_CALCULATOR",
        "label": "signal",
        "config": {
            "mode": "upload_script",
            "input_name": "execution_data",
            "output_name": "signal",
        },
    }])
    result = validate_dag(dag)
    codes = [i.code for i in result.issues]
    assert ValidationErrorCode.MISSING_SCRIPT in codes
    assert ValidationErrorCode.UPLOAD_SCRIPT_DISABLED in codes


def test_signal_script_path_only_fires_warning() -> None:
    dag = _minimal_workflow([{
        "id": "n02",
        "type": "SIGNAL_CALCULATOR",
        "label": "signal",
        "config": {
            "mode": "upload_script",
            "script_path": "/tmp/foo.py",
            "input_name": "execution_data",
            "output_name": "signal",
        },
    }])
    result = validate_dag(dag)
    warnings = [i for i in result.issues if i.severity == "warning"]
    assert any(i.code == ValidationErrorCode.SCRIPT_PATH_ONLY for i in warnings)


def test_signal_script_disabled_by_default() -> None:
    dag = _minimal_workflow([{
        "id": "n02",
        "type": "SIGNAL_CALCULATOR",
        "label": "signal",
        "config": {
            "mode": "upload_script",
            "script_content": "df = df",
            "input_name": "execution_data",
            "output_name": "signal",
        },
    }])
    result = validate_dag(dag)
    disabled = [i for i in result.errors if i.code == ValidationErrorCode.UPLOAD_SCRIPT_DISABLED]
    assert len(disabled) == 1
