"""
Tests for the copilot edit-mode context plumbing.

Ensures:

* `PromptBuilder.initial_prompt(scenario)` is a plain identity when
  no context is attached — the greenfield generation path (the
  palette's example prompts) must stay unchanged.
* When `current_workflow` is passed, the prompt switches to
  edit-mode: embeds the DAG, preserves node IDs, lists errors, and
  instructs the LLM to make a surgical edit.
* The compact representation strips UI-only fields (`position`,
  `disabled`) so prompt token budget isn't wasted on canvas state.
* `_render_errors` normalises mixed shapes (validator dicts, runtime
  dicts, free-form strings).
"""
from __future__ import annotations

from agent.prompt_builder import (
    PromptBuilder,
    _compact_workflow,
    _render_errors,
    _render_selection,
)
from copilot.workflow_generator import WorkflowCopilot


def _small_workflow() -> dict:
    return {
        "workflow_id": "wf_demo",
        "name": "Demo",
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "n01",
                "type": "ALERT_TRIGGER",
                "label": "Alert",
                "config": {},
                # UI-only fields — must be stripped in the prompt.
                "position": {"x": 60, "y": 60},
                "disabled": False,
            },
            {
                "id": "n14",
                "type": "SECTION_SUMMARY",
                "label": "Comms Summary",
                "config": {"input_name": "comms_data"},
            },
        ],
        "edges": [{"from": "n01", "to": "n14", "extra": "ignored"}],
    }


def test_initial_prompt_greenfield_includes_live_context_guidance() -> None:
    pb = PromptBuilder()
    prompt = pb.initial_prompt(
        "Create an FX front-running workflow",
        matched_skills=["skills-agentic-workflow-builder"],
    )

    assert "Create a NEW workflow" in prompt
    assert "Create an FX front-running workflow" in prompt
    assert "current Node I/O Contracts" in prompt
    assert "current Data Source Column Schemas" in prompt
    assert "skills-agentic-workflow-builder" in prompt
    assert "{dataset.column.agg}" in prompt


def test_system_prompt_uses_live_contracts_not_stale_file(tmp_path) -> None:
    stale = tmp_path / "node_contracts.json"
    stale.write_text('{"nodes":{"STALE_ONLY":{"description":"old"}}}')
    pb = PromptBuilder(contracts_path=stale)

    contracts = pb._load_contracts()

    assert "ALERT_TRIGGER" in contracts
    assert "STALE_ONLY" not in contracts


def test_system_prompt_exposes_upload_script_guardrail(monkeypatch) -> None:
    monkeypatch.delenv("DBSHERPA_ALLOW_UPLOAD_SCRIPT", raising=False)
    prompt = PromptBuilder().system_prompt()

    assert "Active Guardrails" in prompt
    assert "upload_script is DISABLED" in prompt
    assert "NEVER set SIGNAL_CALCULATOR.mode='upload_script'" in prompt


class _FakeChatLLM:
    def __init__(self) -> None:
        self.history_lengths: list[int] = []

    def chat_turn(self, *, system_prompt, history, user_turn, temperature, json_mode):
        self.history_lengths.append(len(history))
        return f"history={len(history)} user={user_turn}"


def test_copilot_chat_is_stateless_without_session_id() -> None:
    fake = _FakeChatLLM()
    cp = WorkflowCopilot(llm=fake)

    assert "history=0" in cp.chat("first")
    assert "history=0" in cp.chat("second")
    assert fake.history_lengths == [0, 0]


def test_copilot_chat_history_is_scoped_by_session_id() -> None:
    fake = _FakeChatLLM()
    cp = WorkflowCopilot(llm=fake)

    cp.chat("a1", session_id="A")
    cp.chat("b1", session_id="B")
    reply = cp.chat("a2", session_id="A")
    cp.reset(session_id="A")
    reset_reply = cp.chat("a3", session_id="A")

    assert "history=2" in reply
    assert "history=0" in reset_reply
    assert fake.history_lengths == [0, 0, 2, 0]


def test_initial_prompt_edit_mode_with_workflow() -> None:
    pb = PromptBuilder()
    prompt = pb.initial_prompt(
        "Fix the SECTION_SUMMARY error",
        current_workflow=_small_workflow(),
        matched_skills=["skills-agentic-workflow-builder"],
    )
    # Should switch to edit mode — look for the edit-mode header and
    # the embedded workflow JSON.
    assert "EXISTING workflow" in prompt
    assert '"n01"' in prompt and '"n14"' in prompt
    assert "SECTION_SUMMARY" in prompt
    assert "Current generation context" in prompt
    assert "skills-agentic-workflow-builder" in prompt
    # Editing rules must be present so the LLM knows to preserve IDs.
    assert "Preserve existing node IDs" in prompt
    # User request appears at the bottom.
    assert "Fix the SECTION_SUMMARY error" in prompt


def test_initial_prompt_includes_errors_when_provided() -> None:
    pb = PromptBuilder()
    prompt = pb.initial_prompt(
        "",  # empty — should default to "Fix the errors above."
        current_workflow=_small_workflow(),
        recent_errors=[
            {
                "kind": "runtime",
                "node_id": "n14",
                "severity": "error",
                "message": "'str' object has no attribute 'lower'",
            },
            {"code": "WIRING_BROKEN", "node_id": "n14", "message": "input_name not found"},
            "Raw exception: BackendUnavailable",
        ],
    )
    assert "Recent errors to fix" in prompt
    assert "'str' object has no attribute 'lower'" in prompt
    assert "WIRING_BROKEN" in prompt
    assert "BackendUnavailable" in prompt
    # Empty scenario falls back to the default ask.
    assert "Fix the errors above." in prompt


def test_compact_workflow_strips_ui_fields() -> None:
    compact = _compact_workflow(_small_workflow())
    first = compact["nodes"][0]
    assert "position" not in first
    assert "disabled" not in first
    # Semantic fields must survive.
    assert first["id"] == "n01"
    assert first["type"] == "ALERT_TRIGGER"
    # Edges are normalised to the minimal shape.
    assert compact["edges"] == [{"from": "n01", "to": "n14"}]


def test_render_errors_accepts_mixed_shapes() -> None:
    rendered = _render_errors(
        [
            {"code": "X", "node_id": "n01", "severity": "warning", "message": "msg1"},
            {"kind": "runtime", "message": "boom"},
            "plain string",
        ]
    )
    assert "WARNING" in rendered
    assert "code=X" in rendered and "node=n01" in rendered
    assert "runtime" in rendered and "boom" in rendered
    assert "plain string" in rendered


def test_render_errors_is_empty_for_no_errors() -> None:
    assert _render_errors([]) == ""


def test_initial_prompt_includes_selected_node_for_deictic_refs() -> None:
    """When a node is selected on the canvas and the user says "remove this",
    the prompt must pin down what "this" refers to so the LLM doesn't guess."""
    pb = PromptBuilder()
    prompt = pb.initial_prompt(
        "remove this node",
        current_workflow=_small_workflow(),
        selected_node_id="n14",
    )
    assert "Currently selected node" in prompt
    assert "`n14`" in prompt
    assert "SECTION_SUMMARY" in prompt
    # Editing rules must reference the deictic-resolution rule.
    assert "deictic references" in prompt


def test_initial_prompt_silently_skips_unknown_selected_id() -> None:
    """Frontend state can go stale relative to the DAG we just sent.
    A mismatched id must NOT block the edit — just omit the selection block."""
    pb = PromptBuilder()
    prompt = pb.initial_prompt(
        "add a spoofing signal",
        current_workflow=_small_workflow(),
        selected_node_id="n99_does_not_exist",
    )
    assert "Currently selected node" not in prompt
    # Edit mode is still engaged.
    assert "EXISTING workflow" in prompt


def test_render_selection_handles_missing_label() -> None:
    """Nodes without a label should fall back to the id."""
    wf = {"nodes": [{"id": "n03", "type": "DECISION_RULE", "config": {}}]}
    rendered = _render_selection("n03", wf)
    assert "`n03`" in rendered
    assert "DECISION_RULE" in rendered


def test_render_selection_empty_when_no_selection() -> None:
    assert _render_selection(None, _small_workflow()) == ""
    assert _render_selection("", _small_workflow()) == ""


def test_initial_prompt_includes_incremental_edit_guidance() -> None:
    """Add/remove/insert-between operations rely on specific rules —
    they must be in every edit-mode prompt so the LLM knows how to
    re-wire edges and assign IDs."""
    pb = PromptBuilder()
    prompt = pb.initial_prompt("add X", current_workflow=_small_workflow())
    assert "inserting a new node between" in prompt
    assert "deleting a node" in prompt
    assert "fresh IDs continuing the `nNN` sequence" in prompt


def test_repair_prompt_reminds_model_to_use_current_inventories() -> None:
    prompt = PromptBuilder().repair_prompt(
        [{"code": "BAD_PROMPT_REF", "node_id": "n03", "message": "bad ref"}],
        attempt=2,
        total=3,
    )

    assert "current Node I/O Contracts" in prompt
    assert "Data Source Column Schemas" in prompt
    assert "Surveillance Skills Library" in prompt
    assert "BAD_PROMPT_REF" in prompt
