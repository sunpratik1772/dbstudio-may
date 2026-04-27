"""
Shared window-filter helper used by collector nodes.

Auto-discovery in engine/registry.py skips modules starting with
underscore, so this file is importable by other node modules but never
registered as a NodeSpec itself.

The helper keeps the window-filter contract consistent across every
collector: any collector that declares a `window_key` param can read
the published window dict (start_time / end_time) and filter its output
on a configured time column.
"""
from __future__ import annotations

import pandas as pd

from ..context import RunContext


def apply_window_filter(
    df: pd.DataFrame,
    ctx: RunContext,
    *,
    cfg: dict,
    time_col: str,
    default_window_key: str = "window",
) -> pd.DataFrame:
    """Filter df by the window dict published under ctx.values[window_key].

    No-ops (returns df unchanged) when:
      * no window is published
      * the published value is empty or not a dict
      * the DataFrame doesn't have the configured time_col
      * both start_time and end_time are absent from the window

    The filter is inclusive on both bounds.
    """
    window_key = cfg.get("window_key") or default_window_key
    window = ctx.get(window_key)
    if not isinstance(window, dict) or not window:
        return df
    if time_col not in df.columns:
        return df
    start = window.get("start_time")
    end = window.get("end_time")
    if start is None and end is None:
        return df

    series = pd.to_datetime(df[time_col], errors="coerce")

    # Normalise tz: if either side is tz-aware, make both tz-aware (UTC);
    # otherwise leave both naive. Prevents "tz-naive vs tz-aware" compare
    # errors when a collector emits UTC timestamps (market data) but the
    # window was built from tz-naive literals, or vice versa.
    def _align(ts):
        if ts is None:
            return None
        t = pd.to_datetime(ts)
        series_tz = getattr(series.dt, "tz", None)
        ts_tz = getattr(t, "tzinfo", None)
        if series_tz is not None and ts_tz is None:
            return t.tz_localize(series_tz)
        if series_tz is None and ts_tz is not None:
            return t.tz_convert(None) if hasattr(t, "tz_convert") else t.replace(tzinfo=None)
        return t

    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= series >= _align(start)
    if end is not None:
        mask &= series <= _align(end)
    return df.loc[mask].reset_index(drop=True)
