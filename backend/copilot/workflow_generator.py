"""
dbSherpa Copilot — adapter over the AgentRunner harness.

Historically this module contained the whole generate/validate/repair
loop. That logic now lives in `backend/agent/`, behind a proper harness
with explicit state, a deterministic auto-fixer, and metrics.

This file is kept as a stable seam for:
  * the chat endpoint (multi-turn Gemini history that's unrelated to
    workflow generation)
  * the legacy public surface (`generate_with_critic`,
    `generate_with_critic_stream`) consumed by the HTTP routers and
    tests — we translate AgentEvents back to the loosely-typed dict
    shape the frontend already renders.

Nothing here does any agent reasoning; it's transport + a sprinkling of
backward compatibility.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from agent.harness.runner import AgentRunner
from agent.harness.state import AgentPhase
from agent.planner import Planner
from agent.prompt_builder import PromptBuilder
from agent.repair.auto_fixer import AutoFixer
from agent.validator_adapter import ValidatorAdapter
from llm import GeminiAdapter, get_default_adapter


class WorkflowCopilot:
    def __init__(
        self,
        skills_dir: str = "skills",
        contracts_path: str = "contracts/node_contracts.json",
        llm: GeminiAdapter | None = None,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.contracts_path = Path(contracts_path)
        # One adapter for the whole copilot — chat and planner share
        # vendor config (API key, default model) but keep their own
        # per-call params (temperature, json_mode).
        self._llm = llm or get_default_adapter()

        self._prompt_builder = PromptBuilder(
            skills_dir=self.skills_dir,
            contracts_path=self.contracts_path,
        )
        self._planner = Planner()
        self._runner = AgentRunner(
            planner=self._planner,
            prompt_builder=self._prompt_builder,
            validator=ValidatorAdapter(),
            auto_fixer=AutoFixer(),
        )
        # Chat history is user/session state, not a process-global property.
        # The HTTP layer may cache this WorkflowCopilot for expensive planner
        # setup, so histories are keyed by explicit session_id. Calls without a
        # session_id are intentionally stateless to avoid cross-user leakage.
        self._histories: dict[str, list[dict]] = {}

    # ── multi-turn chat (separate concern from workflow generation) ───────────
    def chat(self, user_message: str, *, session_id: str | None = None) -> str:
        """Free-form chat used by the /copilot/chat endpoint.

        Conversation state is only retained when the caller supplies a
        `session_id`. Anonymous calls are single-turn by design: this backend
        process is shared, and retaining a default/global history would leak
        one user's chat context into another user's response.
        """
        history = self._histories.setdefault(session_id, []) if session_id else []
        reply = self._llm.chat_turn(
            system_prompt=self._prompt_builder.system_prompt(),
            history=history,
            user_turn=user_message,
            # Chat is free-form prose, not JSON. Small temperature
            # lift keeps responses from feeling robotic.
            temperature=0.3,
            json_mode=False,
        )
        if session_id:
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self, *, session_id: str | None = None) -> None:
        if session_id:
            self._histories.pop(session_id, None)
        else:
            self._histories.clear()

    # ── workflow generation — delegates to AgentRunner ────────────────────────
    def generate_with_critic(
        self,
        user_request: str,
        iterations: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
    ) -> dict:
        """Run the harness to completion and translate final state to the
        legacy response envelope.

        When `current_workflow` is provided the planner switches to
        edit-mode: it receives the DAG + any attached errors and is
        asked to produce a targeted fix rather than a greenfield
        workflow."""
        state = self._runner.run(
            user_request,
            max_attempts=iterations,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
        )

        if state.workflow is None or not state.is_valid:
            return {
                "success": False,
                "error": (state.validation or {}).get("summary", "No valid JSON produced"),
                "raw": state.raw_text,
                # The legacy response shape has a `history` slot, but the
                # harness keeps repair-loop prompts private. Multi-turn
                # conversational state lives in `chat()`.
                "history": [],
                "attempts": state.attempts,
                "validation": state.validation,
                "auto_fixes_applied": state.auto_fixes_applied,
            }
        return {
            "success": bool(state.is_valid),
            "workflow": state.workflow,
            "history": [],           # harness doesn't retain full history by design
            "attempts": state.attempts,
            "validation": state.validation,
            "auto_fixes_applied": state.auto_fixes_applied,
        }

    def generate_with_critic_stream(
        self,
        user_request: str,
        iterations: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
    ) -> Iterator[dict]:
        """Stream AgentEvents to the legacy dict shape the frontend already
        consumes. See `generate_with_critic` for the edit-mode contract.

        `AgentEvent.to_json()` is the wire shape consumed by
        `/copilot/generate/stream`; keep frontend phase/status handling in
        sync with `agent/harness/state.py`.
        """
        for event in self._runner.stream(
            user_request,
            max_attempts=iterations,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
        ):
            yield event.to_json()
