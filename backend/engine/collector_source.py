"""
Collector provenance helpers.

Collectors publish datasets whose schema is determined by both node type and
the selected dropdown source. Provenance therefore uses refs such as
``trades:hs_execution`` instead of only ``trades``.
"""
from __future__ import annotations

COLLECTOR_TYPE_TO_SOURCE_ID: dict[str, str] = {
    "EXECUTION_DATA_COLLECTOR": "trades",
    "ORACLE_DATA_COLLECTOR": "oracle",
    "MARKET_DATA_COLLECTOR": "market",
    "COMMS_COLLECTOR": "comms",
}


def collector_source_ref(node_type: str, config: dict | None = None) -> str:
    source_id = COLLECTOR_TYPE_TO_SOURCE_ID[node_type]
    source = (config or {}).get("source")
    if source and source_id in {"trades", "oracle"}:
        return f"{source_id}:{source}"
    return source_id


__all__ = ["COLLECTOR_TYPE_TO_SOURCE_ID", "collector_source_ref"]
