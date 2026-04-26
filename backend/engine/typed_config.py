"""
Typed config helper for node handlers.

Today every handler reads its `node["config"]` as a free-form dict:

    cfg = node.get("config", {})
    name = cfg.get("output_name", "execution_data")

That works but has three problems:

1. **No coercion.** If the UI sends `{"loop_over_books": "true"}`
   (string) instead of `True`, handlers silently compare it wrong.
2. **No defaults.** Every handler repeats `cfg.get("x", default)`
   for each param, duplicating values already declared in `ParamSpec`.
3. **No validation at the boundary.** Missing required params are
   caught by `validator.py` pre-flight, but handlers still have to
   guard against absence again for safety.

`typed_config(node, spec)` walks the node's config through the node's
`ParamSpec` tuple and returns a dict where:

  * Every declared param is present (defaults applied).
  * Types are coerced (booleans, ints, arrays of strings).
  * Unknown keys are dropped (avoids typos silently working).

It is **not** a replacement for `validator.py` — the validator runs
pre-flight and returns structured issues. `typed_config` is the
runtime guard: it trusts the validator has already run and just
applies coercion + defaults.

Migration path:

    # old
    def handle_x(node, ctx):
        cfg = node.get("config", {})
        loop = cfg.get("loop_over_books", False)

    # new (same handler, one helper call)
    def handle_x(node, ctx):
        cfg = typed_config(node, NODE_SPEC)
        loop = cfg["loop_over_books"]  # always a bool, always present

Handlers can adopt this incrementally; the old pattern continues to
work untouched.
"""
from __future__ import annotations

from typing import Any

from .node_spec import NodeSpec
from .ports import ParamSpec, ParamType


def _coerce(value: Any, spec: ParamSpec) -> Any:
    if value is None:
        return spec.default
    if spec.type is ParamType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1")
        return bool(value)
    if spec.type is ParamType.INTEGER:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return spec.default
    if spec.type is ParamType.NUMBER:
        try:
            return float(value)
        except (TypeError, ValueError):
            return spec.default
    if spec.type is ParamType.STRING_LIST:
        if isinstance(value, list):
            return [str(x) for x in value]
        if isinstance(value, str) and value:
            return [s.strip() for s in value.split(",") if s.strip()]
        return list(spec.default) if isinstance(spec.default, list) else []
    if spec.type is ParamType.ARRAY:
        return value if isinstance(value, list) else (spec.default or [])
    if spec.type is ParamType.OBJECT:
        return value if isinstance(value, dict) else (spec.default or {})
    # STRING, ENUM, INPUT_REF, CODE — return as-is; validator has
    # already enforced enum membership pre-flight.
    return value


def typed_config(node: dict, spec: NodeSpec) -> dict:
    """
    Return a dict keyed by every declared param name, with defaults
    applied and types coerced. Unknown keys in `node["config"]` are
    dropped.
    """
    raw = node.get("config") or {}
    out: dict[str, Any] = {}
    for p in spec.params:
        out[p.name] = _coerce(raw.get(p.name), p)
    return out


__all__ = ["typed_config"]
