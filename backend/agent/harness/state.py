"""
Typed state carried through a single agent run.

The old `WorkflowCopilot._run_generation` function mutated a dict and a
local list; every new field meant another implicit contract between
caller and callee. This module replaces that with explicit dataclasses
so each step (Planner, AutoFixer, ValidatorAdapter, …) has a clear
input/output signature.

`AgentEvent` is the on-wire shape that eventually becomes an SSE frame
on the copilot endpoint. Keeping it here — next to the state that
generates it — means the harness and the HTTP adapter can't drift
apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentPhase(str, Enum):
    """The phases the UI renders in its timeline.

    Values are chosen to match the existing frontend `CopilotPhase`
    union so we don't have to retranslate at the HTTP boundary.
    """

    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    GENERATING = "generating"
    AUTO_FIXING = "auto_fixing"     # NEW — surfaced when AutoFixer resolves issues
    CRITIQUING = "critiquing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class AgentEvent:
    """One progress update on the run timeline.

    The harness yields these; the HTTP adapter forwards them as SSE
    frames. Extra per-event payload lives in `data` to avoid a combinatorial
    explosion of optional fields at this layer.
    """

    phase: AgentPhase
    label: str
    status: str = "running"        # "running" | "done" | "error"
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "phase": self.phase.value,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            **self.data,
        }


@dataclass
class AgentState:
    """The working memory for a single run.

    `attempts` counts LLM repair passes only; deterministic auto-fix
    passes don't consume the budget because their behaviour is bounded.
    """

    scenario: str
    max_attempts: int = 3

    workflow: dict | None = None           # the draft DAG, or None if unparsed
    raw_text: str = ""                     # last raw LLM response
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    validation: dict | None = None         # full ValidationResult.to_json()
    history: list[dict] = field(default_factory=list)

    attempts: int = 0                      # completed LLM repair passes
    auto_fix_passes: int = 0
    auto_fixes_applied: list[str] = field(default_factory=list)

    template_id: str | None = None
    matched_skills: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.validation and self.validation.get("valid"))

    def remaining_attempts(self) -> int:
        return max(0, self.max_attempts - self.attempts)
