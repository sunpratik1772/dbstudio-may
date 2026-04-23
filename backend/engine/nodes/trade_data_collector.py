from pathlib import Path

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _mock_hs_client_order(ctx: RunContext) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 50
    return pd.DataFrame({
        "order_id": [f"ORD{i:05d}" for i in range(n)],
        "trader_id": [ctx.get("trader_id", "T001")] * n,
        "book": [ctx.get("book", "FX-SPOT")] * n,
        "currency_pair": [ctx.get("currency_pair", "EUR/USD")] * n,
        "order_time": pd.date_range("2024-01-15 08:00", periods=n, freq="3min"),
        "order_type": rng.choice(["LIMIT", "MARKET", "STOP"], n),
        "side": rng.choice(["BUY", "SELL"], n),
        "quantity": rng.integers(1_000_000, 10_000_000, n),
        "limit_price": np.round(rng.uniform(1.0850, 1.0950, n), 5),
        "status": rng.choice(
            ["FILLED", "PARTIAL", "CANCELLED", "PENDING"], n, p=[0.60, 0.15, 0.15, 0.10]
        ),
        "venue": rng.choice(["EBS", "Reuters", "Bloomberg", "Voice"], n),
    })


def _mock_hs_execution(ctx: RunContext) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 40
    df = pd.DataFrame({
        "exec_id": [f"EXC{i:05d}" for i in range(n)],
        "order_id": [f"ORD{i:05d}" for i in range(n)],
        "trader_id": [ctx.get("trader_id", "T001")] * n,
        "book": [ctx.get("book", "FX-SPOT")] * n,
        "currency_pair": [ctx.get("currency_pair", "EUR/USD")] * n,
        "exec_time": pd.date_range("2024-01-15 08:01", periods=n, freq="4min"),
        "side": rng.choice(["BUY", "SELL"], n),
        "exec_quantity": rng.integers(1_000_000, 8_000_000, n),
        "exec_price": np.round(rng.uniform(1.0850, 1.0950, n), 5),
        "venue": rng.choice(["EBS", "Reuters", "Bloomberg"], n),
        "counterparty": rng.choice(["CITI", "JPM", "BARC", "UBS", "GS"], n),
        "notional_usd": rng.integers(1_000_000, 10_000_000, n),
    })
    # Hard rule: trade_version is ALWAYS 1 for hs_execution — never from context
    df["trade_version"] = 1
    return df


def handle_trade_data_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    source: str = cfg.get("source", "hs_client_order")
    output_name: str = cfg.get("output_name", "trade_data")
    loop_books: bool = cfg.get("loop_over_books", False)

    # Inject context into query template (audit trail only — not executed against real DB here)
    raw_query: str = cfg.get("query_template", "")
    resolved_query = ctx.inject_template(raw_query)

    # Enforce hard rule: trade_version:1 must be present in all hs_execution queries
    if source == "hs_execution" and "trade_version:1" not in resolved_query:
        resolved_query += " AND trade_version:1"

    # Demo mode: when `mock_csv_path` is configured and the file is
    # readable, bypass the synthetic generator and return the CSV
    # verbatim. Lets the /run/demo endpoint stream a reproducible
    # dataset through the same handler/validator/runtime path that
    # production uses — no branch at the HTTP layer.
    mock_csv_path = cfg.get("mock_csv_path")
    if mock_csv_path:
        import os
        if os.path.isfile(mock_csv_path):
            df = pd.read_csv(mock_csv_path)
        else:
            df = _mock_hs_execution(ctx) if source == "hs_execution" else _mock_hs_client_order(ctx)
    elif source == "hs_execution":
        df = _mock_hs_execution(ctx)
    else:
        df = _mock_hs_client_order(ctx)

    if loop_books:
        books: list = cfg.get("books", [ctx.get("book", "FX-SPOT")])
        df = pd.concat([df.assign(book=b) for b in books], ignore_index=True)

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_count", len(df))
    ctx.set(f"_{output_name}_resolved_query", resolved_query)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_trade_data_collector)
