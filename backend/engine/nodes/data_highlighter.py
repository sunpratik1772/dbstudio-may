"""
DATA_HIGHLIGHTER — annotate rows with colour + label.

Each rule fires a `pandas.DataFrame.eval(condition)` mask against the
target dataset; matching rows get the rule's colour/label. Rules are
applied in declared order — last match wins (so order rules from
generic to specific).

The condition string supports `{ref}` placeholders that resolve to
SCALAR values via the cross-dataset ref grammar BEFORE pandas eval.
This lets a rule key off an upstream signal without copying the value
into config:

    {context.peak_threshold}              → ctx.values['peak_threshold']
    {ladder.symmetry.max}                 → max of a column in another dataset
    {executions._signal_flag.sum}         → sum across a sibling tab

Anything that doesn't resolve cleanly is left as `{...}` in the
expression, which pandas.eval will then refuse — surfacing the typo
instead of silently masking it.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..refs import resolve_template

logger = logging.getLogger(__name__)


DEFAULT_RULES = [
    {"condition": "_signal_flag == True", "colour": "#FF4444", "label": "SIGNAL HIT"},
    {"condition": "_keyword_hit == True", "colour": "#FF8C00", "label": "COMM ALERT"},
    {"condition": "status == 'CANCELLED'", "colour": "#FFD700", "label": "CANCELLED"},
    {"condition": "side == 'SELL'", "colour": "#87CEEB", "label": "SELL"},
    {"condition": "side == 'BUY'", "colour": "#90EE90", "label": "BUY"},
]


def handle_data_highlighter(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "signal_data")
    output_name: str = cfg.get("output_name", f"{input_name}_highlighted")
    rules: list[dict] = cfg.get("rules", DEFAULT_RULES)

    df = ctx.datasets.get(input_name)
    if df is None:
        return

    df = df.copy()
    df["_highlight_colour"] = "#FFFFFF"
    df["_highlight_label"] = ""

    for rule in rules:
        condition: str = rule.get("condition", "False")
        colour: str = rule.get("colour", "#FFFFFF")
        label: str = rule.get("label", "")
        # Resolve cross-dataset scalar refs (e.g. {ladder.symmetry.max})
        # before handing off to pandas.eval.
        resolved = resolve_template(condition, ctx)
        try:
            mask: pd.Series = df.eval(resolved)
            df.loc[mask, "_highlight_colour"] = colour
            df.loc[mask, "_highlight_label"] = label
        except Exception as exc:
            # Skip-and-log: a buggy rule (unresolved ref, syntax error,
            # missing column) must NEVER abort the run. LLM-authored
            # workflows are expected to occasionally produce these.
            logger.warning(
                "DATA_HIGHLIGHTER: skipping rule %r on dataset '%s' — %s",
                condition, input_name, exc,
            )

    ctx.datasets[output_name] = df


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_data_highlighter)
