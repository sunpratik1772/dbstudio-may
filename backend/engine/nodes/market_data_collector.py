from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType, Widget


def _norm_timestamp(ts) -> str:
    """Normalise raw nanosecond ints or byte-strings to ISO-8601."""
    if isinstance(ts, (int, float)):
        epoch_s = ts / 1e9 if ts > 1e12 else float(ts)
        return datetime.fromtimestamp(epoch_s, tz=timezone.utc).isoformat()
    if isinstance(ts, bytes):
        return ts.decode("utf-8")
    return str(ts)


def _norm_bytes(val) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def handle_market_data_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    source: str = cfg.get("source", "EBS")
    output_name: str = cfg.get("output_name", "market_data")

    # Demo mode: short-circuit straight to the CSV if provided.
    mock_csv_path = cfg.get("mock_csv_path")
    if mock_csv_path:
        import os
        if os.path.isfile(mock_csv_path):
            clean = pd.read_csv(mock_csv_path)
            ctx.datasets[output_name] = clean
            ctx.set(f"{output_name}_tick_count", len(clean))
            return

    rng = np.random.default_rng(77)
    n = 200

    # Simulate raw tick data: nanosecond timestamps and byte-string fields
    base_ns = 1_705_309_200 * 1_000_000_000  # 2024-01-15 09:00 UTC
    raw_timestamps = [base_ns + i * 30_000_000_000 for i in range(n)]  # 30s steps

    raw_df = pd.DataFrame({
        "raw_timestamp": raw_timestamps,
        "raw_symbol": [b"EUR/USD"] * n,
        "bid": np.round(rng.uniform(1.0840, 1.0940, n), 5),
        "ask": np.round(rng.uniform(1.0841, 1.0941, n), 5),
        "bid_size": rng.integers(1_000_000, 5_000_000, n),
        "ask_size": rng.integers(1_000_000, 5_000_000, n),
        "venue": [source.encode("utf-8")] * n,
        "seq_no": range(n),
    })

    # Normalise dirty fields
    raw_df["timestamp"] = raw_df["raw_timestamp"].apply(_norm_timestamp)
    raw_df["symbol"] = raw_df["raw_symbol"].apply(_norm_bytes)
    raw_df["venue_name"] = raw_df["venue"].apply(_norm_bytes)
    raw_df["mid"] = ((raw_df["bid"] + raw_df["ask"]) / 2).round(5)
    raw_df["spread_pips"] = ((raw_df["ask"] - raw_df["bid"]) * 10_000).round(1)

    clean = raw_df.drop(columns=["raw_timestamp", "raw_symbol", "venue"])

    ctx.datasets[output_name] = clean
    ctx.set(f"{output_name}_tick_count", len(clean))


NODE_SPEC: NodeSpec = _spec(
    "MARKET_DATA_COLLECTOR",
    handle_market_data_collector,
    "Query EBS/Mercury tick data, normalise timestamps",
    color="#0891B2",
    icon="CandlestickChart",
    config_tags=("source", "output_name"),
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
            name="ticks",
            type=PortType.DATAFRAME,
            description=(
                "DataFrame with columns: timestamp (ISO str), symbol (str), bid, ask, "
                "mid, spread_pips, bid_size, ask_size, venue_name, seq_no. Stored under "
                "ctx.datasets[output_name]."
            ),
        ),
        PortSpec(
            name="tick_count",
            type=PortType.SCALAR,
            description="Tick count (int). Stored as {output_name}_tick_count.",
            optional=True,
        ),
    ),
    params=(
        ParamSpec(
            name="source",
            type=ParamType.ENUM,
            description="Which tick feed to query.",
            enum=("EBS", "Mercury"),
            default="EBS",
            required=True,
        ),
        ParamSpec(
            name="query_template",
            type=ParamType.STRING,
            description="Query with {context.xxx} placeholders.",
            required=True,
            widget=Widget.TEXTAREA,
        ),
        ParamSpec(
            name="output_name",
            type=ParamType.STRING,
            description="Dataset name in ctx.datasets.",
            default="market_data",
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
        "Normalises raw_timestamp (nanosecond int) → ISO-8601 string.",
        "Normalises byte-string fields (raw_symbol, venue) → plain str.",
    ),
)
