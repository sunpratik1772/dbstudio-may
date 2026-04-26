"""
Execution collector mock DataFrames must match their selected Solr source
schema, not a broad union of every trade-like column.
"""
from __future__ import annotations

from data_sources import get_registry
from engine.context import RunContext
from engine.nodes.execution_data_collector import _mock_hs_client_order, _mock_hs_execution


def test_trade_mocks_column_keys_are_in_registry():
    ctx = RunContext(alert_payload={})
    reg = get_registry().get("trades")
    assert reg is not None
    client_allowed = set(reg.column_names("hs_client_order"))
    execution_allowed = set(reg.column_names("hs_execution"))

    client = set(_mock_hs_client_order(ctx).columns)
    execution = set(_mock_hs_execution(ctx).columns)

    assert client <= client_allowed, f"client_order columns not in trades.yaml: {client - client_allowed}"
    assert execution <= execution_allowed, f"execution columns not in trades.yaml: {execution - execution_allowed}"
