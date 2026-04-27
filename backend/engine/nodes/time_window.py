"""
TIME_WINDOW — builds a [start_time, end_time] window from alert context.

This is a **cascade primitive**: it takes an anchor time (from ctx or a
literal config value), optionally expands it with pre/post buffers, and
publishes a plain dict under ctx.values[output_name]. Downstream
collectors read that dict via their `window_key` param and filter rows.

Keeping windowing as a separate node (not folded into collectors):
  * Each scenario can declare different buffers (FRO wants ±5min for
    market, ±30min for highlight — two TIME_WINDOW nodes, one collector
    per window).
  * MAP can fan out over distinct windows per group (e.g. per
    instance_id in FISL).
  * The window is a single object, so it shows up as one port on the
    graph — an engineer reading the DAG can see exactly what time span
    the run is scoped to.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _resolve_anchor(ctx: RunContext, key: str, literal: str) -> pd.Timestamp | None:
    """Prefer a ctx value under `key`; fall back to the literal string."""
    if key:
        val = ctx.get(key)
        if val not in (None, ""):
            try:
                return pd.to_datetime(val)
            except (ValueError, TypeError):
                return None
    if literal:
        try:
            return pd.to_datetime(literal)
        except (ValueError, TypeError):
            return None
    return None


def handle_time_window(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    output_name: str = cfg.get("output_name", "window") or "window"
    event_key: str = cfg.get("event_time_key", "") or ""
    end_key: str = cfg.get("end_time_key", "") or ""
    start_literal: str = cfg.get("start_time_literal", "") or ""
    end_literal: str = cfg.get("end_time_literal", "") or ""
    pre_minutes = int(cfg.get("pre_minutes") or 0)
    post_minutes = int(cfg.get("post_minutes") or 0)

    start = _resolve_anchor(ctx, event_key, start_literal)
    end = _resolve_anchor(ctx, end_key, end_literal) if (end_key or end_literal) else start

    if start is None:
        # Empty window — downstream treats this as no-filter. We still
        # publish the key so wiring remains predictable.
        ctx.set(output_name, {})
        return

    if end is None:
        end = start

    if pre_minutes:
        start = start - pd.Timedelta(minutes=pre_minutes)
    if post_minutes:
        end = end + pd.Timedelta(minutes=post_minutes)

    ctx.set(output_name, {
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "buffer_minutes": {"pre": pre_minutes, "post": post_minutes},
    })


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_time_window)
