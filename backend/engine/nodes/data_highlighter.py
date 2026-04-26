from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..signal_contract import signal_flag_column_name


def _default_highlight_rules() -> list[dict]:
    """Defaults use the same flag column name as SIGNAL_CALCULATOR YAML."""
    f = signal_flag_column_name()
    return [
        {"condition": f"{f} == True", "colour": "#FF4444", "label": "SIGNAL HIT"},
        {"condition": "_keyword_hit == True", "colour": "#FF8C00", "label": "COMM ALERT"},
        {"condition": "status == 'CANCELLED'", "colour": "#FFD700", "label": "CANCELLED"},
        {"condition": "side == 'SELL'", "colour": "#87CEEB", "label": "SELL"},
        {"condition": "side == 'BUY'", "colour": "#90EE90", "label": "BUY"},
    ]


def handle_data_highlighter(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "signal_data")
    output_name: str = cfg.get("output_name", f"{input_name}_highlighted")
    rules: list[dict] = cfg.get("rules", _default_highlight_rules())

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
        try:
            mask: pd.Series = df.eval(condition)
            df.loc[mask, "_highlight_colour"] = colour
            df.loc[mask, "_highlight_label"] = label
        except Exception:
            pass  # skip malformed rule

    ctx.datasets[output_name] = df


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_data_highlighter)
