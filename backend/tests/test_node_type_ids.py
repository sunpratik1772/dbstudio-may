"""node_type_ids constants match registered NODE_SPECS keys."""
from __future__ import annotations

import engine.node_type_ids as nti
from engine.registry import NODE_SPECS

_IDS = [
    nti.ALERT_TRIGGER,
    nti.COMMS_COLLECTOR,
    nti.CONSOLIDATED_SUMMARY,
    nti.DECISION_RULE,
    nti.FEATURE_ENGINE,
    nti.MARKET_DATA_COLLECTOR,
    nti.ORACLE_DATA_COLLECTOR,
    nti.REPORT_OUTPUT,
    nti.SECTION_SUMMARY,
    nti.SIGNAL_CALCULATOR,
    nti.EXECUTION_DATA_COLLECTOR,
]


def test_all_node_type_ids_in_registry():
    for tid in _IDS:
        assert tid in NODE_SPECS, f"{tid!r} missing from NODE_SPECS"
