"""Loud DataFrame column checks for handlers (fail fast, no silent zeros).

Call this from node handlers immediately after building or loading a
DataFrame whose downstream contract depends on specific columns. This is
runtime protection: it catches bad source data or handler bugs during a
run. It complements, but does not replace, the pre-flight validator and
NodeSpec `required_columns` metadata, which reason about the DAG before
any pandas objects exist.
"""
from __future__ import annotations

import pandas as pd

__all__ = ["require_columns"]


def require_columns(
    df: pd.DataFrame,
    columns: list[str] | tuple[str, ...],
    *,
    context: str,
) -> None:
    """Raise `ValueError` with a clear message if any required column is missing."""
    need = list(columns)
    missing = [c for c in need if c not in df.columns]
    if missing:
        have = list(df.columns)
        raise ValueError(
            f"{context}: missing required column(s) {missing!r}. "
            f"DataFrame has: {have}"
        )
