"""
COMMS_COLLECTOR — pulls trader chat / e-comms for the alert window.

Comms live in a different upstream system (Oculus) than orders /
executions (Solr). Keeping the collector split per source system is a
deliberate architectural choice — see the chassis section in
docs/BACKEND_ARCHITECTURE.md.

Two extras beyond a plain row pull:

  • keyword_categories — `{INTENT: [...], TIMING: [...], COVERUP: [...]}`.
    For each row we add `_hit_<CAT>` boolean columns and a
    `_matched_categories` join-string. The downstream
    SECTION_SUMMARY in `event_narrative` mode references the join in
    its event_template.
  • emit_hits_only — when true we publish a sibling dataset
    `<output_name>_hits` containing just rows where any keyword
    matched. The validator wiring check is aware of this naming
    convention; downstream nodes can `input_name: comms_hits`.

Like every collector, mock data ships with the module so workflows are
runnable end-to-end without external systems.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..collector_source import collector_source_ref
from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml

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
    categories: dict[str, list[str]] = cfg.get("keyword_categories") or {}
    emit_hits_only: bool = bool(cfg.get("emit_hits_only", False))
    output_name: str = cfg.get("output_name", "comms_data")

    # Demo mode: prefer the configured CSV when present; otherwise
    # generate synthetic rows. See execution_data_collector for the same
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
        return [kw for kw in keywords if re.search(re.escape(kw), str(text), re.IGNORECASE)]

    def find_categories(text: str) -> list[str]:
        t = str(text)
        hits: list[str] = []
        for cat, kws in (categories or {}).items():
            for kw in kws or []:
                if re.search(re.escape(kw), t, re.IGNORECASE):
                    hits.append(cat)
                    break
        return hits

    df["_matched_keywords"] = df["display_post"].apply(find_hits)
    df["_keyword_hit"] = df["_matched_keywords"].apply(bool)
    if categories:
        df["_matched_categories"] = df["display_post"].apply(find_categories)
        for cat in categories.keys():
            df[f"_hit_{cat}"] = df["_matched_categories"].apply(lambda hs, c=cat: c in hs)

    ctx.datasets[output_name] = df
    ctx.dataset_provenance[output_name] = collector_source_ref("COMMS_COLLECTOR", cfg)
    ctx.set(f"{output_name}_keyword_hits", int(df["_keyword_hit"].sum()))

    if emit_hits_only:
        hits_df = df[df["_keyword_hit"]].reset_index(drop=True)
        ctx.datasets[f"{output_name}_hits"] = hits_df
        ctx.set(f"{output_name}_hits_count", int(len(hits_df)))


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_comms_collector)
