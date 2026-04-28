"""Workflow execution — blocking, streaming, and one-click demo variants.

All endpoints run the deterministic validator before touching the DAG
runner so a malformed workflow fails fast with a structured error
payload instead of blowing up half-way through execution.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from engine import RunContext
from engine.jobs import get_default_runner
from engine.validator import validate_dag
from engine.workflow_format import workflow_from_yaml

from ..deps import WORKFLOWS_DIR
from ..schemas import RunWorkflowRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["run"])

# backend/ — used to resolve `demo_data/...` mock_csv_path regardless of process cwd
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _resolve_workflow_mock_csv_paths(dag: dict) -> dict:
    """
    When the UI posts the same JSON as `backend/workflows/*.json`, relative
    `mock_csv_path` values must find CSVs under `backend/` even if uvicorn
    was started from the repo root. Deep-copy the DAG and rewrite paths that
    exist as `backend/<path>` to absolute paths; leave unknown paths unchanged.
    """
    out = copy.deepcopy(dag)
    for node in out.get("nodes", []):
        cfg = node.get("config")
        if not isinstance(cfg, dict):
            continue
        p = cfg.get("mock_csv_path")
        if not p or not isinstance(p, str):
            continue
        if os.path.isabs(p) and os.path.isfile(p):
            continue
        candidate = (_BACKEND_ROOT / p).resolve()
        try:
            candidate.relative_to(_BACKEND_ROOT)
        except ValueError:
            continue
        if candidate.is_file():
            cfg["mock_csv_path"] = str(candidate)
    return out


# Sensible defaults for the demo endpoint so a reviewer can curl the
# URL with an empty body and still get a meaningful run.
_DEMO_WORKFLOW_FILENAME = "fx_fro_v2_workflow.json"
_DEMO_ALERT_PAYLOAD: dict[str, str] = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "currency_pair": "EUR/USD",
    "alert_date": "2024-01-15",
    "alert_id": "DEMO-0001",
    "event_time": "2024-01-15 09:00",
}


class RunDemoRequest(BaseModel):
    """
    Body for `POST /run/demo`. All fields optional — a blank body
    runs the bundled FX front-running workflow against the shipped
    CSV fixtures and returns the generated xlsx as an attachment.
    """

    workflow_filename: str = Field(
        default=_DEMO_WORKFLOW_FILENAME,
        description=(
            "Name of a .json/.yaml workflow file under `backend/workflows/` to execute. "
            "Defaults to the bundled demo workflow. `fxfronew_workflow.json` is "
            "the same DAG with report `output/fxfronew_report.xlsx`."
        ),
    )
    alert_payload: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional override of the canned alert payload.",
    )
    return_json: bool = Field(
        default=False,
        description=(
            "If true, return the normal JSON run result (with "
            "`download_url`) instead of streaming the xlsx. Handy for "
            "inspecting the pipeline output without downloading."
        ),
    )


@router.post("/run")
def run(req: RunWorkflowRequest) -> dict:
    """Execute a workflow DAG synchronously. Returns run summary."""
    # Deterministic pre-flight. Errors short-circuit with HTTP 422 and
    # the same payload shape the /validate endpoint returns, so the
    # frontend handles both uniformly.
    dag = _resolve_workflow_mock_csv_paths(req.dag)
    validation = validate_dag(dag)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.to_json())

    try:
        ctx: RunContext = get_default_runner().run(dag, req.alert_payload).context
        result: dict = {
            "run_id": ctx.run_id,
            "disposition": ctx.disposition,
            "flag_count": ctx.get("flag_count", 0),
            "output_branch": ctx.output_branch,
            "report_path": ctx.report_path,
            "datasets": list(ctx.datasets.keys()),
            "sections": {
                name: {"stats": s["stats"], "narrative": s["narrative"]}
                for name, s in ctx.sections.items()
            },
            "executive_summary": ctx.executive_summary,
        }
        if ctx.report_path:
            result["download_url"] = f"/report/{Path(ctx.report_path).name}"
        # Surface non-blocking warnings so the UI can show an amber
        # banner even on a successful run.
        if validation.warnings:
            result["warnings"] = [w.to_json() for w in validation.warnings]
        return result
    except Exception as exc:
        logger.exception("Workflow run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run/stream")
def run_stream(req: RunWorkflowRequest) -> StreamingResponse:
    """Execute a workflow and stream per-node events as Server-Sent Events.

    If the DAG fails validation the stream emits a single
    `workflow_error` frame with the validation payload and closes,
    rather than raising HTTP 422. That way the frontend — which is
    already parsing SSE — gets a uniform error surface.
    """
    dag = _resolve_workflow_mock_csv_paths(req.dag)
    validation = validate_dag(dag)

    def event_source():
        if not validation.valid:
            yield "data: " + json.dumps(
                {
                    "type": "workflow_error",
                    "error": "Validation failed",
                    "validation": validation.to_json(),
                }
            ) + "\n\n"
            return
        for ev in get_default_runner().stream(dag, req.alert_payload):
            if ev.get("type") == "workflow_complete":
                res = ev.get("result") or {}
                if res.get("report_path"):
                    res["download_url"] = f"/report/{Path(res['report_path']).name}"
                    ev["result"] = res
                if validation.warnings:
                    ev["warnings"] = [w.to_json() for w in validation.warnings]
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _load_bundled_workflow(filename: str) -> dict:
    """
    Read a workflow from the configured workflows dir.

    Only basenames are accepted — this endpoint deliberately doesn't
    let callers escape the directory via `../`. Any suspicious path
    surfaces as a 400, not a 404, so the operator sees intent rather
    than a generic "file missing".
    """
    safe = Path(filename).name  # strips any leading path segments
    if safe != filename:
        raise HTTPException(status_code=400, detail="workflow_filename must be a bare filename")
    path = WORKFLOWS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"workflow '{safe}' not found")
    try:
        text = path.read_text()
        if path.suffix == ".json":
            return json.loads(text)
        if path.suffix in {".yaml", ".yml"}:
            return workflow_from_yaml(text)
        raise HTTPException(status_code=400, detail="workflow_filename must end with .json, .yaml, or .yml")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"workflow '{safe}' is not valid JSON: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"workflow '{safe}' is not valid YAML: {exc}")


@router.post("/run/demo")
def run_demo(req: Optional[RunDemoRequest] = None):
    """
    One-click demo: run a bundled workflow end-to-end against the CSV
    fixtures in `backend/demo_data/` and return the generated xlsx as
    a browser download.

    This endpoint is the fastest way to verify a deployment end-to-end
    — no alert payload, no workflow authoring file, no external data source
    required. Reviewers can `curl -OJ $SERVICE_URL/run/demo` and open
    the resulting xlsx. Pass `return_json=true` in the body to get the
    normal JSON run summary instead (with a `download_url` field).
    """
    req = req or RunDemoRequest()
    dag = _resolve_workflow_mock_csv_paths(_load_bundled_workflow(req.workflow_filename))
    alert = req.alert_payload or dict(_DEMO_ALERT_PAYLOAD)

    validation = validate_dag(dag)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.to_json())

    try:
        ctx: RunContext = get_default_runner().run(dag, alert).context
    except Exception as exc:
        logger.exception("Demo run failed (workflow=%s)", req.workflow_filename)
        raise HTTPException(status_code=500, detail=str(exc))

    if not ctx.report_path:
        # Workflow didn't write a report — fall back to JSON so the
        # caller still sees a successful run and can inspect the
        # datasets / sections.
        return {
            "run_id": ctx.run_id,
            "disposition": ctx.disposition,
            "flag_count": ctx.get("flag_count", 0),
            "datasets": list(ctx.datasets.keys()),
            "executive_summary": ctx.executive_summary,
            "note": "workflow produced no report file",
        }

    if req.return_json:
        return {
            "run_id": ctx.run_id,
            "disposition": ctx.disposition,
            "flag_count": ctx.get("flag_count", 0),
            "output_branch": ctx.output_branch,
            "report_path": ctx.report_path,
            "download_url": f"/report/{Path(ctx.report_path).name}",
            "datasets": list(ctx.datasets.keys()),
            "executive_summary": ctx.executive_summary,
        }

    # Default: stream the xlsx back as a download so `curl -OJ` works.
    # The run_id and disposition are attached as response headers so
    # curl -i / browser devtools can still correlate the run with
    # backend logs without parsing the xlsx.
    report_path = Path(ctx.report_path)
    if not report_path.exists():
        raise HTTPException(status_code=500, detail=f"report path missing after run: {report_path}")
    return FileResponse(
        str(report_path),
        filename=report_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{report_path.name}"',
            "X-Run-Id": ctx.run_id,
            "X-Disposition": ctx.disposition or "",
            "X-Flag-Count": str(ctx.get("flag_count", 0)),
            "X-Content-Type-Options": "nosniff",
        },
    )
