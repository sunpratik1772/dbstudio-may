"""
SECTION_SUMMARY — compute per-section stats and generate a narrative.

Three modes, selected by the `mode` param:

* templated     — legacy-friendly. Compute stats from `field_bindings`,
                  pass them text-joined as {stats} in the prompt.
* fact_pack_llm — compute NAMED facts from `facts`, pass as JSON under
                  {facts}. After generation, verify each `required_facts`
                  name's value appears verbatim in the narrative. If any
                  are missing, retry once with a stricter prompt.
* event_narrative — order rows, format each via `event_template`, cap at
                    `max_events`, pass the joined list as {events}.

For richer scenarios use the optional `prompt_context` block (see
engine/prompt_context.py) which gives you `vars` (cross-dataset refs)
and a `dataset` block. Anything in prompt_context.vars is exposed under
its own slot name; the serialized dataset is exposed as `{dataset}`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from llm import get_default_adapter

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..prompt_context import build_slots, render_prompt


# ---------------------------------------------------------------------------
# LLM seam — monkey-patched in tests
# ---------------------------------------------------------------------------
def _llm_narrative(
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 600,
) -> str:
    try:
        return get_default_adapter().single_shot(
            prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
        )
    except Exception as e:
        return f"[LLM unavailable — {e}]"


def _call_llm_narrative(prompt: str, **kwargs) -> str:
    """Call the LLM seam while preserving old one-arg test monkeypatches."""
    try:
        return _llm_narrative(prompt, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return _llm_narrative(prompt)


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------
def _templated_stats(df: pd.DataFrame | None, field_bindings: list[dict]) -> dict:
    stats: dict = {}
    if df is None:
        return stats
    stats["row_count"] = len(df)
    for binding in field_bindings or []:
        field = binding.get("field", "")
        agg = binding.get("agg", "count")
        if field not in df.columns:
            continue
        value = None
        match agg:
            case "count":   value = int(df[field].count())
            case "sum":     value = float(df[field].sum())
            case "mean":    value = round(float(df[field].mean()), 4)
            case "nunique": value = int(df[field].nunique())
            case "max":     value = str(df[field].max())
            case "min":     value = str(df[field].min())
        if value is None:
            continue
        stats[field] = value
        stats[f"{field}_{agg}"] = value
    if "_signal_flag" in df.columns:
        stats["signal_hits"] = int(df["_signal_flag"].sum())
    if "_keyword_hit" in df.columns:
        stats["comm_keyword_hits"] = int(df["_keyword_hit"].sum())
    return stats


class _StatsSlot:
    """Prompt slot that supports both {stats} text and {stats.field_agg} refs."""

    def __init__(self, stats: dict) -> None:
        self._stats = stats

    def __str__(self) -> str:
        return "\n".join(f"  • {k}: {v}" for k, v in self._stats.items())

    def __getattr__(self, name: str) -> object:
        if name in self._stats:
            return self._stats[name]
        return "{" + f"stats.{name}" + "}"


def _compute_fact(df: pd.DataFrame, column: str, agg: str) -> object:
    """Reducer dispatch for the fact_pack_llm mode."""
    if df is None or column not in df.columns:
        return None
    series = df[column]
    if agg == "count":         return int(series.count())
    if agg == "sum":           return float(series.sum())
    if agg == "mean":          return round(float(series.mean()), 4) if len(series) else 0.0
    if agg == "nunique":       return int(series.nunique())
    if agg == "max":           return _py_scalar(series.max())
    if agg == "min":           return _py_scalar(series.min())
    if agg == "unique_values": return [_py_scalar(v) for v in series.dropna().unique().tolist()]
    if agg == "row_count":     return int(len(df))
    if agg.startswith("count_where_"):
        token = agg[len("count_where_"):]
        return int((series.astype(str).str.lower() == token.lower()).sum())
    return None


def _py_scalar(v):
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            return v
    return v


def _pack_facts(df: pd.DataFrame | None, facts_cfg: list[dict]) -> dict:
    out: dict = {}
    for entry in facts_cfg or []:
        name = entry.get("name")
        col = entry.get("column", "")
        agg = entry.get("agg", "count")
        if not name:
            continue
        out[name] = _compute_fact(df, col, agg) if df is not None else None
    return out


def _required_missing(facts: dict, required: list[str], narrative: str) -> list[str]:
    """Return names of required facts whose stringified value is absent
    from the narrative. Whole-number floats also match their int form."""
    missing: list[str] = []
    for name in required or []:
        if name not in facts:
            missing.append(name)
            continue
        val = facts[name]
        if val is None:
            continue
        needles: list[str] = [str(val)]
        if isinstance(val, float) and val.is_integer():
            needles.append(str(int(val)))
        if all(n and n not in narrative for n in needles):
            missing.append(name)
    return missing


def _event_lines(df: pd.DataFrame | None, sort_by: str, tmpl: str, cap: int) -> list[str]:
    if df is None or not tmpl:
        return []
    working = df
    if sort_by and sort_by in df.columns:
        working = df.sort_values(sort_by)
    working = working.head(max(0, int(cap or 0)))
    from ..prompt_context import SafeMap  # local import to avoid name-shadow
    lines: list[str] = []
    for row in working.to_dict(orient="records"):
        try:
            lines.append(tmpl.format_map(SafeMap(row)))
        except Exception:
            continue
    return lines


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle_section_summary(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    section_name: str = cfg.get("section_name", "section")
    input_name: str = cfg.get("input_name", "trade_data")
    mode: str = (cfg.get("mode") or "templated").lower()
    prompt_template: str = cfg.get(
        "llm_prompt_template",
        "Summarise this surveillance section for {section}:\n{stats}",
    )
    system_prompt: str = render_prompt(
        cfg.get("system_prompt")
        or (
            "You are a financial surveillance analyst. Write precise, evidence-grounded "
            "section narratives. Do not invent facts. Reference only supplied stats, "
            "facts, events, context, and dataset rows."
        ),
        ctx,
        **build_slots(cfg.get("prompt_context"), ctx),
    )
    model = cfg.get("model")
    temperature = float(cfg.get("temperature", 0.2))
    max_output_tokens = int(cfg.get("max_output_tokens", 600))

    df = ctx.datasets.get(input_name)

    # Common slots available to every mode
    base_slots = {
        "section": section_name,
        "disposition": ctx.get("disposition", "REVIEW"),
        "trader_id": ctx.get("trader_id", ""),
        "currency_pair": ctx.get("currency_pair", ""),
    }
    # User-defined cross-dataset slots from the prompt_context block
    base_slots.update(build_slots(cfg.get("prompt_context"), ctx))

    stats: dict = {}
    narrative: str = ""

    if mode == "fact_pack_llm":
        facts = _pack_facts(df, cfg.get("facts") or [])
        stats = {"row_count": int(len(df)) if df is not None else 0, **facts}
        prompt = render_prompt(prompt_template, ctx, **base_slots,
                               facts=json.dumps(facts, default=str, indent=2))
        narrative = _call_llm_narrative(
            prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        required = list(cfg.get("required_facts") or [])
        missing = _required_missing(facts, required, narrative)
        if missing:
            retry = prompt + (
                "\n\nYour previous response omitted these required facts: "
                + ", ".join(missing)
                + ". Rewrite the narrative so every required fact value "
                "appears verbatim in the text."
            )
            narrative = _call_llm_narrative(
                retry,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

    elif mode == "event_narrative":
        sort_by = cfg.get("sort_by") or ""
        event_tmpl = cfg.get("event_template") or ""
        max_events = int(cfg.get("max_events") or 40)
        lines = _event_lines(df, sort_by, event_tmpl, max_events)
        stats = {
            "row_count": int(len(df)) if df is not None else 0,
            "event_count": len(lines),
        }
        events_block = "\n".join(f"  • {ln}" for ln in lines)
        prompt = render_prompt(prompt_template, ctx, **base_slots, events=events_block)
        narrative = _call_llm_narrative(
            prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    else:  # templated
        stats = _templated_stats(df, cfg.get("field_bindings") or [])
        prompt = render_prompt(prompt_template, ctx, **base_slots, stats=_StatsSlot(stats))
        narrative = _call_llm_narrative(
            prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    ctx.sections[section_name] = {
        "name": section_name,
        "stats": stats,
        "narrative": narrative,
        "dataset": input_name,
    }


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_section_summary)
