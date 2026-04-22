"""
dbSherpa agent package.

Thin control system wrapped around the LLM. The shape follows the
"constrained workflow planner with a validation + repair loop" pattern:

    scenario
        │
        ▼
    PromptBuilder → Planner ──► draft graph
                                    │
                                    ▼
                              ValidatorAdapter
                                    │
                              ┌─────┴─────┐
                              │           │
                           valid       invalid
                              │           │
                              │           ▼
                              │    AutoFixer (deterministic)
                              │           │
                              │      still invalid?
                              │           │
                              │           ▼
                              │    FeedbackBuilder → Planner (retry)
                              │           │
                              └───────────┘
                                    │
                                    ▼
                              approved DAG

The harness (AgentRunner) owns `AgentState`, enforces the retry budget,
records metrics, and surfaces a stream of phase events so the UI can
render a live repair trace. The copilot HTTP endpoints are adapters
that drive this harness and translate events to SSE — they don't
contain any agent logic of their own.
"""
from .harness.state import AgentState, AgentEvent, AgentPhase  # noqa: F401
from .harness.runner import AgentRunner  # noqa: F401
from .harness.metrics import AgentMetrics, get_metrics  # noqa: F401
from .validator_adapter import ValidatorAdapter  # noqa: F401
from .planner import Planner  # noqa: F401
from .prompt_builder import PromptBuilder  # noqa: F401
from .repair.auto_fixer import AutoFixer, AutoFixReport  # noqa: F401
from .repair.feedback_builder import build_feedback  # noqa: F401

__all__ = [
    "AgentState",
    "AgentEvent",
    "AgentPhase",
    "AgentRunner",
    "AgentMetrics",
    "get_metrics",
    "ValidatorAdapter",
    "Planner",
    "PromptBuilder",
    "AutoFixer",
    "AutoFixReport",
    "build_feedback",
]
