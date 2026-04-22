from llm import get_default_adapter

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType, Widget


def _llm_summary(prompt: str) -> str:
    try:
        return get_default_adapter().single_shot(
            prompt,
            temperature=0.2,
            max_output_tokens=1000,
        )
    except Exception as e:
        return f"[LLM unavailable — {e}]"


def handle_consolidated_summary(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    prompt_template: str = cfg.get("llm_prompt_template", "")

    section_text = "\n\n".join(
        f"### {name}\n{s['narrative']}" for name, s in ctx.sections.items()
    )

    trader_id = ctx.get("trader_id", "Unknown")
    currency_pair = ctx.get("currency_pair", "N/A")
    disposition = ctx.get("disposition", "REVIEW")
    flag_count = ctx.get("flag_count", 0)

    default_prompt = f"""You are a senior financial surveillance analyst at a global bank.

Write a concise executive summary for the following trade surveillance alert.

Trader ID: {trader_id}
Instrument: {currency_pair}
Disposition: {disposition}
Total Signal Flags: {flag_count}

Section Findings:
{section_text}

Structure your summary across these paragraphs:
1. Alert overview and key finding
2. Trading pattern analysis
3. Communications intelligence (if relevant)
4. Risk assessment and recommended action
5. Evidence summary

Be precise, analytical, and reference specific statistics from the section findings."""

    if prompt_template:
        rendered = ctx.inject_template(prompt_template)

        class _SafeMap(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        prompt = rendered.format_map(_SafeMap(
            section_text=section_text,
            trader_id=trader_id,
            currency_pair=currency_pair,
            disposition=disposition,
            flag_count=flag_count,
        ))
    else:
        prompt = default_prompt

    ctx.executive_summary = _llm_summary(prompt)
    ctx.set("executive_summary", ctx.executive_summary)


NODE_SPEC: NodeSpec = _spec(
    "CONSOLIDATED_SUMMARY",
    handle_consolidated_summary,
    "LLM executive summary across all sections",
    color="#B45309",
    icon="FileStack",
    input_ports=(
        PortSpec(
            name="sections",
            type=PortType.OBJECT,
            description=(
                "All section objects produced by upstream SECTION_SUMMARY nodes "
                "(context.sections)."
            ),
        ),
    ),
    output_ports=(
        PortSpec(
            name="executive_summary",
            type=PortType.TEXT,
            description=(
                "Multi-paragraph executive summary. Stored as "
                "context.executive_summary."
            ),
        ),
    ),
    params=(
        ParamSpec(
            name="llm_prompt_template",
            type=ParamType.STRING,
            description=(
                "Custom prompt with {section_text}, {trader_id}, "
                "{currency_pair}, {disposition}, {flag_count} placeholders. "
                "Falls back to the built-in template when empty."
            ),
            required=False,
            widget=Widget.TEXTAREA,
        ),
    ),
    constraints=(
        "LLM model: claude-sonnet-4-6, max_tokens: 1000.",
        "Must run after all SECTION_SUMMARY nodes.",
    ),
)
