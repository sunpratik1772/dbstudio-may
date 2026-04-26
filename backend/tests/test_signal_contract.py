"""SIGNAL_CALCULATOR output column names are single-sourced in node YAML."""
from __future__ import annotations

from engine.signal_contract import (
    get_signal_output_columns,
    signal_flag_column_name,
    signal_score_column_name,
)


def test_signal_columns_match_yaml_contract():
    cols = get_signal_output_columns()
    assert len(cols) == 5
    assert "_signal_flag" in cols
    assert signal_flag_column_name() == "_signal_flag"
    assert signal_score_column_name() == "_signal_score"
