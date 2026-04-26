"""
Cross-dataset reference resolver.

Single shared utility for any node that needs to read values out of the
RunContext by name — used by DATA_HIGHLIGHTER (cross-tab rule grammar),
SECTION_SUMMARY / CONSOLIDATED_SUMMARY (prompt_context vars), and any
future node that templates upstream values.

Reference grammar (intentionally tiny — extend only when a real scenario
needs it):

    {dataset}                  → pd.DataFrame
    {dataset.column}           → pd.Series
    {dataset.column.agg}       → scalar  (agg ∈ AGG_FUNCS)
    {dataset.@row_count}       → int     (special: row count of dataset)
    {context.key}              → ctx.values[key]      (anything)
    {context.key.attr}         → dotted attr/item access on ctx value

Resolvers raise ResolveError on unknown dataset/column/agg so callers can
decide whether to surface as a validation issue or a silent fallback.

KEEP THIS FILE SMALL. New ref kinds need a real scenario to justify
adding to AGG_FUNCS or the parser — we are deliberately *not* building a
generic expression language.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .context import RunContext


class ResolveError(KeyError):
    """Raised when a ref cannot be resolved against the current context."""


AGG_FUNCS: dict[str, callable] = {
    "sum":     lambda s: float(s.sum()),
    "mean":    lambda s: float(s.mean()) if len(s) else 0.0,
    "max":     lambda s: _py_scalar(s.max()) if len(s) else None,
    "min":     lambda s: _py_scalar(s.min()) if len(s) else None,
    "count":   lambda s: int(s.count()),
    "nunique": lambda s: int(s.nunique()),
    "first":   lambda s: _py_scalar(s.iloc[0]) if len(s) else None,
    "last":    lambda s: _py_scalar(s.iloc[-1]) if len(s) else None,
    "any":     lambda s: bool(s.any()),
    "all":     lambda s: bool(s.all()),
}

# {dataset[.col[.agg]]} or {ctx.key[.attr...]} or {dataset.@row_count}
# Public — re-exported as REF_RE so other nodes don't roll their own.
REF_RE = re.compile(r"\{([a-zA-Z_][\w]*(?:\.[\w@]+)*)\}")
_REF_RE = REF_RE  # backwards-compat alias for any internal callers


def _py_scalar(v: Any) -> Any:
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            return v
    return v


def resolve_ref(ref: str, ctx: RunContext) -> Any:
    """Resolve a single ref expression (no braces) against the context.

    Examples:
        resolve_ref("executions", ctx)              → DataFrame
        resolve_ref("executions.notional", ctx)     → Series
        resolve_ref("executions.notional.sum", ctx) → float
        resolve_ref("executions.@row_count", ctx)   → int
        resolve_ref("context.disposition", ctx)     → str
    """
    parts = ref.split(".")
    head = parts[0]

    if head == "context":
        if len(parts) < 2:
            raise ResolveError("context ref needs a key: {context.<key>}")
        value: Any = ctx.get(parts[1])
        for attr in parts[2:]:
            value = _walk(value, attr)
        return value

    if head not in ctx.datasets:
        raise ResolveError(f"unknown dataset '{head}'")

    df = ctx.datasets[head]
    if len(parts) == 1:
        return df

    col = parts[1]
    if col == "@row_count":
        return int(len(df))
    if col not in df.columns:
        raise ResolveError(f"column '{col}' not in dataset '{head}'")

    series = df[col]
    if len(parts) == 2:
        return series

    agg = parts[2]
    if agg not in AGG_FUNCS:
        raise ResolveError(f"unknown agg '{agg}' on {head}.{col}")
    return AGG_FUNCS[agg](series)


def _walk(value: Any, attr: str) -> Any:
    if isinstance(value, dict):
        return value.get(attr)
    return getattr(value, attr, None)


def resolve_template(text: str, ctx: RunContext, *, stringify: bool = True) -> str:
    """Replace every {ref} in `text` with its resolved value.

    Unresolvable refs are left in place (as `{ref}`) so partial templates
    survive and downstream `.format_map` can still fill the rest.
    """
    def repl(m: re.Match) -> str:
        ref = m.group(1)
        try:
            value = resolve_ref(ref, ctx)
        except ResolveError:
            return m.group(0)
        if isinstance(value, pd.DataFrame):
            return f"<dataframe {len(value)}x{len(value.columns)}>" if stringify else value
        if isinstance(value, pd.Series):
            return value.to_string(index=False) if stringify else value
        return str(value) if stringify else value

    return _REF_RE.sub(repl, text)


def resolve_vars(spec: dict[str, str], ctx: RunContext) -> dict[str, Any]:
    """Resolve a `{name: ref_expr}` mapping. Values keep their native type
    (scalar/Series/DataFrame). Unknown refs become `None` — caller decides
    whether that's an error.
    """
    out: dict[str, Any] = {}
    for name, expr in (spec or {}).items():
        if not isinstance(expr, str):
            out[name] = expr  # literal pass-through
            continue
        m = _REF_RE.fullmatch(expr.strip())
        if m:
            try:
                out[name] = resolve_ref(m.group(1), ctx)
            except ResolveError:
                out[name] = None
        else:
            out[name] = resolve_template(expr, ctx)
    return out
