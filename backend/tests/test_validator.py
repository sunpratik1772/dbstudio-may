"""
Validator tests — exercise the major error codes and the new
schema_version gate. These are deterministic and do not call the LLM.
"""
from __future__ import annotations

from engine.validator import validate_dag


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _alert_only(**extra) -> dict:
    """A single-node valid workflow stub."""
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "n01",
                "type": "ALERT_TRIGGER",
                "label": "Alert",
                "config": {"alert_fields": {"trader_id": "string"}},
            }
        ],
        "edges": [],
        **extra,
    }


# ---------------------------------------------------------------------------
# schema_version gate
# ---------------------------------------------------------------------------
class TestSchemaVersion:
    def test_current_version_passes(self):
        assert validate_dag(_alert_only()).valid

    def test_legacy_file_without_version_defaults_ok(self):
        dag = _alert_only()
        dag.pop("schema_version")
        assert validate_dag(dag).valid

    def test_future_version_blocked(self):
        dag = _alert_only()
        dag["schema_version"] = "99.0"
        result = validate_dag(dag)
        assert not result.valid
        assert any(i.code == "SCHEMA_TOO_NEW" for i in result.errors)

    def test_garbage_version_blocked(self):
        dag = _alert_only()
        dag["schema_version"] = "not-a-version"
        result = validate_dag(dag)
        assert not result.valid
        assert any(i.code == "BAD_SCHEMA_VERSION" for i in result.errors)


# ---------------------------------------------------------------------------
# structural checks
# ---------------------------------------------------------------------------
class TestStructural:
    def test_missing_nodes(self):
        result = validate_dag({"schema_version": "1.0"})
        assert not result.valid
        assert any(i.code == "MISSING_NODES" for i in result.errors)

    def test_empty_nodes(self):
        result = validate_dag({"schema_version": "1.0", "nodes": []})
        assert any(i.code == "EMPTY_WORKFLOW" for i in result.errors)

    def test_unknown_type(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [{"id": "n01", "type": "DOES_NOT_EXIST", "label": "x", "config": {}}],
            }
        )
        assert not result.valid
        assert any(i.code == "UNKNOWN_TYPE" for i in result.errors)

    def test_missing_label_is_warning(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [{"id": "n01", "type": "ALERT_TRIGGER", "config": {}}],
            }
        )
        # Missing label shouldn't block execution.
        assert any(i.code == "MISSING_LABEL" and i.severity == "warning" for i in result.issues)


# ---------------------------------------------------------------------------
# parameter validation
# ---------------------------------------------------------------------------
class TestParams:
    def test_missing_required_param(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "TRADE_DATA_COLLECTOR",
                        "label": "Trades",
                        # 'query_template' and 'output_name' are required; omit query_template.
                        "config": {"source": "hs_client_order", "output_name": "trades"},
                    },
                ],
                "edges": [{"from": "n01", "to": "n02"}],
            }
        )
        assert not result.valid
        assert any(
            i.code == "MISSING_REQUIRED_PARAM" and i.node_id == "n02" for i in result.errors
        )

    def test_enum_value_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "TRADE_DATA_COLLECTOR",
                        "label": "Trades",
                        "config": {
                            "source": "not_a_real_source",
                            "query_template": "*:*",
                            "output_name": "trades",
                        },
                    },
                ],
                "edges": [{"from": "n01", "to": "n02"}],
            }
        )
        assert not result.valid
        codes = {i.code for i in result.errors}
        assert "BAD_ENUM_VALUE" in codes or "BAD_PARAM_TYPE" in codes


# ---------------------------------------------------------------------------
# cycle detection
# ---------------------------------------------------------------------------
class TestAcyclicity:
    def test_cycle_is_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "A", "config": {}},
                    {
                        "id": "n02",
                        "type": "TRADE_DATA_COLLECTOR",
                        "label": "B",
                        "config": {
                            "source": "hs_client_order",
                            "query_template": "*:*",
                            "output_name": "trades",
                        },
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n01"},  # makes it cyclic
                ],
            }
        )
        assert not result.valid
        assert any(i.code == "CYCLE" for i in result.errors)
