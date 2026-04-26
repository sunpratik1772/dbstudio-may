"""
Workflow validation endpoint.

Separate from /run so the frontend can cheaply ask "is this workflow
ok?" without executing anything, and the copilot can use the same
entrypoint to drive its self-corrector.
"""
from __future__ import annotations

from fastapi import APIRouter

from engine.validator import validate_dag

from .run import _resolve_workflow_mock_csv_paths
from ..schemas import ValidateWorkflowRequest

router = APIRouter(tags=["validate"])


@router.post("/validate")
def validate(req: ValidateWorkflowRequest) -> dict:
    """Run structural + contract + wiring + hard-rule checks.

    Always returns HTTP 200 with the validation result payload — the
    caller decides whether `valid=false` should block them. This keeps
    the endpoint idempotent and safe for the copilot to spam during a
    self-correction loop.
    """
    dag = _resolve_workflow_mock_csv_paths(req.dag)
    return validate_dag(dag).to_json()
