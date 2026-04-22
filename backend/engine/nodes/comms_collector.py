import re

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType, Widget

_MOCK_MESSAGES = [
    "need to move before the fix window opens",
    "client wants to buy 20m eurusd before 4pm",
    "layering the book now, be ready to pull",
    "don't show this order yet — wait for my signal",
    "the benchmark is at 1.0890, let's push through",
    "cover the position quickly before announcement",
    "rotate through the accounts as discussed",
    "market moving, grab liquidity now",
    "that trade was front-run again",
    "normal execution, nothing unusual here",
    "quarterly rebalancing flow expected",
    "client order in line with their mandate",
    "standard hedging activity for the desk",
    "confirmed execution at market",
    "following standard procedure",
    "WM fix approaching, check your position",
    "got the order, executing now",
    "spoofing the offer side to flush stops",
    "step-out to avoid detection",
    "all clear, clean execution",
]


def handle_comms_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    keywords: list[str] = cfg.get("keywords", [
        "fix", "benchmark", "front-run", "ahead", "before the move",
        "cover", "rotate", "push through", "WM fix", "layering", "spoofing",
    ])
    output_name: str = cfg.get("output_name", "comms_data")

    # Demo mode: prefer the configured CSV when present; otherwise
    # generate synthetic rows. See trade_data_collector for the same
    # pattern and rationale.
    mock_csv_path = cfg.get("mock_csv_path")
    if mock_csv_path:
        import os
        if os.path.isfile(mock_csv_path):
            df = pd.read_csv(mock_csv_path)
        else:
            df = None
    else:
        df = None

    if df is None:
        rng = np.random.default_rng(99)
        n = 30
        trader_id = ctx.get("trader_id", "T001")
        df = pd.DataFrame({
            "user": [trader_id] * n,
            "timestamp": pd.date_range("2024-01-15 07:30", periods=n, freq="8min"),
            "display_post": rng.choice(_MOCK_MESSAGES, n),
            "event_type": rng.choice(["CHAT", "VOICE", "EMAIL", "BLOOMBERG_MSG"], n),
        })

    def find_hits(text: str) -> list[str]:
        return [kw for kw in keywords if re.search(re.escape(kw), text, re.IGNORECASE)]

    df["_matched_keywords"] = df["display_post"].apply(find_hits)
    df["_keyword_hit"] = df["_matched_keywords"].apply(bool)

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_keyword_hits", int(df["_keyword_hit"].sum()))


NODE_SPEC: NodeSpec = _spec(
    "COMMS_COLLECTOR",
    handle_comms_collector,
    "Query Oculus comms with keyword scanning",
    color="#059669",
    icon="MessageSquareText",
    config_tags=("output_name",),
    input_ports=(
        PortSpec(
            name="context",
            type=PortType.OBJECT,
            description="Context keys referenced in query_template as {context.xxx}.",
            optional=True,
        ),
    ),
    output_ports=(
        PortSpec(
            name="comms",
            type=PortType.DATAFRAME,
            description=(
                "DataFrame with columns: user, timestamp, display_post, event_type, "
                "_keyword_hit, _matched_keywords. Stored under ctx.datasets[output_name]."
            ),
        ),
        PortSpec(
            name="keyword_hit_count",
            type=PortType.SCALAR,
            description="Total keyword hit count (int). Stored as {output_name}_keyword_hits.",
            optional=True,
        ),
    ),
    params=(
        ParamSpec(
            name="query_template",
            type=ParamType.STRING,
            description="Oculus query with {context.xxx} placeholders.",
            required=True,
            widget=Widget.TEXTAREA,
        ),
        ParamSpec(
            name="keywords",
            type=ParamType.STRING_LIST,
            description="Terms to scan in display_post.",
            default=[],
            required=False,
        ),
        ParamSpec(
            name="output_name",
            type=ParamType.STRING,
            description="Dataset name in ctx.datasets.",
            default="comms",
            required=True,
        ),
        ParamSpec(
            name="mock_csv_path",
            type=ParamType.STRING,
            description=(
                "Demo-mode override: path to a CSV used verbatim instead of "
                "the synthetic generator. Ignored if the file is missing."
            ),
            default="",
            required=False,
        ),
    ),
    constraints=(
        "Always adds _keyword_hit (boolean) and _matched_keywords (list[str]) columns.",
        "Scans display_post field only.",
    ),
)
