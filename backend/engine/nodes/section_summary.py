import pandas as pd

from llm import get_default_adapter

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType, Widget


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
    input_name: str = cfg.get("input_name", "trade_data")
    field_bindings: list[dict] = cfg.get("field_bindings", [])
    prompt_template: str = cfg.get(
        "llm_prompt_template",
        "Summarise this surveillance section for {section}:\n{stats}",
    )

    df = ctx.datasets.get(input_name)
    stats: dict = {}

    if df is not None:
        stats["row_count"] = len(df)
        for binding in field_bindings:
            field: str = binding.get("field", "")
            agg: str = binding.get("agg", "count")
            if field not in df.columns:
                continue
            match agg:
                case "count":   stats[field] = int(df[field].count())
                case "sum":     stats[field] = float(df[field].sum())
                case "mean":    stats[field] = round(float(df[field].mean()), 4)
                case "nunique": stats[field] = int(df[field].nunique())
                case "max":     stats[field] = str(df[field].max())
                case "min":     stats[field] = str(df[field].min())
        if "_signal_flag" in df.columns:
            stats["signal_hits"] = int(df["_signal_flag"].sum())
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


NODE_SPEC: NodeSpec = _spec(
    "SECTION_SUMMARY",
    handle_section_summary,
    "Aggregate stats + LLM narrative section",
    color="#DB2777",
    icon="NotebookText",
    input_ports=(
        PortSpec(
            name="dataset",
            type=PortType.DATAFRAME,
            description="Any DataFrame referenced by input_name.",
        ),
        PortSpec(
            name="context",
            type=PortType.OBJECT,
            description=(
                "trader_id, currency_pair, disposition consumed by the prompt "
                "template."
            ),
            optional=True,
        ),
    ),
    output_ports=(
        PortSpec(
            name="section",
            type=PortType.OBJECT,
            description=(
                "{name, stats, narrative, dataset}. Stored under "
                "context.sections[section_name]."
            ),
        ),
    ),
    params=(
        ParamSpec(
            name="section_name",
            type=ParamType.STRING,
            description="Unique section identifier.",
            required=True,
        ),
        ParamSpec(
            name="input_name",
            type=ParamType.INPUT_REF,
            description="Source dataset.",
            required=True,
        ),
        ParamSpec(
            name="field_bindings",
            type=ParamType.ARRAY,
            description=(
                "Array of {field: string, agg: 'count'|'sum'|'mean'|'nunique'|'max'|'min'}."
            ),
            default=[],
            required=False,
        ),
        ParamSpec(
            name="llm_prompt_template",
            type=ParamType.STRING,
            description=(
                "Prompt with {stats}, {section}, {disposition}, {trader_id}, "
                "{currency_pair} placeholders."
            ),
            required=False,
            widget=Widget.TEXTAREA,
        ),
    ),
    constraints=("LLM model: claude-sonnet-4-6, max_tokens: 600.",),
)
