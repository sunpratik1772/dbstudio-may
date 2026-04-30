from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.context import RunContext
from engine.dag_runner import execute_nodes, run_workflow_stream
from engine.registry import NODE_SPECS


def test_agent_layer_nodes_registered() -> None:
    expected = {
        "LLM_PLANNER",
        "PLAN_VALIDATOR",
        "LLM_ACTION",
        "ACTION_VALIDATOR",
        "TOOL_EXECUTOR",
        "LLM_CRITIC",
        "STATE_MANAGER",
        "LLM_EVALUATOR",
        "LOOP_CONTROLLER",
        "LLM_SYNTHESIZER",
        "LLM_CONTEXTUALIZER",
        "GUARDRAIL",
        "AGGREGATOR_NODE",
        "DATA_REDUCER",
        "ERROR_HANDLER",
    }
    assert expected <= set(NODE_SPECS)


def test_agent_layer_chain_executes_and_writes_artifact(tmp_path: Path) -> None:
    ctx = RunContext(alert_payload={"goal": "Compute revenue by region"})
    ctx.datasets["sales"] = pd.DataFrame(
        [
            {"region": "EU", "revenue": 10.0},
            {"region": "EU", "revenue": 15.0},
            {"region": "US", "revenue": 7.0},
        ]
    )

    artifact_path = tmp_path / "agent_result.json"
    nodes = [
        {
            "id": "n01",
            "type": "LLM_PLANNER",
            "label": "Plan",
            "config": {
                "goal": "Compute revenue by region",
                "plan": [
                    {
                        "step_id": "step_1",
                        "action": "Aggregate sales",
                        "tool": "aggregation",
                        "inputs": {
                            "input_name": "sales",
                            "metric": "revenue",
                            "group_by": "region",
                            "output_name": "revenue_by_region",
                        },
                        "dependencies": [],
                    }
                ],
            },
        },
        {"id": "n02", "type": "PLAN_VALIDATOR", "label": "Validate Plan", "config": {}},
        {"id": "n03", "type": "LLM_ACTION", "label": "Choose Action", "config": {}},
        {"id": "n04", "type": "ACTION_VALIDATOR", "label": "Validate Action", "config": {"block_on_invalid": True}},
        {"id": "n05", "type": "TOOL_EXECUTOR", "label": "Execute Tool", "config": {}},
        {"id": "n06", "type": "DATA_REDUCER", "label": "Reduce Data", "config": {"input_name": "revenue_by_region"}},
        {"id": "n07", "type": "LLM_CRITIC", "label": "Critic", "config": {}},
        {"id": "n08", "type": "STATE_MANAGER", "label": "State", "config": {}},
        {"id": "n09", "type": "LLM_EVALUATOR", "label": "Evaluate", "config": {}},
        {"id": "n10", "type": "LOOP_CONTROLLER", "label": "Loop", "config": {"max_iterations": 5}},
        {
            "id": "n11",
            "type": "LLM_SYNTHESIZER",
            "label": "Synthesize",
            "config": {"output_path": str(artifact_path)},
        },
    ]
    edges = [{"from": f"n{i:02d}", "to": f"n{i + 1:02d}"} for i in range(1, 11)]

    execute_nodes(nodes, edges, ctx)

    result = ctx.datasets["revenue_by_region"].sort_values("region").reset_index(drop=True)
    assert result.to_dict(orient="records") == [
        {"region": "EU", "revenue": 25.0},
        {"region": "US", "revenue": 7.0},
    ]
    assert ctx.values["validation"]["valid"] is True
    assert ctx.values["evaluator"]["done"] is True
    assert ctx.values["loop_controller"]["continue"] is False
    assert artifact_path.exists()
    assert ctx.report_path == str(artifact_path)


def test_data_quality_tool_accepts_dataset_name_alias() -> None:
    ctx = RunContext()
    ctx.datasets["orders"] = pd.DataFrame(
        [
            {"order_id": "o1", "trader_id": "T1"},
            {"order_id": None, "trader_id": "T1"},
        ]
    )

    nodes = [
        {
            "id": "n01",
            "type": "TOOL_EXECUTOR",
            "label": "DQ Check",
            "config": {
                "tool": "data_quality_checks",
                "args": {
                    "dataset_name": "orders",
                    "checks": [
                        {"type": "row_count_min", "value": 3},
                        {
                            "type": "null_columns",
                            "columns": ["order_id", "trader_id"],
                            "threshold": 0.1,
                        },
                    ],
                },
                "output_name": "orders_dq",
            },
        }
    ]

    execute_nodes(nodes, [], ctx)

    report = ctx.values["orders_dq"]["report"]
    assert report["row_count"] == 2
    assert ctx.values["orders_count"] == 2
    assert "row_count 2 below minimum 3" in report["issues"]
    assert any("order_id" in issue for issue in report["issues"])


def test_direct_critic_does_not_require_action_for_evidence_review() -> None:
    ctx = RunContext()
    ctx.set(
        "last_result",
        {
            "status": "issues",
            "report": {
                "row_count": 0,
                "issues": ["row_count 0 below minimum 1"],
            },
        },
    )

    nodes = [
        {
            "id": "n01",
            "type": "LLM_CRITIC",
            "label": "Critique Evidence",
            "config": {
                "output_name": "evidence_critique",
            },
        }
    ]

    execute_nodes(nodes, [], ctx)

    critique = ctx.values["evidence_critique"]
    assert critique["valid"] is False
    assert "Action did not specify a tool." not in critique["issues"]
    assert "row_count 0 below minimum 1" in critique["issues"]


def test_data_quality_handles_list_valued_columns() -> None:
    ctx = RunContext()
    ctx.datasets["comms"] = pd.DataFrame(
        [
            {
                "user": "T1",
                "timestamp": "2024-01-01T09:00:00Z",
                "display_post": "front-run",
                "_matched_keywords": ["front-run"],
            },
            {
                "user": "T1",
                "timestamp": "2024-01-01T09:00:00Z",
                "display_post": "front-run",
                "_matched_keywords": ["front-run"],
            },
        ]
    )

    execute_nodes(
        [
            {
                "id": "n01",
                "type": "TOOL_EXECUTOR",
                "label": "DQ Communications",
                "config": {
                    "tool": "data_quality_checks",
                    "args": {"input_name": "comms", "checks": ["duplicates"]},
                    "output_name": "comms_dq",
                },
            }
        ],
        [],
        ctx,
    )

    assert ctx.values["comms_dq"]["report"]["duplicates"] == 1


def test_synthesizer_prompt_supports_dotted_runtime_dict_slots(tmp_path: Path) -> None:
    ctx = RunContext(
        alert_payload={
            "alert_id": "A-1",
            "alert_date": "2024-01-15",
            "trader_id": "T1",
        }
    )
    ctx.set(
        "evaluation_result",
        {
            "done": False,
            "confidence": 0.62,
            "missing": ["market data coverage"],
        },
    )
    ctx.set("executive_summary", "Evidence is incomplete.")

    artifact_path = tmp_path / "memo.json"
    execute_nodes(
        [
            {
                "id": "n01",
                "type": "LLM_SYNTHESIZER",
                "label": "Synthesize Memo",
                "config": {
                    "result_key": "evaluation_result",
                    "prompt_template": (
                        "Alert {context.alert_id} on {context.alert_date}\n"
                        "Done: {evaluation_result.done}\n"
                        "Confidence: {evaluation_result.confidence}\n"
                        "Missing: {evaluation_result.missing}\n"
                        "Summary: {executive_summary}"
                    ),
                    "output_path": str(artifact_path),
                },
            }
        ],
        [],
        ctx,
    )

    assert artifact_path.exists()
    memo = ctx.values["final_output"]
    assert memo["result"]["done"] is False
    assert memo["result"]["confidence"] == 0.62


def test_stream_output_includes_agent_response_for_agent_nodes() -> None:
    dag = {
        "schema_version": "1.0",
        "name": "agent response smoke test",
        "nodes": [
            {
                "id": "n01",
                "type": "LLM_PLANNER",
                "label": "Plan",
                "config": {
                    "goal": "Check evidence",
                    "plan": [
                        {
                            "step_id": "step_1",
                            "action": "Review evidence",
                            "tool": "passthrough",
                            "inputs": {},
                            "dependencies": [],
                        }
                    ],
                },
            }
        ],
        "edges": [],
    }

    events = list(run_workflow_stream(dag, {}))
    complete = next(e for e in events if e["type"] == "node_complete")

    assert complete["output"]["agent_response"] == (
        "Planned 1 step(s). First step: Review evidence."
    )
