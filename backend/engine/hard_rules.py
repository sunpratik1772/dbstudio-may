"""
Declarative registry of workflow hard-rules.

Before this module, `_validate_hard_rules` in `validator.py` was an
if/elif chain. Adding a rule meant editing validator.py (which any
new rule should never need to touch), and the rules weren't
discoverable without reading the function body.

Now each rule is a small object with:
  * `code`        — the ValidationErrorCode it can emit
  * `node_type`   — which node it applies to (or None for DAG-level)
  * `check(...)`  — pure function: (node, dag, result) -> None

Rules register themselves via `@register_hard_rule`. The validator
iterates the registry, filters by `node_type`, and calls `check`.
That's it — no branching in `validator.py`.

Extending the engine with a new rule is a one-file change: drop a
new function decorated with `@register_hard_rule` into
`engine/hard_rules/<name>.py` (or right below the existing ones for
tiny rules) and the validator will pick it up on next import.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from .node_type_ids import EXECUTION_DATA_COLLECTOR, SIGNAL_CALCULATOR
from .validation_codes import ValidationErrorCode


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
class _ResultSink(Protocol):
    """Duck-typed subset of `ValidationResult` the rules need.

    Defined as a Protocol so rules stay decoupled from `validator.py` —
    otherwise we'd have a circular import (validator → hard_rules →
    validator).
    """

    def add(
        self,
        code: ValidationErrorCode,
        message: str,
        *,
        severity: str = "error",
        node_id: str | None = None,
        field: str | None = None,
    ) -> None: ...


HardRuleCheck = Callable[[dict, dict, _ResultSink], None]
"""Signature: (node, dag, result) -> None.

`node` is the current node dict, `dag` is the full workflow (for
cross-node checks), `result` is the collector. Rules emit 0..N
issues via `result.add(...)` and never raise.
"""


@dataclass(frozen=True)
class HardRule:
    """One declarative hard rule.

    `node_type=None` means the rule runs for every node. `code` is
    declarative metadata — the rule itself decides the severity and
    can emit OTHER codes too (see `_signal_calc_script` which emits
    both MISSING_SCRIPT and SCRIPT_PATH_ONLY). The field exists so
    tooling can cross-reference the primary code the rule guards.
    """

    name: str
    code: ValidationErrorCode
    node_type: str | None
    check: HardRuleCheck
    description: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: list[HardRule] = []


def register_hard_rule(
    *,
    name: str,
    code: ValidationErrorCode,
    node_type: str | None = None,
    description: str = "",
) -> Callable[[HardRuleCheck], HardRuleCheck]:
    """
    Decorator that registers a hard-rule check.

    Usage:
        @register_hard_rule(
            name="trade_version_pin",
            code=ValidationErrorCode.MISSING_TRADE_VERSION,
            node_type="EXECUTION_DATA_COLLECTOR",
        )
        def _rule(node, dag, result): ...

    Returns the original callable so tests can import it directly.
    """
    def _decorator(fn: HardRuleCheck) -> HardRuleCheck:
        _REGISTRY.append(
            HardRule(
                name=name,
                code=code,
                node_type=node_type,
                check=fn,
                description=description,
            )
        )
        return fn

    return _decorator


def all_hard_rules() -> Iterable[HardRule]:
    """Read-only view of registered rules (ordering = registration order)."""
    return tuple(_REGISTRY)


def run_hard_rules(
    nodes_by_id: dict[str, dict],
    dag: dict,
    result: _ResultSink,
) -> None:
    """
    Execute every registered rule against the DAG.

    Rules are pure; any exception is suppressed to protect the overall
    validation pass (a buggy new rule should not prevent every OTHER
    rule from running and reporting its issue).
    """
    for rule in _REGISTRY:
        for nid, node in nodes_by_id.items():
            if rule.node_type is not None and node.get("type") != rule.node_type:
                continue
            config = node.get("config")
            # Normalise `config` before handing it to the rule so every
            # check can assume a dict without guarding for None / non-dict.
            # Structural validation in _validate_node_config already
            # emitted BAD_CONFIG for the weird cases.
            if config is not None and not isinstance(config, dict):
                continue
            try:
                rule.check(node, dag, result)
            except Exception:
                # A rule crash MUST NOT take down validation. Future
                # work: funnel this into a diagnostics channel so
                # operators notice silent rule failures.
                continue


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------
# These are the rules that used to live hardcoded inside
# `_validate_hard_rules`. Each one is now a declarative registration
# that tests can mock, disable, or assert on individually.


@register_hard_rule(
    name="trade_version_pin",
    code=ValidationErrorCode.MISSING_TRADE_VERSION,
    node_type=EXECUTION_DATA_COLLECTOR,
    description=(
        "Surveillance integrity: hs_execution queries MUST pin "
        "trade_version:1 to avoid joining superseded amendments."
    ),
)
def _rule_trade_version_pin(node: dict, dag: dict, result: _ResultSink) -> None:
    config = node.get("config") or {}
    if config.get("source") not in {"hs_execution", "hs_trades", "hs_orders_and_executions"}:
        return
    qt = config.get("query_template") or ""
    if "trade_version:1" not in qt:
        result.add(
            ValidationErrorCode.MISSING_TRADE_VERSION,
            f"Node '{node.get('id')}' targets hs_execution but query_template does not"
            " hard-code 'trade_version:1'. This is a surveillance integrity rule.",
            node_id=node.get("id"),
            field="config.query_template",
        )


@register_hard_rule(
    name="signal_calculator_script_presence",
    code=ValidationErrorCode.MISSING_SCRIPT,
    node_type=SIGNAL_CALCULATOR,
    description=(
        "In `upload_script` mode the calculator needs either inline "
        "content (runs anywhere) or a path (best-effort; warns)."
    ),
)
def _rule_signal_calc_script(node: dict, dag: dict, result: _ResultSink) -> None:
    config = node.get("config") or {}
    if config.get("mode") != "upload_script":
        return
    if os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() not in {"1", "true", "yes"}:
        result.add(
            ValidationErrorCode.UPLOAD_SCRIPT_DISABLED,
            f"Node '{node.get('id')}' uses mode='upload_script', but "
            "DBSHERPA_ALLOW_UPLOAD_SCRIPT is not enabled. Use mode='configure' "
            "with a built-in signal_type, or ask a platform engineer to enable scripts.",
            node_id=node.get("id"),
            field="config.mode",
        )
    script_content = config.get("script_content")
    script_path = config.get("script_path")
    if not script_content and not script_path:
        result.add(
            ValidationErrorCode.MISSING_SCRIPT,
            f"Node '{node.get('id')}' uses mode='upload_script' but supplies neither"
            " script_content nor script_path.",
            node_id=node.get("id"),
            field="config",
        )
    elif not script_content:
        result.add(
            ValidationErrorCode.SCRIPT_PATH_ONLY,
            f"Node '{node.get('id')}' references a script_path but does not include inline"
            " script_content. Runs may fail if the path isn't available on the"
            " execution host.",
            severity="warning",
            node_id=node.get("id"),
            field="config.script_path",
        )

__all__ = [
    "HardRule",
    "HardRuleCheck",
    "all_hard_rules",
    "register_hard_rule",
    "run_hard_rules",
]
