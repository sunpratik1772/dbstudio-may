"""
AutoFixer tests — exercise each deterministic repair rule in isolation
and confirm idempotency. No LLM calls.
"""
from __future__ import annotations

from agent.repair.auto_fixer import AutoFixer


def _err(code: str, node_id: str | None = None, **extra) -> dict:
    return {"code": code, "node_id": node_id, "message": "", **extra}


class TestEdgeNormalisation:
    def test_source_target_becomes_from_to(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01"}, {"id": "n02"}],
            "edges": [{"source": "n01", "target": "n02"}],
        }
        report = AutoFixer().fix(wf, [])
        assert report.changed
        assert wf["edges"] == [{"from": "n01", "to": "n02"}]

    def test_already_normalised_is_idempotent(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01"}, {"id": "n02"}],
            "edges": [{"from": "n01", "to": "n02"}],
        }
        report = AutoFixer().fix(wf, [])
        assert not report.changed
        assert wf["edges"] == [{"from": "n01", "to": "n02"}]


class TestLabelFix:
    def test_missing_label_fills_from_type(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01", "type": "ALERT_TRIGGER", "config": {}}],
            "edges": [],
        }
        report = AutoFixer().fix(wf, [_err("MISSING_LABEL", node_id="n01", field="label")])
        assert report.changed
        assert wf["nodes"][0]["label"]


class TestTradeVersionFix:
    def test_hs_execution_gets_trade_version(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [
                {
                    "id": "n01",
                    "type": "EXECUTION_DATA_COLLECTOR",
                    "label": "executions",
                    "config": {
                        "source": "hs_execution",
                        "query_template": "trader_id:{context.trader_id}",
                        "output_name": "executions",
                    },
                }
            ],
            "edges": [],
        }
        report = AutoFixer().fix(
            wf, [_err("MISSING_TRADE_VERSION", node_id="n01", field="config.query_template")]
        )
        assert report.changed
        assert "trade_version:1" in wf["nodes"][0]["config"]["query_template"]


class TestAutoFixerIsSafe:
    def test_non_dict_workflow_returns_empty_report(self):
        report = AutoFixer().fix("not a dict", [_err("EDGE_SHAPE")])  # type: ignore[arg-type]
        assert not report.changed
        assert report.applied == []

    def test_unknown_error_code_is_ignored(self):
        wf = {"schema_version": "1.0", "nodes": [], "edges": []}
        report = AutoFixer().fix(wf, [_err("SOMETHING_BRAND_NEW")])
        assert not report.changed
