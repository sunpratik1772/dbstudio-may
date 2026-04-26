"""
DECISION_RULE — turn signal flags into a disposition + severity.

Two evaluation modes:

* Threshold mode (default): compare `flag_count` against
  `escalate_threshold` / `review_threshold`. Disposition follows the
  classic ladder ESCALATE > REVIEW > DISMISS.
* Rule mode: a `rules` list of `{name, when, severity, disposition}`.
  Rules are evaluated top-to-bottom; the first match wins. `when` is
  any cross-dataset ref expression (`{executions._signal_flag.sum}`,
  `{ladder.symmetry.max}`, `{context.flag_count}`) that resolves to a
  truthy/comparable value, optionally followed by a comparison
  operator + literal. Threshold mode is implied when `rules` is empty.

Outputs (all stored on ctx.values too):
    disposition     ESCALATE | REVIEW | DISMISS
    severity        CRITICAL | HIGH | MEDIUM | LOW
    score           float 0..1   (flag_count / escalate_threshold, clamped)
    output_branch   str          (override via output_branches map)
    matched_rule    str | ""     (which rule fired, when in rule mode)
"""
from __future__ import annotations

import operator
import re
from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..refs import REF_RE, ResolveError, resolve_ref


_OPS: dict[str, callable] = {
    ">=": operator.ge, "<=": operator.le,
    "==": operator.eq, "!=": operator.ne,
    ">":  operator.gt, "<":  operator.lt,
}

_COMPARISON_RE = re.compile(
    r"^\s*\{([^}]+)\}\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$"
)

# Default severity per disposition. Tunable via params.severity_map.
_DEFAULT_SEVERITY = {
    "ESCALATE": "HIGH",
    "REVIEW":   "MEDIUM",
    "DISMISS":  "LOW",
}


def _coerce(literal: str) -> Any:
    s = literal.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s.strip("'\"")


def _eval_when(expr: str, ctx: RunContext) -> bool:
    """Evaluate a `when` expression: either `{ref} OP literal` or a bare
    `{ref}` (truthy)."""
    m = _COMPARISON_RE.match(expr)
    if m:
        ref, op, rhs = m.group(1), m.group(2), m.group(3)
        try:
            lhs = resolve_ref(ref, ctx)
        except ResolveError:
            return False
        return bool(_OPS[op](lhs, _coerce(rhs)))
    bare = REF_RE.fullmatch(expr.strip())
    if bare:
        try:
            return bool(resolve_ref(bare.group(1), ctx))
        except ResolveError:
            return False
    return False


def _flag_count(input_name: str, ctx: RunContext) -> int:
    df = ctx.datasets.get(input_name)
    if df is not None and "_signal_flag" in df.columns:
        return int(df["_signal_flag"].sum())
    return int(ctx.get(f"{input_name}_flag_count", 0))


def handle_decision_rule(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "signal_data")
    escalate_threshold: int = int(cfg.get("escalate_threshold", 5))
    review_threshold: int = int(cfg.get("review_threshold", 1))
    output_branches: dict = cfg.get("output_branches", {})
    severity_map: dict = {**_DEFAULT_SEVERITY, **(cfg.get("severity_map") or {})}
    rules: list[dict] = cfg.get("rules") or []

    flag_count = _flag_count(input_name, ctx)
    # Expose flag_count BEFORE rule eval so {context.flag_count} works in rules.
    ctx.set("flag_count", flag_count)

    matched_rule = ""
    severity_override: str | None = None
    disposition_override: str | None = None

    if rules:
        for rule in rules:
            when = rule.get("when") or ""
            if when and _eval_when(when, ctx):
                matched_rule = rule.get("name", "")
                severity_override = rule.get("severity")
                disposition_override = rule.get("disposition")
                break

    if disposition_override:
        disposition = disposition_override
    elif flag_count >= escalate_threshold:
        disposition = "ESCALATE"
    elif flag_count >= review_threshold:
        disposition = "REVIEW"
    else:
        disposition = "DISMISS"

    severity = severity_override or severity_map.get(disposition, "LOW")
    score = min(1.0, flag_count / escalate_threshold) if escalate_threshold > 0 else 0.0
    branch = output_branches.get(disposition, disposition)

    ctx.disposition = disposition
    ctx.output_branch = branch
    ctx.set("disposition", disposition)
    ctx.set("output_branch", branch)
    ctx.set("severity", severity)
    ctx.set("score", round(score, 4))
    ctx.set("matched_rule", matched_rule)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_decision_rule)
