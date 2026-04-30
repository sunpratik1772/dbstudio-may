"""
Shared prompt-rendering primitives for any node that calls an LLM.

Consolidates what was previously duplicated across `section_summary.py`
and `consolidated_summary.py`:

* `SafeMap`           — `.format_map()` dict that leaves unknown
                        placeholders intact.
* `render_prompt()`   — two-pass render: ref grammar (refs.resolve_template)
                        then named slot fill (.format_map).
* `build_dataset_block()` — serialize a DataFrame for inclusion as
                        prompt context (csv | json | markdown).
* `build_slots()`     — turn a `prompt_context` config block into the
                        slot dict that `render_prompt` will fill.

The `prompt_context` block (used on SECTION_SUMMARY / CONSOLIDATED_SUMMARY
configs) has the shape:

    prompt_context:
      mode: template | dataset | mixed
      vars:                        # for template / mixed
        peak_symmetry: "{ladder.symmetry.max}"
        last_signal:   "{signals.score.last}"
      dataset:                     # for dataset / mixed
        ref:        ladder         # dataset name in ctx.datasets
        format:     csv            # csv | json | markdown
        max_rows:   200
        columns:    [bucket, symmetry, cancel_ratio]   # optional whitelist

Author writes a `prompt_template` that interpolates whatever vars they
need: "Peak symmetry was {peak_symmetry}. Rows:\n{dataset}"

Keep this file small. New modes only when a real scenario needs them.
"""
from __future__ import annotations

import json
import re
import string
from typing import Any

import pandas as pd

from .context import RunContext
from .refs import resolve_template, resolve_vars


class SafeMap(dict):
    """`dict` for `str.format_map()` that leaves unknown keys intact as
    `{key}` rather than raising KeyError. Lets multiple render passes
    cooperate without losing placeholders."""

    def __getitem__(self, key: str) -> Any:
        return _attr_view(super().__getitem__(key))

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class _AttrDict:
    """Dict wrapper that lets format strings use `{slot.key}` safely."""

    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value

    def __getattr__(self, key: str) -> Any:
        if key not in self._value:
            return "{" + key + "}"
        return _attr_view(self._value[key])

    def __str__(self) -> str:
        return json.dumps(self._value, default=str)


def _attr_view(value: Any) -> Any:
    if isinstance(value, dict):
        return _AttrDict(value)
    return value


def render_prompt(template: str, ctx: RunContext, **slots: Any) -> str:
    """Two-pass render: resolve `{ref}` grammar against ctx, then
    `.format_map` named slots. Order matters — refs run first so that
    they can produce values which then get fed into slots, not the
    other way around."""
    rendered = resolve_template(template, ctx)
    try:
        return rendered.format_map(SafeMap(slots))
    except ValueError as exc:
        if (
            "unmatched '{'" not in str(exc)
            and "Single '}'" not in str(exc)
            and "Invalid format specifier" not in str(exc)
        ):
            raise
        return _render_prompt_lenient(rendered, slots)


def validate_prompt_template(template: str) -> str | None:
    """Return an issue string if a template has malformed literal braces.

    Single refs/placeholders like ``{context.foo}`` are valid. Literal JSON
    examples should escape braces as ``{{`` / ``}}`` or avoid raw braces.
    """
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as exc:
        if (
            "unmatched '{'" in str(exc)
            or "Single '}'" in str(exc)
            or "Invalid format specifier" in str(exc)
        ):
            return str(exc)
        raise
    allowed_field = re.compile(r"^[a-zA-Z_][\w]*(?:\.[\w@]+)*$")
    for _literal, field_name, format_spec, _conversion in parsed:
        if field_name is None:
            continue
        if not allowed_field.fullmatch(field_name):
            return f"invalid placeholder {{{field_name}}}"
        if format_spec:
            return f"unsupported format specifier on {{{field_name}}}: {format_spec!r}"
    return None


def _render_prompt_lenient(rendered: str, slots: dict[str, Any]) -> str:
    """Render known placeholders while leaving malformed literal braces intact."""
    for key, value in slots.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def build_dataset_block(
    df: pd.DataFrame | None,
    *,
    fmt: str = "csv",
    max_rows: int = 200,
    columns: list[str] | None = None,
) -> str:
    if df is None or df.empty:
        return "(no rows)"
    working = df[columns] if columns else df
    if max_rows and len(working) > max_rows:
        working = working.head(max_rows)
    if fmt == "json":
        return working.to_json(orient="records", date_format="iso")
    if fmt == "markdown":
        try:
            return working.to_markdown(index=False)
        except ImportError:
            return working.to_csv(index=False)
    return working.to_csv(index=False)


def build_slots(spec: dict | None, ctx: RunContext) -> dict[str, Any]:
    """Materialise a prompt_context block into a slot dict ready for
    `render_prompt(**slots)`. Shape:

        {
          mode: 'template' | 'dataset' | 'mixed',
          vars: { name: ref_or_literal, ... },
          dataset: { ref, format, max_rows, columns }
        }

    The well-known slot name `{dataset}` is reserved for the serialized
    dataset block when `mode` is dataset or mixed.
    """
    if not spec:
        return {}
    mode = (spec.get("mode") or "template").lower()
    slots: dict[str, Any] = {}

    if mode in ("template", "mixed"):
        for name, value in resolve_vars(spec.get("vars") or {}, ctx).items():
            slots[name] = _stringify(value)

    if mode in ("dataset", "mixed"):
        ds_cfg = spec.get("dataset") or {}
        ref = ds_cfg.get("ref")
        df = ctx.datasets.get(ref) if ref else None
        slots["dataset"] = build_dataset_block(
            df,
            fmt=(ds_cfg.get("format") or "csv").lower(),
            max_rows=int(ds_cfg.get("max_rows") or 200),
            columns=ds_cfg.get("columns") or None,
        )

    return slots


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Series):
        return value.to_string(index=False)
    if isinstance(value, pd.DataFrame):
        return value.to_csv(index=False)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)
