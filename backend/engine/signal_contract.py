"""
Signal output column names — read only from SIGNAL_CALCULATOR node YAML
(`extras.signal_output_columns`), never duplicated as string literals elsewhere.
"""
from __future__ import annotations

__all__ = [
    "get_signal_output_columns",
    "signal_flag_column_name",
    "signal_score_column_name",
]


def get_signal_output_columns() -> tuple[str, ...]:
    from .registry import get_spec

    raw = (get_spec("SIGNAL_CALCULATOR").contract or {}).get("signal_output_columns")
    if not raw:
        raise RuntimeError(
            "SIGNAL_CALCULATOR node YAML must define extras.signal_output_columns"
        )
    return tuple(str(x) for x in raw)


def signal_flag_column_name() -> str:
    for c in get_signal_output_columns():
        if c == "_signal_flag":
            return c
    raise RuntimeError("signal_output_columns must include _signal_flag")


def signal_score_column_name() -> str:
    for c in get_signal_output_columns():
        if c == "_signal_score":
            return c
    raise RuntimeError("signal_output_columns must include _signal_score")
