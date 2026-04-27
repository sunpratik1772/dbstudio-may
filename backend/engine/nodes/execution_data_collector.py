"""
EXECUTION_DATA_COLLECTOR — the single Solr-backed trade/order collector.

The node's `source` dropdown is populated from
`data_sources/metadata/trades.yaml`, not hard-coded in the frontend.
Use `source=hs_client_order` for order-lifecycle rows and
`source=hs_execution` / `hs_trades` / etc. for fills/trades/quotes.

Hard rule (enforced in engine/hard_rules.py): when `source ==
'hs_execution'`, the query_template MUST pin `trade_version:1` so
we don't accidentally join superseded amendments. The handler
appends it defensively too, but the validator-level rule catches
buggy queries before runtime.

Like the other collectors:
  • Honours the shared `window_key` (filters by exec_time / order_time).
  • Ships a deterministic mock generator so workflows run end-to-end
    offline; `mock_csv_path` lets demos pin a CSV.
"""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml
from ..refs import resolve_template


def _mock_hs_client_order(ctx: RunContext) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 50
    return pd.DataFrame({
        "order_id": [f"ORD{i:05d}" for i in range(n)],
        "trader_id": [ctx.get("trader_id", "T001")] * n,
        "book": [ctx.get("book", "FX-SPOT")] * n,
        "currency_pair": [ctx.get("currency_pair", "EUR/USD")] * n,
        "instrument": [ctx.get("currency_pair", "EUR/USD")] * n,
        "order_time": pd.date_range("2024-01-15 08:00", periods=n, freq="3min"),
        "event_time": pd.date_range("2024-01-15 08:00", periods=n, freq="3min")
        + pd.to_timedelta(rng.integers(0, 120, n), unit="s"),
        "instance_id": rng.choice(["INST-1", "INST-2", "INST-3"], n),
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


def _mock_hs_trades(ctx: RunContext) -> pd.DataFrame:
    rng = np.random.default_rng(43)
    n = 35
    return pd.DataFrame({
        "trade_id": [f"TRD{i:05d}" for i in range(n)],
        "trader_id": [ctx.get("trader_id", "T001")] * n,
        "book": [ctx.get("book", "FX-SPOT")] * n,
        "currency_pair": [ctx.get("currency_pair", "EUR/USD")] * n,
        "trade_time": pd.date_range("2024-01-15 08:02", periods=n, freq="5min"),
        "side": rng.choice(["BUY", "SELL"], n),
        "trade_quantity": rng.integers(1_000_000, 8_000_000, n),
        "trade_price": np.round(rng.uniform(1.0850, 1.0950, n), 5),
        "counterparty": rng.choice(["CITI", "JPM", "BARC", "UBS", "GS"], n),
        "trade_version": [1] * n,
    })


def _mock_hs_orders_and_executions(ctx: RunContext) -> pd.DataFrame:
    orders = _mock_hs_client_order(ctx).head(40).reset_index(drop=True)
    execs = _mock_hs_execution(ctx).reset_index(drop=True)
    return pd.DataFrame({
        "order_id": orders["order_id"],
        "exec_id": execs["exec_id"],
        "trader_id": orders["trader_id"],
        "book": orders["book"],
        "currency_pair": orders["currency_pair"],
        "order_time": orders["order_time"],
        "exec_time": execs["exec_time"],
        "side": orders["side"],
        "quantity": orders["quantity"],
        "exec_quantity": execs["exec_quantity"],
        "limit_price": orders["limit_price"],
        "exec_price": execs["exec_price"],
        "status": orders["status"],
        "trade_version": [1] * len(execs),
    })


def _mock_hs_quotes(ctx: RunContext) -> pd.DataFrame:
    rng = np.random.default_rng(44)
    n = 50
    mid = np.round(rng.uniform(1.0850, 1.0950, n), 5)
    spread = np.round(rng.uniform(0.00005, 0.00020, n), 5)
    return pd.DataFrame({
        "quote_id": [f"QTE{i:05d}" for i in range(n)],
        "trader_id": [ctx.get("trader_id", "T001")] * n,
        "currency_pair": [ctx.get("currency_pair", "EUR/USD")] * n,
        "quote_time": pd.date_range("2024-01-15 08:00", periods=n, freq="1min"),
        "bid": mid - spread,
        "ask": mid + spread,
        "bid_size": rng.integers(500_000, 5_000_000, n),
        "ask_size": rng.integers(500_000, 5_000_000, n),
        "venue": rng.choice(["EBS", "Reuters", "Bloomberg"], n),
    })


_MOCK_BY_SOURCE = {
    "hs_client_order": _mock_hs_client_order,
    "hs_execution": _mock_hs_execution,
    "hs_trades": _mock_hs_trades,
    "hs_orders_and_executions": _mock_hs_orders_and_executions,
    "hs_quotes": _mock_hs_quotes,
}


_TIME_COL_BY_SOURCE = {
    "hs_client_order": "order_time",
    "hs_execution": "exec_time",
    "hs_trades": "trade_time",
    "hs_orders_and_executions": "order_time",
    "hs_quotes": "quote_time",
}


def handle_trade_data_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    source: str = cfg.get("source", "hs_client_order")
    output_name: str = cfg.get("output_name", "trade_data")
    loop_books: bool = cfg.get("loop_over_books", False)
    trader_filter_key: str = cfg.get("trader_filter_key", "trader_id") or ""

    # Inject context into query template (audit trail only — not executed against real DB here)
    raw_query: str = cfg.get("query_template", "")
    resolved_query = resolve_template(raw_query, ctx)

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
            df = _MOCK_BY_SOURCE.get(source, _mock_hs_client_order)(ctx)
    else:
        df = _MOCK_BY_SOURCE.get(source, _mock_hs_client_order)(ctx)

    if trader_filter_key:
        trader_val = ctx.get(trader_filter_key)
        if trader_val is not None and "trader_id" in df.columns:
            df = df.loc[df["trader_id"] == trader_val].reset_index(drop=True)

    if loop_books:
        books: list = cfg.get("books", [ctx.get("book", "FX-SPOT")])
        df = pd.concat([df.assign(book=b) for b in books], ignore_index=True)

    # Optional window filter — time column is source-specific.
    from ._window import apply_window_filter
    time_col = _TIME_COL_BY_SOURCE.get(source, "order_time")
    df = apply_window_filter(df, ctx, cfg=cfg, time_col=time_col)

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_count", len(df))
    ctx.set(f"_{output_name}_resolved_query", resolved_query)


def _spec_with_data_source_metadata() -> NodeSpec:
    spec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_trade_data_collector)
    from data_sources import get_registry

    trades = get_registry().get("trades")
    if trades is None:
        return spec

    source_values = tuple(trades.sources)
    params = tuple(
        replace(p, enum=source_values)
        if p.name == "source"
        else p
        for p in spec.params
    )
    required_by_source = {
        name: [c.name for c in schema.columns if not c.optional]
        for name, schema in trades.source_schemas.items()
    }
    contract = {
        **spec.contract,
        "params": [p.to_json() for p in params],
        "output_columns_by_source": required_by_source,
    }
    return replace(spec, params=params, contract=contract)


NODE_SPEC: NodeSpec = _spec_with_data_source_metadata()
