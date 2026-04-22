"""
/agent/* endpoints.

Currently only exposes a read-only metrics snapshot used by the UI
status strip + CI regression checks. Future additions live here:
  - GET /agent/attempts/:id  (per-run trace)
  - POST /agent/autofix      (run auto-fixer standalone for a DAG)
"""
from __future__ import annotations

from fastapi import APIRouter

from agent.harness.metrics import get_metrics

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/metrics")
def metrics() -> dict:
    """Return a snapshot of in-process agent metrics.

    These reset on process restart. Think of them as a dev/ops
    dashboard feed rather than long-term telemetry.
    """
    return get_metrics().snapshot()


@router.post("/metrics/reset")
def reset_metrics() -> dict:
    """Zero all counters. Handy during a demo or after a regression fix."""
    get_metrics().reset()
    return {"status": "ok"}
