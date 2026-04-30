"""
AgentRunner — the control system around the Planner.

Responsibilities (per the blueprint):
  * control retries
  * track state
  * apply constraints
  * measure quality
  * prevent bad outputs

Flow for a single run:

    1. Emit `understanding` + `planning` events (so the UI timeline has
       the familiar shape).
    2. Call Planner with the initial prompt.
    3. Parse → Validate.
    4. If valid: emit success, return.
    5. If invalid: run AutoFixer. If it clears all errors, emit an
       `auto_fixing` event and return without consuming an LLM attempt.
    6. If still invalid: build repair brief → Planner → repeat up to
       `max_attempts` times.

The runner yields `AgentEvent`s. The HTTP adapter translates those to
SSE frames. The blocking caller just drains the iterator and inspects
the final state.
"""
from __future__ import annotations

import copy
from typing import Iterator

from ..planner import Planner
from ..prompt_builder import PromptBuilder
from ..repair.auto_fixer import AutoFixer
from ..validator_adapter import ValidatorAdapter
from .metrics import AgentMetrics, get_metrics
from .state import AgentEvent, AgentPhase, AgentState


class AgentRunner:
    def __init__(
        self,
        planner: Planner | None = None,
        prompt_builder: PromptBuilder | None = None,
        validator: ValidatorAdapter | None = None,
        auto_fixer: AutoFixer | None = None,
        metrics: AgentMetrics | None = None,
    ) -> None:
        self.planner = planner or Planner()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.validator = validator or ValidatorAdapter()
        self.auto_fixer = auto_fixer or AutoFixer()
        self.metrics = metrics or get_metrics()

    # --------------------------------------------------------------------
    # Public API — both shapes delegate to _run() which does the real work.
    # --------------------------------------------------------------------
    def run(
        self,
        scenario: str,
        max_attempts: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
    ) -> AgentState:
        """Blocking entry-point. Drains the stream and returns final state."""
        state: AgentState | None = None
        for ev, s in self._run(
            scenario, max_attempts, current_workflow, recent_errors, selected_node_id
        ):
            state = s  # last yielded state is the final one
        assert state is not None  # _run always yields at least once
        return state

    def stream(
        self,
        scenario: str,
        max_attempts: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
    ) -> Iterator[AgentEvent]:
        """Streaming entry-point. Yields AgentEvents as the run progresses."""
        for ev, _state in self._run(
            scenario, max_attempts, current_workflow, recent_errors, selected_node_id
        ):
            yield ev

    # --------------------------------------------------------------------
    # Inner driver — yields (event, state) so both API shapes can read
    # whatever they need without duplicating logic.
    # --------------------------------------------------------------------
    def _run(
        self,
        scenario: str,
        max_attempts: int,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
    ) -> Iterator[tuple[AgentEvent, AgentState]]:
        self.metrics.record_run_start()
        state = AgentState(scenario=scenario, max_attempts=max_attempts)
        system_prompt = self.prompt_builder.system_prompt()
        history: list[dict] = []

        editing_mode = current_workflow is not None
        # ── Phase: understanding ------------------------------------------
        yield AgentEvent(
            AgentPhase.UNDERSTANDING, "Understanding the request",
            detail=(
                f"Editing existing workflow · {scenario[:100]}"
                if editing_mode
                else f"Parsing: {scenario[:120]}"
            ),
        ), state
        summary_detail = (
            (
                f"Edit of {len(current_workflow.get('nodes', []))}-node workflow"
                + (
                    f" · {len(recent_errors)} error(s) to fix"
                    if recent_errors
                    else ""
                )
            )
            if editing_mode
            else f"{len(scenario.split())} words, targeting workflow generation"
        )
        yield AgentEvent(
            AgentPhase.UNDERSTANDING, "Understanding the request",
            status="done",
            detail=summary_detail,
        ), state

        # ── Phase: planning (skills match, heuristic template pick) ------
        all_skills = self.prompt_builder.list_skills()
        matched = self.prompt_builder.match_skills(scenario)
        state.matched_skills = matched
        yield AgentEvent(
            AgentPhase.PLANNING, "Retrieving skills & contracts",
            detail="Scanning skill library and node I/O contracts",
        ), state
        yield AgentEvent(
            AgentPhase.PLANNING, "Retrieving skills & contracts",
            status="done",
            detail=(
                f"{len(all_skills)} skills, matched: "
                f"{', '.join(matched) or '(none)'}"
            ),
            data={"skills": all_skills, "matched": matched},
        ), state

        # ── Phase: initial generation -------------------------------------
        yield AgentEvent(
            AgentPhase.GENERATING, "Creating nodes & edges",
            detail="Calling LLM for initial workflow draft",
        ), state

        initial_turn = self.prompt_builder.initial_prompt(
            scenario,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
            matched_skills=matched,
        )
        try:
            plan = self.planner.generate(system_prompt, history, initial_turn)
        except Exception as exc:
            yield AgentEvent(
                AgentPhase.ERROR, "Generation failed", status="error", detail=str(exc),
            ), state
            self.metrics.record_run_failure(attempts=0, error_codes=["LLM_CALL_FAILED"])
            return

        history.append({"role": "user", "content": initial_turn})
        history.append({"role": "assistant", "content": plan.raw})
        state.raw_text = plan.raw
        state.workflow = plan.workflow

        state.validation = self.validator.validate(state.workflow)
        state.errors = state.validation.get("errors", [])
        state.warnings = state.validation.get("warnings", [])

        if state.workflow is not None:
            yield AgentEvent(
                AgentPhase.GENERATING, "Creating nodes & edges", status="done",
                detail=(
                    f"Draft: {len(state.workflow.get('nodes', []))} nodes / "
                    f"{len(state.workflow.get('edges', []))} edges · "
                    + ("validator clean" if state.is_valid
                       else f"{len(state.errors)} validator error(s)")
                ),
                data={"draft_summary": _summarize(state.workflow)},
            ), state
        else:
            yield AgentEvent(
                AgentPhase.GENERATING, "Creating nodes & edges", status="error",
                detail="Draft was not parseable JSON",
            ), state

        if state.is_valid:
            yield from self._emit_success(state)
            return

        # ── Phase: deterministic auto-fix pass (no LLM) -------------------
        # We only try auto-fix when we have *something* to patch. If the
        # LLM returned unparseable JSON there's nothing to mechanically fix.
        if state.workflow is not None:
            yield from self._try_auto_fix(state)
            if state.is_valid:
                yield from self._emit_success(state)
                return

        # ── Phase: LLM repair loop ----------------------------------------
        while state.attempts < state.max_attempts:
            attempt = state.attempts + 1
            current_errors = state.errors
            repair_msg = self.prompt_builder.repair_prompt(
                current_errors, attempt, state.max_attempts
            )

            yield AgentEvent(
                AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                detail=(
                    f"{len(current_errors)} validator error(s) to fix"
                    if state.workflow is not None
                    else "Re-asking for parseable JSON"
                ),
                data={
                    "attempt": attempt,
                    "validation_errors": current_errors[:12],
                },
            ), state

            try:
                plan = self.planner.generate(system_prompt, history, repair_msg)
            except Exception as exc:
                yield AgentEvent(
                    AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                    status="error", detail=str(exc),
                    data={"attempt": attempt},
                ), state
                yield AgentEvent(
                    AgentPhase.ERROR, "Repair failed", status="error", detail=str(exc),
                ), state
                self.metrics.record_run_failure(
                    attempts=attempt,
                    error_codes=[e.get("code", "ERROR") for e in current_errors],
                )
                return

            history.append({"role": "user", "content": repair_msg})
            history.append({"role": "assistant", "content": plan.raw})
            state.raw_text = plan.raw
            state.attempts = attempt

            if plan.workflow is None:
                # Don't clobber the previous best draft. Let the loop retry.
                yield AgentEvent(
                    AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                    status="error", detail="Repair output was not valid JSON",
                    data={"attempt": attempt},
                ), state
                continue

            state.workflow = plan.workflow
            state.validation = self.validator.validate(state.workflow)
            state.errors = state.validation.get("errors", [])
            state.warnings = state.validation.get("warnings", [])

            approved = state.is_valid
            yield AgentEvent(
                AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                status="done",
                detail=(
                    "APPROVED — validator clean" if approved
                    else f"{len(state.errors)} error(s) remain"
                ),
                data={
                    "attempt": attempt,
                    "approved": approved,
                    "summary": _summarize(state.workflow),
                    "validation_errors": state.errors[:12],
                },
            ), state

            if approved:
                yield from self._emit_success(state)
                return

            # Try an auto-fix pass after each LLM repair — the model
            # often fixes 90% of errors and leaves a hard-rule holdout
            # that AutoFixer can patch without burning another attempt.
            yield from self._try_auto_fix(state)
            if state.is_valid:
                yield from self._emit_success(state)
                return

        # ── Exhausted attempts --------------------------------------------
        yield AgentEvent(
            AgentPhase.FINALIZING, "Finalizing workflow", status="done",
            detail=(
                f"{len(state.workflow.get('nodes', []))} nodes · "
                f"{len(state.workflow.get('edges', []))} edges · "
                f"{len(state.errors)} unresolved error(s)"
                if state.workflow is not None
                else "No parseable workflow after all attempts"
            ),
        ), state
        yield AgentEvent(
            AgentPhase.COMPLETE, "Workflow ready" if state.is_valid else "Workflow failed",
            status="done" if state.is_valid else "error",
            detail=state.workflow.get("name", "") if state.workflow else "",
            data={
                # Guardrail guarantee: never hand the UI a workflow that the
                # deterministic validator rejected. The failed draft stays in
                # validation/raw diagnostics, but it must not be loaded or saved.
                "workflow": state.workflow if state.is_valid else None,
                "validation": state.validation,
            },
        ), state
        self.metrics.record_run_failure(
            attempts=state.attempts,
            error_codes=[e.get("code", "ERROR") for e in state.errors],
        )

    # --------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------
    def _try_auto_fix(self, state: AgentState) -> Iterator[tuple[AgentEvent, AgentState]]:
        """Apply deterministic fixes and re-validate.

        We work on a deep copy first so a buggy rule can't corrupt the
        state; only swap the workflow in if the repaired version has
        strictly fewer errors.
        """
        if state.workflow is None:
            return
        candidate = copy.deepcopy(state.workflow)
        report = self.auto_fixer.fix(candidate, state.errors)
        if not report.changed:
            return

        new_validation = self.validator.validate(candidate)
        new_errors = new_validation.get("errors", [])

        # Only accept the rewrite if it's a strict improvement. AutoFixer
        # is supposed to be safe, but "don't make things worse" is a
        # cheap invariant to enforce at the harness level.
        if len(new_errors) >= len(state.errors):
            return

        state.workflow = candidate
        state.validation = new_validation
        state.errors = new_errors
        state.warnings = new_validation.get("warnings", [])
        state.auto_fix_passes += 1
        state.auto_fixes_applied.extend(report.applied)
        self.metrics.record_auto_fix(report.applied)

        yield AgentEvent(
            AgentPhase.AUTO_FIXING, "Deterministic auto-fix",
            status="done",
            detail=(
                f"Applied {len(report.applied)} mechanical fix(es); "
                + (
                    "validator clean"
                    if new_validation["valid"]
                    else f"{len(new_errors)} error(s) remain"
                )
            ),
            data={
                "applied": report.applied,
                "approved": new_validation["valid"],
                "summary": _summarize(candidate),
            },
        ), state

    def _emit_success(self, state: AgentState) -> Iterator[tuple[AgentEvent, AgentState]]:
        yield AgentEvent(
            AgentPhase.FINALIZING, "Finalizing workflow", status="done",
            detail=(
                f"{len(state.workflow.get('nodes', []))} nodes · "
                f"{len(state.workflow.get('edges', []))} edges"
            ),
        ), state
        yield AgentEvent(
            AgentPhase.COMPLETE, "Workflow ready", status="done",
            detail=state.workflow.get("name", ""),
            data={
                "workflow": state.workflow,
                "validation": state.validation,
            },
        ), state
        self.metrics.record_run_success(attempts=state.attempts)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _summarize(wf: dict) -> dict:
    return {
        "name": wf.get("name"),
        "node_count": len(wf.get("nodes", [])),
        "edge_count": len(wf.get("edges", [])),
        "node_types": sorted(
            {n.get("type") for n in wf.get("nodes", []) if n.get("type")}
        ),
    }
