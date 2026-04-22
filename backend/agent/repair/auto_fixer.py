"""
Deterministic, LLM-free repairs for validator errors we can fix
mechanically. Runs BEFORE the LLM repair loop so we don't waste an
expensive round-trip on formatting sins and hard-rule injections the
model consistently gets wrong.

Each rule is keyed off a validator error `code` and a small, targeted
transform on the workflow dict. Rules are *idempotent* — running them
twice is a no-op.

A rule returns True when it modified the graph, False otherwise. The
harness iterates until no rule modifies anything or the modification
log exceeds a safety cap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.validation_codes import ValidationErrorCode


# --------------------------------------------------------------------------
# Report type
# --------------------------------------------------------------------------
@dataclass
class AutoFixReport:
    """Summary of what the auto-fixer did on a single pass."""

    applied: list[str] = field(default_factory=list)
    """Human-readable descriptions: e.g. 'n02.query_template: added trade_version:1'."""

    @property
    def changed(self) -> bool:
        return len(self.applied) > 0


# --------------------------------------------------------------------------
# Individual fix rules
# --------------------------------------------------------------------------
# Each rule is `(error_code, fn(workflow, error, report) -> bool)`.
# The bool indicates whether the rule applied (for idempotency tracking).
# --------------------------------------------------------------------------
_NODE_ID_RE = re.compile(r"^n\d+")


def _find_node(workflow: dict, node_id: str) -> dict | None:
    for n in workflow.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") == node_id:
            return n
    return None


def _fix_missing_trade_version(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    node = _find_node(workflow, error.get("node_id") or "")
    if not node:
        return False
    cfg = node.setdefault("config", {})
    qt = cfg.get("query_template") or ""
    if "trade_version:1" in qt:
        return False
    # Prepend so it's always at the top of the AND chain; surveillance
    # teams expect it as the first clause for readability.
    cfg["query_template"] = f"trade_version:1 AND {qt}" if qt.strip() else "trade_version:1"
    report.applied.append(
        f"{node['id']}.query_template: prepended 'trade_version:1' (surveillance hard rule)"
    )
    return True


def _fix_missing_label(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    node = _find_node(workflow, error.get("node_id") or "")
    if not node or node.get("label"):
        return False
    # Derive a reasonable default from the type.
    t = node.get("type") or "node"
    label = t.replace("_", " ").title()
    node["label"] = label
    report.applied.append(f"{node['id']}.label: set to '{label}'")
    return True


def _fix_wrong_entry_id(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    """If ALERT_TRIGGER doesn't have id 'n01', rename it and rewrite edges."""
    current_id = error.get("node_id")
    if not current_id or current_id == "n01":
        return False
    node = _find_node(workflow, current_id)
    if not node or node.get("type") != "ALERT_TRIGGER":
        return False
    # Don't overwrite an existing n01; that would collide.
    if _find_node(workflow, "n01") is not None:
        return False
    node["id"] = "n01"
    for edge in workflow.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        if edge.get("from") == current_id:
            edge["from"] = "n01"
        if edge.get("to") == current_id:
            edge["to"] = "n01"
        # ReactFlow form:
        if edge.get("source") == current_id:
            edge["source"] = "n01"
        if edge.get("target") == current_id:
            edge["target"] = "n01"
    report.applied.append(f"ALERT_TRIGGER id: '{current_id}' → 'n01'")
    return True


def _normalize_edge_schema(workflow: dict) -> bool:
    """Convert {source,target} edges to {from,to}. Not tied to a specific error
    code; called unconditionally because it fixes a whole class of validator
    complaints at once (and the dag_runner would otherwise happily accept
    {source,target} — see `_edge_endpoints` — but other consumers won't)."""
    changed = False
    edges = workflow.get("edges") or []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if "from" not in edge and "source" in edge:
            edge["from"] = edge.pop("source")
            changed = True
        if "to" not in edge and "target" in edge:
            edge["to"] = edge.pop("target")
            changed = True
    return changed


def _fix_bad_param_type_empty_array(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    """When an ARRAY param is missing / wrong-typed and the validator flagged
    it, fall back to an empty list. Only applies to params whose field path
    we can recover from the error — and only when the current value is
    `None` (removing a user-typed value silently would be surprising)."""
    field = error.get("field") or ""
    node_id = error.get("node_id") or ""
    if not field.startswith("config.") or not node_id:
        return False
    param_name = field[len("config."):]
    message = error.get("message") or ""
    if "should be an array" not in message:
        return False
    node = _find_node(workflow, node_id)
    if not node:
        return False
    cfg = node.setdefault("config", {})
    if cfg.get(param_name) is None:
        cfg[param_name] = []
        report.applied.append(f"{node_id}.{param_name}: initialised to []")
        return True
    return False


def _fix_missing_required_param_known(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    """Fill in defaults for the small set of required params with an obvious
    canonical default. Anything ambiguous is left for the LLM to resolve —
    this function intentionally does not try to be clever."""
    field = error.get("field") or ""
    node_id = error.get("node_id") or ""
    if not field.startswith("config.") or not node_id:
        return False
    param_name = field[len("config."):]
    node = _find_node(workflow, node_id)
    if not node:
        return False
    cfg = node.setdefault("config", {})
    if cfg.get(param_name) not in (None, ""):
        return False

    # Only apply safe, type-specific defaults.
    node_type = node.get("type")
    defaults: dict[tuple[str, str], Any] = {
        ("REPORT_OUTPUT", "tabs"): [],
        ("DATA_HIGHLIGHTER", "rules"): [],
        ("SECTION_SUMMARY", "field_bindings"): [],
    }
    default = defaults.get((node_type or "", param_name))
    if default is None:
        return False
    cfg[param_name] = default
    report.applied.append(
        f"{node_id}.{param_name}: defaulted to {default!r} (known-safe fallback)"
    )
    return True


# Table driving the dispatcher. Keys are `ValidationErrorCode` members
# (str-enum) so typos trip at import time, and IDE tooling can jump to
# the definition from either direction.
_RULES: dict[ValidationErrorCode, Callable[[dict, dict, AutoFixReport], bool]] = {
    ValidationErrorCode.MISSING_TRADE_VERSION: _fix_missing_trade_version,
    ValidationErrorCode.MISSING_LABEL: _fix_missing_label,
    ValidationErrorCode.WRONG_ENTRY_ID: _fix_wrong_entry_id,
    ValidationErrorCode.BAD_PARAM_TYPE: _fix_bad_param_type_empty_array,
    ValidationErrorCode.MISSING_REQUIRED_PARAM: _fix_missing_required_param_known,
}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
class AutoFixer:
    """Applies deterministic repairs to a workflow based on validator errors.

    `fix()` mutates the workflow in place and returns a report. Callers
    re-run the validator afterwards to see what remains.
    """

    def fix(self, workflow: dict, errors: list[dict]) -> AutoFixReport:
        report = AutoFixReport()
        if not isinstance(workflow, dict):
            return report

        # Normalise edge schema unconditionally — cheap and frequently fires.
        if _normalize_edge_schema(workflow):
            report.applied.append("edges: converted {source,target} → {from,to}")

        # Apply per-error rules. Each rule is idempotent so re-entry is
        # safe if the caller calls fix() multiple times.
        for err in errors or []:
            code = err.get("code")
            rule = _RULES.get(code) if code else None
            if not rule:
                continue
            try:
                rule(workflow, err, report)
            except Exception:  # pragma: no cover — defensive; a bad rule must not abort the run
                continue
        return report
