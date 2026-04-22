import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType

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
        try:
            mask: pd.Series = df.eval(condition)
            df.loc[mask, "_highlight_colour"] = colour
            df.loc[mask, "_highlight_label"] = label
        except Exception:
            pass  # skip malformed rule

    ctx.datasets[output_name] = df


NODE_SPEC: NodeSpec = _spec(
    "DATA_HIGHLIGHTER",
    handle_data_highlighter,
    "Apply colour rules to dataset rows",
    color="#9333EA",
    icon="Highlighter",
    config_tags=("output_name",),
    input_ports=(
        PortSpec(
            name="dataset",
            type=PortType.DATAFRAME,
            description="Any DataFrame referenced by input_name.",
        ),
    ),
    output_ports=(
        PortSpec(
            name="highlighted",
            type=PortType.DATAFRAME,
            description=(
                "Input DataFrame + _highlight_colour (hex) + _highlight_label (str). "
                "Stored under ctx.datasets[output_name]."
            ),
        ),
    ),
    params=(
        ParamSpec(
            name="input_name",
            type=ParamType.INPUT_REF,
            description="Source dataset.",
            required=True,
        ),
        ParamSpec(
            name="output_name",
            type=ParamType.STRING,
            description=(
                "Highlighted dataset name (convention: input_name + '_highlighted')."
            ),
            required=True,
        ),
        ParamSpec(
            name="rules",
            type=ParamType.ARRAY,
            description=(
                "Array of {condition: string (pandas eval expression), "
                "colour: string (hex #RRGGBB), label: string}."
            ),
            default=[],
            required=False,
        ),
    ),
    constraints=(
        "Conditions are evaluated with pandas DataFrame.eval().",
        "Rules are applied in order — last matching rule wins.",
        "Rows with no matching rule get colour #FFFFFF and empty label.",
    ),
)
