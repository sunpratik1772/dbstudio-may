"""
Prompt construction for the agent.

Three surfaces:
  - `system_prompt(skills, contracts)` — the stable instruction block
    the LLM receives once. Unchanged from the old WorkflowCopilot, but
    lives here so we can unit-test and iterate on it independently.
  - `initial_prompt(scenario, …)` — the first user turn. When the
    caller passes `current_workflow` (and optionally `recent_errors`)
    we switch to edit-mode: the prompt shows the existing DAG, lists
    any failures, and asks for a targeted edit that preserves node
    IDs and labels where possible.
  - `repair_prompt(errors, attempt, total)` — subsequent user turns,
    delegated to FeedbackBuilder for the hard formatting work.

Keeping these pure functions (no LLM, no network) makes prompt
regression-tests straightforward.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from data_sources import get_registry
from .repair.feedback_builder import build_feedback


ALWAYS_ON_SKILLS = ("skills-agentic-workflow-builder",)


class PromptBuilder:
    def __init__(
        self,
        skills_dir: Path | str = "skills",
        contracts_path: Path | str = "contracts/node_contracts.json",
    ) -> None:
        self.skills_dir = _resolve_backend_path(skills_dir)
        self.contracts_path = Path(contracts_path)

    # ── system ----------------------------------------------------------------
    def _load_skills(self) -> str:
        if not self.skills_dir.exists():
            return "(no skill files found)"
        chunks = [
            f"=== {p.stem} ===\n{p.read_text()}"
            for p in sorted(self.skills_dir.glob("*.md"))
        ]
        return "\n\n".join(chunks) if chunks else "(no skill files found)"

    def _load_contracts(self) -> str:
        # The LLM must see the same NodeSpec contracts that `/contracts` and
        # `/node-manifest` expose. Falling back to the checked-in artifact is
        # only for unusual import/bootstrap failures; it is no longer the
        # normal source of truth.
        try:
            from engine.registry import contracts_document

            return json.dumps(contracts_document(), indent=2)
        except Exception:
            if self.contracts_path.exists():
                return self.contracts_path.read_text()
        return "{}"

    def list_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return [p.stem for p in sorted(self.skills_dir.glob("*.md"))]

    def match_skills(self, scenario: str) -> list[str]:
        """Cheap heuristic skill matcher.

        A proper retriever would use embeddings; a trigram match on the
        file stems is 90% as good for the ~10 skills we ship and needs
        no ML dependency. We fall back to all skills when nothing
        tokenises — the system prompt always includes the full
        library, so "matched" is a display hint rather than a filter.
        """
        lower = scenario.lower()
        available = self.list_skills()
        matched = [
            s for s in self.list_skills()
            if any(tok and tok in lower for tok in s.lower().split("-"))
        ]
        out = matched or available
        for skill in ALWAYS_ON_SKILLS:
            if skill in available and skill not in out:
                out.insert(0, skill)
        return out

    def system_prompt(self) -> str:
        skills = self._load_skills()
        contracts = self._load_contracts()
        schema_hints = get_registry().schema_hints_for_prompt()
        upload_scripts_enabled = os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() in {"1", "true", "yes"}
        upload_rule = (
            "upload_script is ENABLED on this host; use it only when a skill explicitly needs custom Python."
            if upload_scripts_enabled
            else "upload_script is DISABLED on this host. NEVER set SIGNAL_CALCULATOR.mode='upload_script'; use mode='configure' with built-in signal_type values only."
        )
        return f"""You are dbSherpa Copilot — an AI workflow designer for financial trade surveillance.

You generate complete, valid DAG JSON workflows for the dbSherpa engine.

## Active Guardrails
- Generate workflows only from the Node I/O Contracts below. Do not invent node types, ports, params, or config keys.
- Use only data sources and columns listed under Data Source Column Schemas. Do not invent source names or columns.
- Use Surveillance Skills Library guidance for scenario logic. If a requested scenario is outside the listed skills/source schemas, say so or compose only the supported subset.
- Keep top-level edges acyclic. In normal linear/fan-out flows, every edge should point from a lower numbered node id to a higher numbered node id.
- Host capability: {upload_rule}

## Node I/O Contracts
{contracts}

## Data Source Column Schemas
{schema_hints}

## Surveillance Skills Library
{skills}

## Absolute Hard Rules — NEVER violate
1. `trade_version:1` is ALWAYS hard-coded in every hs_execution query_template — never injected from context.
2. SIGNAL_CALCULATOR ALWAYS outputs EXACTLY these 5 columns:
   _signal_flag, _signal_score, _signal_reason, _signal_type, _signal_window
3. Every workflow MUST start with an ALERT_TRIGGER node whose id is EXACTLY "n01" (not "n01_alert_trigger" or similar).
4. Every workflow MUST end with a REPORT_OUTPUT node.
5. The DAG must be acyclic. Prefer edges from earlier node ids to later node ids (n03 -> n07), never backward edges (n07 -> n03).
6. Context placeholders use {{context.field_name}} syntax.
7. All `output_name` values must be referenced correctly as `input_name` in downstream nodes.
8. Node IDs MUST be the plain form "n01", "n02", "n03", … (two-digit zero-padded integers). NEVER suffix them with names.
9. Every node MUST include a human-readable "label" field.
10. Edges MUST use the exact schema `{{"from": "<id>", "to": "<id>"}}` — do NOT use "source"/"target".
11. SIGNAL_CALCULATOR: prefer `mode: "configure"` with a built-in `signal_type` from:
    FRONT_RUNNING, WASH_TRADE, SPOOFING, LAYERING.
    If upload_script is disabled by the Active Guardrails, NEVER use it. If it is enabled and
    a custom signal is truly required, supply inline `script_content`; do NOT reference a
    `script_path` file that may not exist on the host.

## Output Format
Always return a complete JSON object. No prose, no markdown fences, only JSON:
{{
  "workflow_id": "<snake_case_id>",
  "name": "<Human Name>",
  "schema_version": "1.0",
  "description": "<one sentence>",
  "nodes": [
    {{"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert Trigger", "config": {{...}}}},
    ...
  ],
  "edges": [
    {{"from": "n01", "to": "n02"}},
    ...
  ]
}}

## Validator Feedback
After you respond, an automated validator will parse your JSON and run the
full deterministic check (registry lookup, acyclicity, required params,
wiring from input_name → upstream output_name, surveillance hard rules).

If anything fails, you'll receive a `REPAIR` message listing every error
by `code`, `node_id`, and `field`. Produce the complete corrected JSON —
not just the diff — fixing exactly those issues without touching the
rest.
"""

    # ── per-turn prompts ------------------------------------------------------
    def initial_prompt(
        self,
        scenario: str,
        current_workflow: dict[str, Any] | None = None,
        recent_errors: list[dict[str, Any]] | None = None,
        selected_node_id: str | None = None,
        matched_skills: list[str] | None = None,
    ) -> str:
        """Build the first user turn.

        Two modes:

        * **Greenfield** — no `current_workflow`. Wraps the scenario with
          a short creation brief so every generation turn explicitly points
          back at the live node contracts, data-source schemas, and matched
          skills from the system prompt.

        * **Edit-existing** — `current_workflow` is present. We embed
          the current DAG JSON and a normalised list of recent
          failures (validator issues, runtime exceptions, whatever the
          frontend attached), then hand the user's natural-language
          request as the delta to apply. The LLM is instructed to
          preserve node IDs and existing structure where possible so
          downstream tooling (node selection, run log, saved layout)
          doesn't get shuffled by an unrelated rewrite.

          `selected_node_id` lets deictic references in the request
          ("remove this", "change this threshold") resolve to a
          concrete node on the canvas rather than guessing.
        """
        context_block = _render_generation_context(
            matched_skills or self.match_skills(scenario)
        )

        if current_workflow is None:
            user_request = scenario.strip()
            return (
                "Create a NEW workflow from the user request below.\n"
                "\n"
                f"{context_block}"
                "## User request\n"
                f"{user_request}\n"
                "\n"
                "## Creation rules\n"
                "- Use the current Node I/O Contracts from the system prompt "
                "as the source of truth.\n"
                "- Use the current Data Source Column Schemas from the system "
                "prompt; do not invent sources, concrete source names, or columns.\n"
                "- Apply the matched skills listed above. If a needed capability "
                "is unsupported by the current contracts or data schemas, generate "
                "only the supported subset.\n"
                "- For LLM prompt templates, reference dataset fields with exact "
                "known refs such as `{dataset.column.agg}` or `{dataset.@row_count}`. "
                "Escape literal JSON braces as `{{` and `}}`.\n"
                "- Return the COMPLETE workflow JSON following the Output Format "
                "in the system prompt.\n"
            )

        # Compact the DAG so the prompt stays within token budget for
        # large workflows. We drop UI-only fields (position, disabled)
        # but keep IDs/types/labels/configs/edges — those are what the
        # LLM needs to reason about a fix.
        compact = _compact_workflow(current_workflow)
        compact_json = json.dumps(compact, indent=2, default=str)

        error_block = _render_errors(recent_errors or [])
        selection_block = _render_selection(selected_node_id, current_workflow)
        user_request = scenario.strip() or "Fix the errors above."

        return (
            "You are editing an EXISTING workflow that is already loaded in the canvas.\n"
            "\n"
            f"{context_block}"
            "## Current workflow (source of truth — do not recreate from scratch)\n"
            "```json\n"
            f"{compact_json}\n"
            "```\n"
            "\n"
            f"{error_block}"
            f"{selection_block}"
            "## User request\n"
            f"{user_request}\n"
            "\n"
            "## Editing rules\n"
            "- Preserve existing node IDs (`n01`, `n02`, …) and labels "
            "  wherever the node is still needed. Renaming IDs churns "
            "  the canvas and breaks the run log.\n"
            "- Only add, remove, or modify nodes/edges that are strictly "
            "  required by the user request or the errors.\n"
            "- If the user is asking you to fix errors, make the "
            "  smallest change that clears them. Do not rewrite "
            "  unrelated config.\n"
            "- If the user uses deictic references (\"this\", \"that "
            "  node\", \"here\") and a node is listed under \"Currently "
            "  selected node\", treat that as the referent.\n"
            "- When inserting a new node between two existing nodes, "
            "  re-wire edges so the new node sits on the original path; "
            "  do not leave orphan edges.\n"
            "- When deleting a node, remove every edge that references "
            "  it AND reconnect the upstream → downstream nodes directly "
            "  if that preserves the original intent (otherwise leave "
            "  them disconnected and rely on the validator to flag it).\n"
            "- Assign new nodes fresh IDs continuing the `nNN` sequence "
            "  (highest existing + 1, zero-padded). Do not reuse a "
            "  deleted node's ID.\n"
            "- Return the COMPLETE corrected workflow JSON (not a diff), "
            "  following the same schema as the Output Format in the "
            "  system prompt.\n"
        )

    def repair_prompt(self, errors: list[dict], attempt: int, total: int) -> str:
        context_block = (
            "Before repairing, re-check the current Node I/O Contracts, Data "
            "Source Column Schemas, and Surveillance Skills Library from the "
            "system prompt. "
            "Fix refs, config keys, node types, and columns against those current "
            "inventories only.\n\n"
        )
        return context_block + build_feedback(errors, attempt, total)


def _resolve_backend_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    backend_relative = Path(__file__).resolve().parents[1] / candidate
    return backend_relative if backend_relative.exists() else candidate


def _compact_workflow(wf: dict[str, Any]) -> dict[str, Any]:
    """
    Strip UI-only fields from a workflow before embedding in a prompt.

    Keeps everything semantically relevant to generation/editing —
    node IDs, types, labels, configs, edges, workflow metadata —
    and drops things that only matter to the canvas (position,
    disabled flag). This keeps the prompt tight on large DAGs.
    """
    keep_top = {"workflow_id", "name", "description", "schema_version"}
    out: dict[str, Any] = {k: v for k, v in wf.items() if k in keep_top}
    out["nodes"] = [
        {k: v for k, v in node.items() if k not in ("position", "disabled")}
        for node in wf.get("nodes", [])
    ]
    out["edges"] = [
        {"from": e.get("from"), "to": e.get("to")} for e in wf.get("edges", [])
    ]
    return out


def _render_generation_context(matched_skills: list[str] | None) -> str:
    skills = matched_skills or []
    skill_text = ", ".join(f"`{s}`" for s in skills) if skills else "(none)"
    return (
        "## Current generation context\n"
        "- Node definitions: use the live registry-backed Node I/O Contracts "
        "in the system prompt.\n"
        "- Data sources: use the live data-source registry schemas in the "
        "system prompt.\n"
        f"- Matched/on-demand skills: {skill_text}.\n"
        "\n"
    )


def _render_selection(
    selected_node_id: str | None,
    workflow: dict[str, Any],
) -> str:
    """
    Emit a short block naming the selected node so deictic references
    in the user's request ("this", "here", "remove that node") map
    to a concrete ID. Falls back silently if the ID doesn't resolve
    — the frontend may have stale state relative to the DAG we just
    sent, and we don't want to block the edit on a mismatch.
    """
    if not selected_node_id:
        return ""
    match = next(
        (n for n in workflow.get("nodes", []) if n.get("id") == selected_node_id),
        None,
    )
    if not match:
        return ""
    label = match.get("label") or match.get("id")
    type_ = match.get("type") or "?"
    return (
        "## Currently selected node (what \"this\" / \"that node\" refers to)\n"
        f"- `{match.get('id')}` · **{type_}** · {label}\n"
        "\n"
    )


def _render_errors(errors: list[dict[str, Any]]) -> str:
    """
    Normalise a mixed list of validator issues / runtime exceptions /
    free-form error strings into a single bulleted section the LLM
    can act on.

    Each item is expected to be a dict with at least one of:
      * `code` — validator error code (e.g. `UNKNOWN_NODE_TYPE`)
      * `node_id` — id of the offending node
      * `message` — human-readable description
      * `severity` — "error" | "warning" | "info"
      * `kind` — "validation" | "runtime" (optional hint)

    We accept plain strings too — they're wrapped as `{"message": str}`
    so the caller doesn't have to pre-shape them.
    """
    if not errors:
        return ""
    lines = ["## Recent errors to fix"]
    for raw in errors:
        if isinstance(raw, str):
            raw = {"message": raw}
        code = raw.get("code")
        node_id = raw.get("node_id") or raw.get("nodeId")
        severity = (raw.get("severity") or "error").upper()
        kind = raw.get("kind")
        message = raw.get("message") or raw.get("detail") or "(no details)"
        prefix_bits = [severity]
        if kind:
            prefix_bits.append(kind)
        if code:
            prefix_bits.append(f"code={code}")
        if node_id:
            prefix_bits.append(f"node={node_id}")
        prefix = " ".join(prefix_bits)
        lines.append(f"- [{prefix}] {message}")
    lines.append("")  # blank line before next section
    return "\n".join(lines) + "\n"
