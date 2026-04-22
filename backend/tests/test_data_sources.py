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


# ---------------------------------------------------------------------------
# semantic_map
# ---------------------------------------------------------------------------

def test_semantic_map_returns_correct_columns():
    trades = get_registry().get("trades")
    sm = trades.semantic_map()
    assert sm["trader"] == ["trader_id"]
    assert sm["size"] == ["qty"]
    assert sm["price"] == ["price"]
    assert sm["time"] == ["timestamp"]


def test_semantic_map_multi_column():
    """market.price maps to bid, ask, mid — all three in order."""
    market = get_registry().get("market")
    sm = market.semantic_map()
    assert set(sm["price"]) == {"bid", "ask", "mid"}


def test_semantic_map_empty_when_no_tags():
    """signals dataset has no semantic tags — map should be empty."""
    signals = get_registry().get("signals")
    assert signals.semantic_map() == {}


# ---------------------------------------------------------------------------
# schema_hint / schema_hints_for_prompt
# ---------------------------------------------------------------------------

def test_schema_hint_contains_column_names():
    hint = get_registry().get("trades").schema_hint()
    assert "trader_id" in hint
    assert "qty" in hint
    assert "semantic: size" in hint


def test_schema_hints_for_prompt_covers_all_sources():
    hints = get_registry().schema_hints_for_prompt()
    for source_id in ("trades", "comms", "market", "signals"):
        assert source_id in hints


def test_schema_hints_for_prompt_warns_against_aliases():
    """The instruction block must tell the LLM to use exact column names."""
    hints = get_registry().schema_hints_for_prompt()
    assert "exact column names" in hints.lower() or "ONLY" in hints
