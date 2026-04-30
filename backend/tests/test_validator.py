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
                        "type": "EXECUTION_DATA_COLLECTOR",
                        "label": "Executions",
                        # 'query_template' and 'output_name' are required; omit query_template.
                        "config": {"source": "hs_client_order", "output_name": "execution_data"},
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
                        "type": "EXECUTION_DATA_COLLECTOR",
                        "label": "Executions",
                        "config": {
                            "source": "not_a_real_source",
                            "query_template": "*:*",
                            "output_name": "execution_data",
                        },
                    },
                ],
                "edges": [{"from": "n01", "to": "n02"}],
            }
        )
        assert not result.valid
        codes = {i.code for i in result.errors}
        assert "BAD_ENUM_VALUE" in codes or "BAD_PARAM_TYPE" in codes

    def test_bad_prompt_template_braces_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "LLM_ACTION",
                        "label": "Action",
                        "config": {
                            "prompt_template": 'Return JSON like {"tool": "aggregation"}',
                        },
                    },
                ],
                "edges": [{"from": "n01", "to": "n02"}],
            }
        )

        assert not result.valid
        assert any(
            i.code == "BAD_PROMPT_TEMPLATE" and i.node_id == "n02"
            for i in result.errors
        )

    def test_prompt_ref_unknown_dataset_column_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "COMMS_COLLECTOR",
                        "label": "Comms",
                        "config": {
                            "query_template": "user:{context.trader_id}",
                            "output_name": "comms",
                        },
                    },
                    {
                        "id": "n03",
                        "type": "LLM_CRITIC",
                        "label": "Critic",
                        "config": {
                            "prompt_template": "Keyword hits: {comms.keyword_hit_count}",
                        },
                    },
                    {
                        "id": "n04",
                        "type": "REPORT_OUTPUT",
                        "label": "Report",
                        "config": {"output_path": "output/test.xlsx"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n03"},
                    {"from": "n03", "to": "n04"},
                ],
            }
        )

        assert not result.valid
        assert any(
            i.code == "BAD_PROMPT_REF" and i.node_id == "n03"
            for i in result.errors
        )

    def test_prompt_ref_known_dataset_column_agg_allowed(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "COMMS_COLLECTOR",
                        "label": "Comms",
                        "config": {
                            "query_template": "user:{context.trader_id}",
                            "output_name": "comms",
                        },
                    },
                    {
                        "id": "n03",
                        "type": "LLM_CRITIC",
                        "label": "Critic",
                        "config": {
                            "prompt_template": "Keyword hits: {comms._keyword_hit.sum}",
                        },
                    },
                    {
                        "id": "n04",
                        "type": "REPORT_OUTPUT",
                        "label": "Report",
                        "config": {"output_path": "output/test.xlsx"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n03"},
                    {"from": "n03", "to": "n04"},
                ],
            }
        )

        assert result.valid, result.to_json()

    def test_prompt_ref_unknown_special_ref_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "MARKET_DATA_COLLECTOR",
                        "label": "Market",
                        "config": {
                            "source": "EBS",
                            "query_template": "symbol:{context.currency_pair}",
                            "output_name": "market_data",
                        },
                    },
                    {
                        "id": "n03",
                        "type": "LLM_CRITIC",
                        "label": "Critic",
                        "config": {
                            "prompt_template": "Ticks: {market_data.@tick_count}",
                        },
                    },
                    {
                        "id": "n04",
                        "type": "REPORT_OUTPUT",
                        "label": "Report",
                        "config": {"output_path": "output/test.xlsx"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n03"},
                    {"from": "n03", "to": "n04"},
                ],
            }
        )

        assert not result.valid
        assert any(
            i.code == "BAD_PROMPT_REF" and i.node_id == "n03"
            for i in result.errors
        )

    def test_section_summary_dotted_stats_ref_allowed_when_computed(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "EXECUTION_DATA_COLLECTOR",
                        "label": "Orders",
                        "config": {
                            "source": "hs_client_order",
                            "query_template": "*:*",
                            "output_name": "client_orders",
                        },
                    },
                    {
                        "id": "n03",
                        "type": "SECTION_SUMMARY",
                        "label": "Client Orders Summary",
                        "config": {
                            "section_name": "client_orders_summary",
                            "input_name": "client_orders",
                            "mode": "templated",
                            "field_bindings": [
                                {"field": "order_id", "agg": "count"},
                                {"field": "quantity", "agg": "sum"},
                            ],
                            "llm_prompt_template": (
                                "Total orders: {stats.order_id_count}. "
                                "Total quantity: {stats.quantity_sum}."
                            ),
                        },
                    },
                    {
                        "id": "n04",
                        "type": "REPORT_OUTPUT",
                        "label": "Report",
                        "config": {"output_path": "output/test.xlsx"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n03"},
                    {"from": "n03", "to": "n04"},
                ],
            }
        )

        assert result.valid, result.to_json()

    def test_section_summary_dotted_stats_ref_rejected_when_not_computed(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
                    {
                        "id": "n02",
                        "type": "EXECUTION_DATA_COLLECTOR",
                        "label": "Orders",
                        "config": {
                            "source": "hs_client_order",
                            "query_template": "*:*",
                            "output_name": "client_orders",
                        },
                    },
                    {
                        "id": "n03",
                        "type": "SECTION_SUMMARY",
                        "label": "Client Orders Summary",
                        "config": {
                            "section_name": "client_orders_summary",
                            "input_name": "client_orders",
                            "mode": "templated",
                            "field_bindings": [
                                {"field": "order_id", "agg": "count"},
                            ],
                            "llm_prompt_template": "Bad stat: {stats.order_count}.",
                        },
                    },
                    {
                        "id": "n04",
                        "type": "REPORT_OUTPUT",
                        "label": "Report",
                        "config": {"output_path": "output/test.xlsx"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n03"},
                    {"from": "n03", "to": "n04"},
                ],
            }
        )

        assert not result.valid
        assert any(
            i.code == "BAD_PROMPT_REF" and i.node_id == "n03"
            for i in result.errors
        )


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
                        "type": "EXECUTION_DATA_COLLECTOR",
                        "label": "B",
                        "config": {
                            "source": "hs_client_order",
                            "query_template": "*:*",
                            "output_name": "execution_data",
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


# ---------------------------------------------------------------------------
# field_bindings column validation
# ---------------------------------------------------------------------------
def _dag_with_section_summary(field: str, collector_output: str = "execution_data") -> dict:
    """Minimal valid DAG: trigger → execution collector → section summary."""
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert", "config": {}},
            {
                "id": "n02",
                "type": "EXECUTION_DATA_COLLECTOR",
                "label": "Executions",
                "config": {
                    "source": "hs_client_order",
                    "query_template": "*:*",
                    "output_name": collector_output,
                },
            },
            {
                "id": "n03",
                "type": "SECTION_SUMMARY",
                "label": "Summary",
                "config": {
                    "section_name": "exec_section",
                    "input_name": collector_output,
                    "field_bindings": [{"field": field, "agg": "nunique"}],
                },
            },
        ],
        "edges": [{"from": "n01", "to": "n02"}, {"from": "n02", "to": "n03"}],
    }


class TestFieldBindings:
    def test_valid_column_passes(self):
        result = validate_dag(_dag_with_section_summary("trader_id"))
        assert not any(i.code == "UNKNOWN_COLUMN" for i in result.issues)
        assert result.valid

    def test_semantic_alias_passes(self):
        """Semantic tag 'size' resolves to selected source size column — no false UNKNOWN."""
        result = validate_dag(_dag_with_section_summary("size"))
        assert not any(i.code == "UNKNOWN_COLUMN" for i in result.issues)
        assert result.valid
        assert not any(i.code == "UNKNOWN_COLUMN" for i in result.errors)

    def test_signal_calculator_passes_through_upstream_columns(self):
        dag = _dag_with_section_summary("exec_id", "signals")
        dag["nodes"][1]["config"] = {
            "source": "hs_execution",
            "query_template": "*:* AND trade_version:1",
            "output_name": "execution_data",
        }
        dag["nodes"].insert(
            2,
            {
                "id": "n02b",
                "type": "SIGNAL_CALCULATOR",
                "label": "Signals",
                "config": {
                    "mode": "configure",
                    "signal_type": "FRONT_RUNNING",
                    "input_name": "execution_data",
                    "output_name": "signals",
                },
            },
        )
        dag["edges"] = [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n02b"},
            {"from": "n02b", "to": "n03"},
        ]

        result = validate_dag(dag)
        assert result.valid
        assert not any(i.code == "UNKNOWN_COLUMN" for i in result.issues)

    def test_invented_column_is_error(self):
        result = validate_dag(_dag_with_section_summary("does_not_exist"))
        assert not result.valid
        assert any(
            i.code == "UNKNOWN_COLUMN" and i.severity == "error" for i in result.errors
        )

    def test_unresolvable_input_name_skips_silently(self):
        """If the dataset name doesn't trace to a collector, skip (no false positives)."""
        dag = _dag_with_section_summary("qty", "execution_data")
        dag["nodes"][2]["config"]["input_name"] = "enriched_trades"
        result = validate_dag(dag)
        assert not any(i.code == "UNKNOWN_COLUMN" for i in result.issues)
