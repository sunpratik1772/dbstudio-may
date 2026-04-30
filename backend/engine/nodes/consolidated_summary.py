"""
CONSOLIDATED_SUMMARY — final executive narrative for the report.

Reads the small narratives that SECTION_SUMMARY nodes left in
`ctx.sections`, plus the disposition / severity from DECISION_RULE,
and asks the LLM to stitch them into a 5-paragraph executive summary.

Why a separate node: keeping section narratives independent makes
each one cheap to retry and easy to swap. The exec summary just
glues them; it does no fact-pack verification of its own.

The `prompt_context` block on this node is shared with
SECTION_SUMMARY (see engine/prompt_context.py) — set
`prompt_context.vars` to inject any cross-dataset slot you want to
reference in the prompt template.

The `_llm_summary` indirection exists so tests can monkey-patch the
LLM seam to deterministic prose (see test_fro_v2_golden_path.py).
"""
from pathlib import Path

from llm import get_default_adapter

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..prompt_context import build_slots, render_prompt


def _llm_summary(
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1000,
) -> str:
    """LLM seam — monkey-patched in tests to return deterministic text."""
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


def _call_llm_summary(prompt: str, **kwargs) -> str:
    """Call the LLM seam while preserving old one-arg test monkeypatches."""
    try:
        return _llm_summary(prompt, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return _llm_summary(prompt)


_DEFAULT_PROMPT = """You are a senior financial surveillance analyst at a global bank.

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


def handle_consolidated_summary(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    template: str = cfg.get("llm_prompt_template") or _DEFAULT_PROMPT

    section_text = "\n\n".join(
        f"### {name}\n{s['narrative']}" for name, s in ctx.sections.items()
    )

    slots = {
        "section_text": section_text,
        "trader_id":    ctx.get("trader_id", "Unknown"),
        "currency_pair": ctx.get("currency_pair", "N/A"),
        "disposition":  ctx.get("disposition", "REVIEW"),
        "flag_count":   ctx.get("flag_count", 0),
    }
    slots.update(build_slots(cfg.get("prompt_context"), ctx))

    system_prompt = render_prompt(
        cfg.get("system_prompt")
        or (
            "You are a senior financial surveillance analyst. Write executive summaries "
            "that are concise, factual, and tied to the supplied section findings. "
            "Do not invent evidence."
        ),
        ctx,
        **slots,
    )
    prompt = render_prompt(template, ctx, **slots)
    ctx.executive_summary = _call_llm_summary(
        prompt,
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.2)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1000)),
    )
    ctx.set("executive_summary", ctx.executive_summary)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_consolidated_summary)
