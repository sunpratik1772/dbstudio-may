"""Collector type → data_sources id map stays aligned with NodeSpecs."""
from __future__ import annotations

from engine.collector_source import COLLECTOR_TYPE_TO_SOURCE_ID, collector_source_ref
from engine.registry import NODE_SPECS


def test_collector_types_are_registered_nodes():
    for tid in COLLECTOR_TYPE_TO_SOURCE_ID:
        assert tid in NODE_SPECS, f"unknown collector type {tid!r}"


def test_expected_registry_ids():
    assert COLLECTOR_TYPE_TO_SOURCE_ID["EXECUTION_DATA_COLLECTOR"] == "trades"
    assert COLLECTOR_TYPE_TO_SOURCE_ID["ORACLE_DATA_COLLECTOR"] == "oracle"
    assert COLLECTOR_TYPE_TO_SOURCE_ID["MARKET_DATA_COLLECTOR"] == "market"
    assert COLLECTOR_TYPE_TO_SOURCE_ID["COMMS_COLLECTOR"] == "comms"


def test_selected_source_is_part_of_provenance():
    assert (
        collector_source_ref("EXECUTION_DATA_COLLECTOR", {"source": "hs_execution"})
        == "trades:hs_execution"
    )
    assert (
        collector_source_ref("ORACLE_DATA_COLLECTOR", {"source": "oracle_orders"})
        == "oracle:oracle_orders"
    )
