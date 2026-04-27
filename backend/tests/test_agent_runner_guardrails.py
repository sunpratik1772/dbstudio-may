"""Guardrail guarantees for the Copilot runner."""
from __future__ import annotations

import json

from agent.harness.runner import AgentRunner
from agent.planner import Planner


class _StaticLLM:
    def __init__(self, workflow: dict) -> None:
        self.raw = json.dumps(workflow)

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        return self.raw


class _AlwaysInvalidValidator:
    def validate(self, workflow: dict | None) -> dict:
        return {
            "valid": False,
            "errors": [{"code": "CYCLE", "message": "DAG contains a cycle", "severity": "error"}],
            "warnings": [],
            "summary": "1 error(s)",
        }


def test_stream_does_not_emit_invalid_workflow_on_exhausted_attempts() -> None:
    workflow = {
        "schema_version": "1.0",
        "nodes": [{"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert"}],
        "edges": [],
    }
    runner = AgentRunner(
        planner=Planner(_StaticLLM(workflow)),
        validator=_AlwaysInvalidValidator(),
    )

    events = [ev.to_json() for ev in runner.stream("make workflow", max_attempts=0)]
    complete = events[-1]

    assert complete["phase"] == "complete"
    assert complete["status"] == "error"
    assert complete["workflow"] is None
    assert complete["validation"]["errors"][0]["code"] == "CYCLE"
