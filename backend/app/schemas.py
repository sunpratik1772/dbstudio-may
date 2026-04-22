"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunWorkflowRequest(BaseModel):
    dag: dict[str, Any]
    alert_payload: dict[str, Any]


class ValidateWorkflowRequest(BaseModel):
    dag: dict[str, Any]


class CopilotChatRequest(BaseModel):
    message: str
    reset_history: bool = False


class CopilotGenerateRequest(BaseModel):
    prompt: str
    critic_iterations: int = 3
    # Optional editing context. When the user is iterating on an
    # existing workflow (fixing errors, adding nodes, renaming things)
    # the frontend attaches the current canvas state + any recent
    # failures so the planner can produce a targeted edit rather than
    # a greenfield draft. Both fields default to None so the legacy
    # "describe a scenario → generate from scratch" path is unchanged.
    current_workflow: dict[str, Any] | None = None
    recent_errors: list[dict[str, Any]] | None = None
    # When the user has a node selected on the canvas and writes
    # something deictic ("remove this", "change this threshold") we
    # ship the selected node id so the LLM can resolve the referent
    # instead of guessing.
    selected_node_id: str | None = None
