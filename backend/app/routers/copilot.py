"""Copilot and NodeSpec-facing endpoints.

Router map for newcomers:
  * POST /copilot/chat              free-form multi-turn chat
  * POST /copilot/generate          blocking workflow draft/repair
  * POST /copilot/generate/stream   SSE workflow draft/repair timeline
  * GET  /copilot/skills            skill index for the prompt builder
  * GET  /copilot/skills/{id}       skill body

This module also owns `contracts_router`, mounted at top level from
`app.main`, for historical API compatibility:
  * GET /data_sources
  * GET /contracts
  * GET /node-manifest

The important architectural point: Studio should learn node behavior from
the live NodeSpec registry (`/node-manifest`), not from frontend constants.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import CONTRACTS_PATH, DRAFTS_DIR, SKILLS_DIR, get_copilot
from ..schemas import CopilotChatRequest, CopilotGenerateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/copilot", tags=["copilot"])


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", (name or "draft").lower()).strip("-")
    return s or "draft"


def _autosave_draft(dag: dict[str, Any]) -> str | None:
    """Persist a Copilot-generated workflow to drafts/ so it appears in the
    drawer's Drafts section. Returns the filename written, or None on failure
    (we never want this to break the generate call)."""
    try:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        slug = _slugify(dag.get("name") or dag.get("workflow_id") or "draft")
        filename = f"{slug}-{int(time.time())}.json"
        path = DRAFTS_DIR / filename
        with open(path, "w") as f:
            json.dump(dag, f, indent=2)
        return filename
    except Exception:
        logger.exception("Failed to auto-save draft")
        return None


@router.post("/chat")
def copilot_chat(req: CopilotChatRequest) -> dict:
    """Copilot chat.

    Multi-turn history is scoped by `session_id`. Requests without a
    session_id are deliberately stateless so the process-wide cached
    WorkflowCopilot cannot leak chat context between users.
    """
    cp = get_copilot()
    if req.reset_history:
        cp.reset(session_id=req.session_id)
    try:
        reply = cp.chat(req.message, session_id=req.session_id)
        return {"reply": reply}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate")
def copilot_generate(req: CopilotGenerateRequest) -> dict:
    """Generate a workflow DAG JSON with N critic iterations.

    Successfully generated workflows are auto-persisted to `drafts/` so
    they show up in the Drafts section of the workflow drawer — the user
    can then promote one to a Saved workflow via Save-as.

    When the frontend attaches `current_workflow` (and optionally
    `recent_errors`) the planner runs in edit-mode: it sees the DAG
    already loaded in the canvas plus any validator/runtime failures
    and produces a targeted fix rather than a greenfield workflow.
    """
    try:
        result = get_copilot().generate_with_critic(
            req.prompt,
            iterations=req.critic_iterations,
            current_workflow=req.current_workflow,
            recent_errors=req.recent_errors,
            selected_node_id=req.selected_node_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("success") and result.get("workflow"):
        draft_filename = _autosave_draft(result["workflow"])
        if draft_filename:
            result["draft_filename"] = draft_filename
    return result


@router.post("/generate/stream")
def copilot_generate_stream(req: CopilotGenerateRequest) -> StreamingResponse:
    """
    Stream workflow generation as Server-Sent Events.
    Phases: understanding → planning → generating → critiquing → finalizing → complete.

    Accepts the same optional edit-mode fields as `/copilot/generate`.
    """
    def event_source():
        try:
            for event in get_copilot().generate_with_critic_stream(
                req.prompt,
                iterations=req.critic_iterations,
                current_workflow=req.current_workflow,
                recent_errors=req.recent_errors,
                selected_node_id=req.selected_node_id,
            ):
                # Hitch a draft auto-save to the terminal "complete" event
                # so the drawer's Drafts section reflects the new workflow
                # the instant streaming finishes.
                if event.get("phase") == "complete" and event.get("workflow"):
                    draft_filename = _autosave_draft(event["workflow"])
                    if draft_filename:
                        event = {**event, "draft_filename": draft_filename}
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Copilot stream failed")
            yield f"data: {json.dumps({'phase': 'error', 'status': 'error', 'label': 'Server error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/skills")
def list_skills() -> dict:
    """Return available skill file names and descriptions."""
    return {"skills": _skill_rows()}


def _skill_rows() -> list[dict]:
    skills: list[dict] = []
    if SKILLS_DIR.exists():
        for f in sorted(SKILLS_DIR.glob("*.md")):
            content = f.read_text()
            first_line = next((l for l in content.splitlines() if l.startswith("# ")), f.stem)
            skills.append(
                {
                    "id": f.stem,
                    "name": first_line.lstrip("# "),
                    "filename": f.name,
                }
            )
    return skills


@router.get("/guardrails")
def get_guardrails() -> dict:
    """
    Return the active authoring constraints that Copilot generation must obey.

    This is UI-facing: it lets the Plan panel show the same boundaries the
    backend prompt/validator uses (live NodeSpecs, data-source YAML, skill files,
    and host capabilities like whether custom script execution is enabled).
    """
    from data_sources import get_registry
    from engine.registry import studio_manifest

    manifest = studio_manifest()
    data_sources = get_registry().to_json().get("sources", [])
    upload_enabled = os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() in {"1", "true", "yes"}
    return {
        "nodes": [
            {
                "type_id": n["type_id"],
                "description": n["description"],
                "section": n.get("palette_group"),
            }
            for n in manifest["nodes"]
        ],
        "data_sources": data_sources,
        "skills": _skill_rows(),
        "capabilities": {
            "upload_script_enabled": upload_enabled,
            "allowed_signal_modes": ["configure"] + (["upload_script"] if upload_enabled else []),
            "builtin_signal_types": ["FRONT_RUNNING", "WASH_TRADE", "SPOOFING", "LAYERING"],
        },
        "rules": [
            "Only use node types and parameters from live NodeSpec.",
            "Only use data-source names and columns declared in metadata YAML.",
            "Use scenario logic from skills; unsupported scenarios should be narrowed to supported sources/nodes.",
            (
                "Custom Python signal scripts are allowed."
                if upload_enabled
                else "Custom Python signal scripts are disabled; use built-in SIGNAL_CALCULATOR configure mode."
            ),
        ],
    }


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str) -> dict:
    """Return full content of a skill file."""
    safe = f"{skill_id}.md"
    if safe != f"{Path(safe).name}":
        raise HTTPException(status_code=400, detail="skill_id must be a bare filename stem")
    path = SKILLS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"id": skill_id, "content": path.read_text()}


# Contracts live at the top level (not under /copilot) for historical
# reasons, but the copilot is the primary consumer so they're grouped here.
# We mount this via a second router in main.py.
contracts_router = APIRouter(tags=["copilot"])


@contracts_router.get("/data_sources")
def get_data_sources() -> dict:
    """
    Return the declarative dataset catalog. Each entry lists columns
    and their types/semantic tags as loaded from
    `backend/data_sources/metadata/*.yaml`. See
    `backend/data_sources/registry.py` for the shape.
    """
    from data_sources import get_registry

    return get_registry().to_json()


@contracts_router.get("/contracts")
def get_contracts() -> dict:
    """
    Return node I/O contracts, generated live from the registry.

    Serving this dynamically (rather than the old static
    `node_contracts.json`) means: adding a new node via
    `engine/nodes/<type>.py` is immediately visible to the
    frontend palette + copilot prompt builder on the next
    request — no script to run, no artifact to commit.

    If `CONTRACTS_PATH` still exists, we merge it with the live document.
    Dynamic registry entries win on duplicate node ids, so a newly edited
    NodeSpec is what the UI/copilot sees on the next request.
    """
    from engine.registry import contracts_document

    doc = contracts_document()
    if CONTRACTS_PATH.exists():
        try:
            with open(CONTRACTS_PATH) as f:
                static_doc = json.load(f)
            # Merge: dynamic wins on duplicates.
            merged_nodes = {**static_doc.get("nodes", {}), **doc["nodes"]}
            doc = {**static_doc, **doc, "nodes": merged_nodes}
        except Exception:  # pragma: no cover - defensive
            pass
    return doc


@contracts_router.get("/node-manifest")
def get_node_manifest() -> dict:
    """
    Live NodeSpec snapshot for the Studio: palette sections, node list with
    UI metadata, typed ports/params, and contracts. The UI fetches this on
    load (and on manual refresh) so new backend nodes appear without
    regenerating frontend artifacts.
    """
    from engine.registry import studio_manifest

    return studio_manifest()
