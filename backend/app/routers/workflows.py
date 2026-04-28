"""
Workflow CRUD for two parallel stores:

  workflows/   — explicitly "saved" workflows. Named by the user.
  drafts/      — in-flight or Copilot-generated workflows. Transient; users
                 promote a draft to a saved workflow by clicking Save As.

Files may be JSON or YAML. The runner still receives the same in-memory DAG
dict either way; YAML is the human-friendly authoring/export format.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from engine.workflow_format import workflow_from_yaml, workflow_to_yaml

from ..schemas import WorkflowYamlParseRequest, WorkflowYamlRenderRequest
from ..deps import DRAFTS_DIR, WORKFLOWS_DIR


# ---------------------------------------------------------------------------
# Shared file helpers
# ---------------------------------------------------------------------------
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")
_WORKFLOW_SUFFIXES = {".json", ".yaml", ".yml"}


def _safe_path(base: Path, filename: str) -> Path:
    """Reject filenames that try to escape the base directory."""
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail=f"Invalid filename '{filename}'")
    if Path(filename).suffix not in _WORKFLOW_SUFFIXES:
        raise HTTPException(status_code=400, detail="Workflow filename must end with .json, .yaml, or .yml")
    return base / filename


def _read_workflow(path: Path) -> dict:
    try:
        text = path.read_text()
        if path.suffix == ".json":
            return json.loads(text)
        return workflow_from_yaml(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"'{path.name}' is not valid JSON: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"'{path.name}' is not valid workflow YAML: {exc}")


def _write_workflow(path: Path, dag: dict[str, Any]) -> None:
    if path.suffix == ".json":
        path.write_text(json.dumps(dag, indent=2) + "\n")
    else:
        path.write_text(workflow_to_yaml(dag))


def _list_dir(base: Path) -> list[dict]:
    items: list[dict] = []
    if not base.exists():
        return items
    files = [f for f in base.iterdir() if f.is_file() and f.suffix in _WORKFLOW_SUFFIXES]
    for f in sorted(files):
        try:
            dag = _read_workflow(f)
        except Exception:
            continue
        stat = f.stat()
        items.append(
            {
                "filename": f.name,
                "workflow_id": dag.get("workflow_id"),
                "name": dag.get("name"),
                "description": dag.get("description"),
                "node_count": len(dag.get("nodes", [])),
                # Newest-first sorting happens on the frontend. Exposing
                # both mtime + size lets the UI show "edited 2 mins ago".
                "modified_ms": int(stat.st_mtime * 1000),
            }
        )
    # Sort: most recently modified first (drafts churn, saved workflows may
    # legitimately stay untouched for months).
    items.sort(key=lambda r: r.get("modified_ms") or 0, reverse=True)
    return items


def _load(base: Path, filename: str) -> dict:
    path = _safe_path(base, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in {base.name}")
    return _read_workflow(path)


def _save(base: Path, filename: str, dag: dict[str, Any]) -> dict:
    path = _safe_path(base, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_workflow(path, dag)
    return {"saved": filename, "location": base.name}


def _delete(base: Path, filename: str) -> dict:
    path = _safe_path(base, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in {base.name}")
    path.unlink()
    return {"deleted": filename, "location": base.name}


# ---------------------------------------------------------------------------
# /workflows — saved (named, promoted) workflows
# ---------------------------------------------------------------------------
router = APIRouter(tags=["workflows"])


@router.post("/workflow-format/yaml-to-json")
def parse_workflow_yaml(req: WorkflowYamlParseRequest) -> dict:
    """Convert human-authored workflow YAML into the runtime JSON DAG."""
    try:
        return {"workflow": workflow_from_yaml(req.content)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflow-format/json-to-yaml")
def render_workflow_yaml(req: WorkflowYamlRenderRequest) -> dict:
    """Convert the runtime JSON DAG into downloadable workflow YAML."""
    return {"content": workflow_to_yaml(req.workflow)}


@router.get("/workflows")
def list_workflows() -> dict:
    """List saved workflows only. Drafts live under /drafts."""
    return {"workflows": _list_dir(WORKFLOWS_DIR)}


@router.get("/workflows/{filename}")
def get_workflow(filename: str) -> dict:
    return _load(WORKFLOWS_DIR, filename)


@router.post("/workflows/{filename}")
def save_workflow(filename: str, dag: dict[str, Any]) -> dict:
    return _save(WORKFLOWS_DIR, filename, dag)


@router.delete("/workflows/{filename}")
def delete_workflow(filename: str) -> dict:
    return _delete(WORKFLOWS_DIR, filename)


# ---------------------------------------------------------------------------
# /drafts — Copilot-generated or manually-built scratch workflows
# ---------------------------------------------------------------------------
drafts_router = APIRouter(tags=["drafts"])


@drafts_router.get("/drafts")
def list_drafts() -> dict:
    return {"drafts": _list_dir(DRAFTS_DIR)}


@drafts_router.get("/drafts/{filename}")
def get_draft(filename: str) -> dict:
    return _load(DRAFTS_DIR, filename)


@drafts_router.post("/drafts/{filename}")
def save_draft(filename: str, dag: dict[str, Any]) -> dict:
    return _save(DRAFTS_DIR, filename, dag)


@drafts_router.delete("/drafts/{filename}")
def delete_draft(filename: str) -> dict:
    return _delete(DRAFTS_DIR, filename)


# ---------------------------------------------------------------------------
# /drafts/{filename}/promote — move a draft into workflows/ under a new name
# ---------------------------------------------------------------------------
@drafts_router.post("/drafts/{filename}/promote")
def promote_draft(filename: str, body: dict[str, Any]) -> dict:
    """Promote a draft to a saved workflow.

    Body: { "target_filename": "my_new_workflow.json", "name": "Human name" }
    Effect: writes the draft JSON to workflows/<target_filename> (optionally
    updating the embedded `name` field) and deletes the draft.
    """
    target = body.get("target_filename")
    if not target:
        raise HTTPException(status_code=400, detail="target_filename is required")

    dag = _load(DRAFTS_DIR, filename)
    if body.get("name"):
        dag["name"] = body["name"]
    _save(WORKFLOWS_DIR, target, dag)
    _delete(DRAFTS_DIR, filename)
    return {"promoted": filename, "saved_as": target, "location": WORKFLOWS_DIR.name}
