"""
Planner — the LLM wrapper.

The planner doesn't know about validation, repair loops, or harness
state. Its contract is narrow:

    planner.generate(system_prompt, history, user_turn) -> raw text

Keeping it narrow means (a) tests can swap in a stub that returns
canned JSON and (b) switching from Gemini to another provider is a
local change here rather than a wiring diagram change.

Parsing the model's text into a workflow dict also happens here, since
that's the last step the LLM layer is aware of — the harness receives
`(raw_text, parsed_workflow_or_none)`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from llm import GeminiAdapter, get_default_adapter


@dataclass
class PlanResult:
    raw: str
    workflow: dict | None


class LLMClient(Protocol):
    """Minimal protocol the Planner needs. Satisfied by the default
    `GeminiAdapter`-backed client below, and by test stubs that
    return canned strings."""

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str: ...


class _AdapterClient:
    """Default LLMClient — delegates to the shared `GeminiAdapter`.

    Kept as a thin protocol adapter (not a subclass of GeminiAdapter)
    so tests can still inject any object that implements `complete`
    without needing to know what a chat-turn looks like.
    """

    def __init__(self, adapter: GeminiAdapter | None = None) -> None:
        self._adapter = adapter or get_default_adapter()

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        return self._adapter.chat_turn(
            system_prompt=system_prompt,
            history=history,
            user_turn=user_turn,
            temperature=0.0,
            json_mode=True,
        )


class Planner:
    """Generates a workflow draft from the current conversation state."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or _AdapterClient()

    def generate(
        self,
        system_prompt: str,
        history: list[dict],
        user_turn: str,
    ) -> PlanResult:
        raw = self.llm.complete(system_prompt, history, user_turn)
        return PlanResult(raw=raw, workflow=_try_parse_workflow(raw))


# ---------------------------------------------------------------------------
# JSON extraction — the model still occasionally wraps its output even when
# we forbid markdown fences, so we greedily grab the first {...} block.
# ---------------------------------------------------------------------------
def _try_parse_workflow(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None
