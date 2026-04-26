"""Collect placeholder Oracle order/execution extracts.

The real adapter will swap the synthetic branch for an Oracle client, but the
node contract is already schema-driven: the selected source maps to
data_sources/metadata/oracle.yaml and provenance records the exact subsection.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from data_sources import get_registry

from ..collector_source import collector_source_ref
from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _mock_oracle_source(ctx: RunContext, source: str, rows: int = 12) -> pd.DataFrame:
    ds = get_registry().get("oracle")
    schema = ds.source_schema(source) if ds is not None else None
    if schema is None:
        raise ValueError(f"Unknown Oracle source '{source}'")

    values = {}
    for column in schema.columns:
        name = column.name
        if column.type == "datetime":
            values[name] = pd.date_range("2024-01-15 08:00", periods=rows, freq="7min")
        elif column.type in {"number", "integer"}:
            base = list(range(1, rows + 1))
            values[name] = base if column.type == "integer" else [float(v * 1000) for v in base]
        elif name == "trader_id":
            values[name] = [ctx.get("trader_id", "T001")] * rows
        elif name == "book":
            values[name] = [ctx.get("book", "FX-SPOT")] * rows
        elif name == "instrument":
            values[name] = [ctx.get("currency_pair", "EUR/USD")] * rows
        elif name == "side":
            values[name] = ["BUY" if i % 2 == 0 else "SELL" for i in range(rows)]
        else:
            values[name] = [f"{name}_{i:03d}" for i in range(rows)]
    return pd.DataFrame(values)


def handle_oracle_data_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    source: str = cfg.get("source", "oracle_orders")
    output_name: str = cfg.get("output_name", "oracle_data")

    ds = get_registry().get("oracle")
    raw_query = cfg.get("query_template") or (ds.base_query(source) if ds else "")
    resolved_query = ctx.inject_template(raw_query)

    mock_csv_path = cfg.get("mock_csv_path")
    if mock_csv_path:
        import os

        if os.path.isfile(mock_csv_path):
            df = pd.read_csv(mock_csv_path)
        else:
            df = _mock_oracle_source(ctx, source)
    else:
        df = _mock_oracle_source(ctx, source)

    ctx.datasets[output_name] = df
    ctx.dataset_provenance[output_name] = collector_source_ref("ORACLE_DATA_COLLECTOR", cfg)
    ctx.set(f"{output_name}_count", len(df))
    ctx.set(f"_{output_name}_resolved_query", resolved_query)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_oracle_data_collector)
