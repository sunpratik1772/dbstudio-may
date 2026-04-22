"""DataSourceRegistry loads YAML metadata correctly."""
from __future__ import annotations

from data_sources import get_registry


def test_registry_loads_all_sources():
    reg = get_registry()
    ids = {s.id for s in reg.all()}
    assert {"trades", "comms", "market", "signals"} <= ids


def test_trades_has_expected_columns():
    trades = get_registry().get("trades")
    assert trades is not None
    names = set(trades.column_names())
    # Spot-check the columns the workflows actually reference.
    for expected in ("trader_id", "order_id", "timestamp", "qty", "price", "side"):
        assert expected in names, f"missing column {expected}"


def test_semantic_tag_lookup():
    """The 'size' semantic maps to 'qty' on trades and 'bid_size/ask_size' on market."""
    reg = get_registry()
    trades_size = [c.name for c in reg.get("trades").columns if c.semantic == "size"]
    market_size = [c.name for c in reg.get("market").columns if c.semantic == "size"]
    assert trades_size == ["qty"]
    assert set(market_size) == {"bid_size", "ask_size"}


def test_unknown_source_returns_none():
    assert get_registry().get("does-not-exist") is None


def test_registry_endpoint_shape():
    """The JSON shape is stable — anyone reading /data_sources relies on it."""
    doc = get_registry().to_json()
    assert "sources" in doc
    for s in doc["sources"]:
        assert {"id", "description", "sources", "columns"} <= set(s.keys())
        for c in s["columns"]:
            assert {"name", "type", "description", "semantic", "optional"} <= set(c.keys())
