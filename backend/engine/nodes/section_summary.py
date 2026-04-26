from __future__ import annotations

from pathlib import Path

import pandas as pd
from data_sources import get_registry, split_source_ref

from llm import get_default_adapter

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..signal_contract import signal_flag_column_name


def _column_for_field(field: str, df: pd.DataFrame, source_id: str | None) -> str | None:
    """Resolve field_bindings field to a column present on df (direct name or semantic)."""
    if not field or df is None:
        return None
    if field in df.columns:
        return field
    if source_id:
        ds_id, source_name = split_source_ref(source_id)
        ds = get_registry().get(ds_id)
        if ds is not None:
            phys = ds.resolve_field(field, source_name)
            if phys and phys in df.columns:
                return phys
    return None


def _llm_narrative(prompt: str) -> str:
    # Narrative is prose, so we keep some variability (temperature=0.2)
    # but cap tokens at the value declared in NODE_SPEC constraints.
    # Errors degrade to a placeholder string — we must never fail the
    # whole workflow run because Gemini is momentarily unavailable.
    try:
        return get_default_adapter().single_shot(
            prompt,
            temperature=0.2,
            max_output_tokens=600,
        )
    except Exception as e:
        return f"[LLM unavailable — {e}]"


def handle_section_summary(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    section_name: str = cfg.get("section_name", "section")
    input_name: str = cfg.get("input_name", "execution_data")
    field_bindings: list[dict] = cfg.get("field_bindings", [])
    prompt_template: str = cfg.get(
        "llm_prompt_template",
        "Summarise this surveillance section for {section}:\n{stats}",
    )

    df = ctx.datasets.get(input_name)
    stats: dict = {}

    if df is not None:
        stats["row_count"] = len(df)
        prov = ctx.dataset_provenance.get(input_name)
        for binding in field_bindings:
            field: str = binding.get("field", "")
            agg: str = binding.get("agg", "count")
            col = _column_for_field(field, df, prov)
            if col is None:
                continue
            if agg == "count":
                stats[field] = int(df[col].count())
            elif agg == "sum":
                stats[field] = float(df[col].sum())
            elif agg == "mean":
                stats[field] = round(float(df[col].mean()), 4)
            elif agg == "nunique":
                stats[field] = int(df[col].nunique())
            elif agg == "max":
                stats[field] = str(df[col].max())
            elif agg == "min":
                stats[field] = str(df[col].min())
        _sf = signal_flag_column_name()
        if _sf in df.columns:
            stats["signal_hits"] = int(df[_sf].sum())
        if "_keyword_hit" in df.columns:
            stats["comm_keyword_hits"] = int(df["_keyword_hit"].sum())

    stats_text = "\n".join(f"  • {k}: {v}" for k, v in stats.items())

    # Two-pass render to tolerate LLM-authored prompts that mix {context.xxx} placeholders
    # with the well-known {stats}/{section}/… slots.
    rendered = ctx.inject_template(prompt_template)

    class _SafeMap(dict):
        def __missing__(self, key):  # leave unknown placeholders as-is rather than crash
            return "{" + key + "}"

    prompt = rendered.format_map(_SafeMap(
        stats=stats_text,
        section=section_name,
        disposition=ctx.get("disposition", "REVIEW"),
        trader_id=ctx.get("trader_id", ""),
        currency_pair=ctx.get("currency_pair", ""),
    ))

    ctx.sections[section_name] = {
        "name": section_name,
        "stats": stats,
        "narrative": _llm_narrative(prompt),
        "dataset": input_name,
    }


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_section_summary)
