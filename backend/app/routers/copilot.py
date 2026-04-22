"""Copilot endpoints — chat, workflow generation, skills + contracts."""
from __future__ import annotations

import json
import logging
import re
import time
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
    """Multi-turn copilot chat."""
    cp = get_copilot()
    if req.reset_history:
        cp.reset()
    try:
        reply = cp.chat(req.message)
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
    return {"skills": skills}


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str) -> dict:
    """Return full content of a skill file."""
    path = SKILLS_DIR / f"{skill_id}.md"
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

    If `CONTRACTS_PATH` still exists we fall back to it on the
    off-chance someone has checked in an override. In practice
    the file should be deleted once this endpoint is live.
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
