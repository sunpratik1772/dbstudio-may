"""
ORDER_COLLECTOR — pulls order-lifecycle rows (hs_client_order).

Differs from TRADE_DATA_COLLECTOR in that it is *orders-only* (no
executions) and always exposes the canonical order-lifecycle schema
declared in data_sources/metadata/orders.yaml:

    order_id, trader_id, book, instrument, side, order_time,
    event_time, quantity, limit_price, status, venue

Scenarios that need order lifecycle (FRO, FISL spoofing, layering,
wash-trade pairing) build on top of this collector. Executions come
from TRADE_DATA_COLLECTOR(source=hs_execution).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..refs import resolve_template
from ._window import apply_window_filter


_STATUSES = ("NEW", "PLACED", "AMENDED", "PARTIAL", "FILLED", "CANCELLED")


def _mock_orders(ctx: RunContext, n: int = 60) -> pd.DataFrame:
    """Generate a deterministic, realistic order-lifecycle dataset.

    Two books so GROUP_BY_BOOK has something to fan out over; statuses
    cover the full lifecycle so lifecycle_event narrative nodes have
    interesting events to narrate.
    """
    rng = np.random.default_rng(17)
    trader = ctx.get("trader_id", "T001")
    books = ["FX-SPOT-EU", "FX-SPOT-APAC"]
    instruments = [ctx.get("currency_pair", "EUR/USD"), "GBP/USD"]
    order_times = pd.date_range("2024-01-15 08:00", periods=n, freq="2min")
    return pd.DataFrame({
        "order_id": [f"ORD{i:05d}" for i in range(n)],
        "trader_id": [trader] * n,
        "book": rng.choice(books, n),
        "instrument": rng.choice(instruments, n),
        "side": rng.choice(["BUY", "SELL"], n),
        "order_time": order_times,
        "event_time": order_times + pd.to_timedelta(rng.integers(0, 120, n), unit="s"),
        "quantity": rng.integers(1_000_000, 10_000_000, n),
        "limit_price": np.round(rng.uniform(1.0850, 1.0950, n), 5),
        "status": rng.choice(_STATUSES, n, p=[0.10, 0.20, 0.10, 0.10, 0.35, 0.15]),
        "venue": rng.choice(["EBS", "Reuters", "Bloomberg"], n),
    })


def handle_order_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    output_name: str = cfg.get("output_name", "orders")
    trader_filter_key: str = cfg.get("trader_filter_key", "trader_id") or ""

    raw_query: str = cfg.get("query_template", "")
    resolved_query = resolve_template(raw_query, ctx) if raw_query else ""

    # Demo mode: use a CSV verbatim when configured and readable; else synthesize.
    mock_csv_path = cfg.get("mock_csv_path")
    df: pd.DataFrame | None = None
    if mock_csv_path and os.path.isfile(mock_csv_path):
        df = pd.read_csv(mock_csv_path)
    if df is None:
        df = _mock_orders(ctx)

    # Optional trader filter — keeps the collector self-contained so
    # downstream nodes don't have to re-apply the filter.
    if trader_filter_key:
        trader_val = ctx.get(trader_filter_key)
        if trader_val is not None and "trader_id" in df.columns:
            df = df.loc[df["trader_id"] == trader_val].reset_index(drop=True)

    # Shared window-filter helper — same contract every collector uses.
    df = apply_window_filter(df, ctx, cfg=cfg, time_col="order_time")

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_count", len(df))
    if resolved_query:
        ctx.set(f"_{output_name}_resolved_query", resolved_query)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_order_collector)
