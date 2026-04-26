"""DataSourceRegistry loads YAML metadata correctly."""
from __future__ import annotations

from data_sources import get_registry


def test_registry_loads_all_sources():
    reg = get_registry()
    ids = {s.id for s in reg.all()}
    assert {"trades", "oracle", "comms", "market", "signals"} <= ids


def test_trades_has_expected_columns():
    trades = get_registry().get("trades")
    assert trades is not None
    names = set(trades.column_names("hs_client_order"))
    for expected in ("trader_id", "order_id", "order_time", "quantity", "limit_price", "side"):
        assert expected in names, f"missing column {expected}"

    exec_names = set(trades.column_names("hs_execution"))
    for expected in ("exec_id", "order_id", "exec_time", "exec_quantity", "exec_price", "trade_version"):
        assert expected in exec_names, f"missing column {expected}"


def test_semantic_tag_lookup():
    """The 'size' semantic maps per selected source."""
    reg = get_registry()
    trades_size = reg.get("trades").semantic_map("hs_client_order")["size"]
    executions_size = reg.get("trades").semantic_map("hs_execution")["size"]
    market_size = [c.name for c in reg.get("market").columns if c.semantic == "size"]
    assert trades_size == ["quantity"]
    assert executions_size == ["exec_quantity"]
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
    sm = trades.semantic_map("hs_client_order")
    assert sm["trader"] == ["trader_id"]
    assert sm["size"] == ["quantity"]
    assert sm["price"] == ["limit_price"]
    assert sm["time"] == ["order_time"]


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
# resolve_field
# ---------------------------------------------------------------------------


def test_resolve_field_direct_column():
    trades = get_registry().get("trades")
    assert trades.resolve_field("trader_id", "hs_client_order") == "trader_id"
    assert trades.resolve_field("quantity", "hs_client_order") == "quantity"


def test_resolve_field_semantic_alias():
    trades = get_registry().get("trades")
    assert trades.resolve_field("size", "hs_client_order") == "quantity"
    assert trades.resolve_field("size", "hs_execution") == "exec_quantity"
    assert trades.resolve_field("trader", "hs_execution") == "trader_id"


def test_resolve_field_multi_semantic_uses_first():
    market = get_registry().get("market")
    assert market.resolve_field("price") in ("bid", "ask", "mid")
    first = market.semantic_map()["price"][0]
    assert market.resolve_field("price") == first


def test_resolve_field_unknown():
    assert get_registry().get("trades").resolve_field("does_not_exist", "hs_client_order") is None
    assert get_registry().get("trades").resolve_field("", "hs_client_order") is None

    signals = get_registry().get("signals")
    assert signals.resolve_field("_signal_flag") == "_signal_flag"
    assert signals.resolve_field("nope") is None


# ---------------------------------------------------------------------------
# schema_hint / schema_hints_for_prompt
# ---------------------------------------------------------------------------

def test_schema_hint_contains_column_names():
    hint = get_registry().get("trades").schema_hint()
    assert "trader_id" in hint
    assert "hs_client_order" in hint
    assert "quantity" in hint
    assert "hs_execution" in hint
    assert "exec_quantity" in hint
    assert "semantic: size" in hint


def test_schema_hints_for_prompt_covers_all_sources():
    hints = get_registry().schema_hints_for_prompt()
    for source_id in ("trades", "oracle", "comms", "market", "signals"):
        assert source_id in hints


def test_schema_hints_for_prompt_warns_against_aliases():
    """The instruction block must tell the LLM to use exact column names."""
    hints = get_registry().schema_hints_for_prompt()
    assert "exact column names" in hints.lower() or "ONLY" in hints
