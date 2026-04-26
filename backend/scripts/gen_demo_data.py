"""
Regenerate the CSV fixtures under `backend/demo_data/`.

The `/run/demo` endpoint feeds these fixtures through the real engine
pipeline. Regenerating them is a pure function of the mock-data
generators in `engine/nodes/*_collector.py`, so this script is
deterministic (numpy seeds baked in).

Usage:
    python scripts/gen_demo_data.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.context import RunContext
from engine.nodes.comms_collector import _MOCK_MESSAGES
from engine.nodes.execution_data_collector import _mock_hs_client_order, _mock_hs_execution


OUT = Path(__file__).resolve().parents[1] / "demo_data"


def _trade_fixtures(ctx: RunContext) -> dict[str, pd.DataFrame]:
    return {
        "trades_hs_client_order.csv": _mock_hs_client_order(ctx),
        "trades_hs_execution.csv": _mock_hs_execution(ctx),
    }


def _comms_fixture() -> pd.DataFrame:
    rng = np.random.default_rng(99)
    n = 30
    return pd.DataFrame({
        "user": ["T001"] * n,
        "timestamp": pd.date_range("2024-01-15 07:30", periods=n, freq="8min"),
        "display_post": rng.choice(_MOCK_MESSAGES, n),
        "event_type": rng.choice(["CHAT", "VOICE", "EMAIL", "BLOOMBERG_MSG"], n),
    })


def _market_fixture() -> pd.DataFrame:
    rng = np.random.default_rng(77)
    n = 200
    base_ns = 1_705_309_200 * 1_000_000_000  # 2024-01-15 09:00 UTC
    raw_ts = [base_ns + i * 30_000_000_000 for i in range(n)]
    ts = [datetime.fromtimestamp(x / 1e9, tz=timezone.utc).isoformat() for x in raw_ts]
    bid = np.round(rng.uniform(1.0840, 1.0940, n), 5)
    ask = np.round(rng.uniform(1.0841, 1.0941, n), 5)
    df = pd.DataFrame({
        "timestamp": ts,
        "symbol": ["EUR/USD"] * n,
        "bid": bid,
        "ask": ask,
        "bid_size": rng.integers(1_000_000, 5_000_000, n),
        "ask_size": rng.integers(1_000_000, 5_000_000, n),
        "venue_name": ["EBS"] * n,
        "seq_no": range(n),
    })
    df["mid"] = ((df["bid"] + df["ask"]) / 2).round(5)
    df["spread_pips"] = ((df["ask"] - df["bid"]) * 10_000).round(1)
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    ctx = RunContext(alert_payload={
        "trader_id": "T001", "book": "FX-SPOT", "currency_pair": "EUR/USD",
        "alert_id": "A1", "alert_date": "2024-01-15",
    })
    for k, v in ctx.alert_payload.items():
        ctx.set(k, v)

    outputs: dict[str, pd.DataFrame] = {
        **_trade_fixtures(ctx),
        "comms.csv": _comms_fixture(),
        "market.csv": _market_fixture(),
    }

    for name, df in outputs.items():
        path = OUT / name
        df.to_csv(path, index=False)
        print(f"  wrote {path.relative_to(Path.cwd())} ({df.shape[0]} rows × {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
