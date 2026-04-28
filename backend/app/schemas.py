"""Pydantic request/response models for the HTTP API.

These classes are intentionally thin: routers own behavior, while these
models describe the wire contract that FastAPI exposes through OpenAPI.
Good field descriptions here help both humans and frontend developers
understand what shape each endpoint expects without reading router code.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunWorkflowRequest(BaseModel):
    dag: dict[str, Any] = Field(
        ...,
        description=(
            "Workflow DAG JSON with nodes and edges. Nodes must use backend "
            "NodeSpec type_id values and config keys."
        ),
    )
    alert_payload: dict[str, Any] = Field(
        ...,
        description=(
            "Opaque alert/event payload for the run. ALERT_TRIGGER binds known "
            "keys into RunContext values for downstream query templates."
        ),
    )


class ValidateWorkflowRequest(BaseModel):
    dag: dict[str, Any] = Field(
        ...,
        description="Workflow DAG JSON to validate without executing any node handlers.",
    )


class WorkflowYamlParseRequest(BaseModel):
    content: str = Field(
        ...,
        description="Human-authored workflow YAML to parse into the runtime JSON DAG shape.",
    )


class WorkflowYamlRenderRequest(BaseModel):
    workflow: dict[str, Any] = Field(
        ...,
        description="Runtime workflow DAG JSON to render as human-readable YAML.",
    )


class CopilotChatRequest(BaseModel):
    message: str = Field(..., description="Free-form user message for the copilot chat endpoint.")
    reset_history: bool = Field(
        False,
        description="When true, clear this session's server-side chat history before sending.",
    )
    session_id: Optional[str] = Field(
        None,
        description=(
            "Optional caller-owned session id for multi-turn chat. Omit for a "
            "stateless single-turn call."
        ),
    )


class CopilotGenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="Scenario or edit instruction used by the agent harness to draft or repair a workflow.",
    )
    critic_iterations: int = Field(
        3,
        description="Maximum LLM repair attempts after deterministic validation failures.",
    )
    # Optional editing context. When the user is iterating on an
    # existing workflow (fixing errors, adding nodes, renaming things)
    # the frontend attaches the current canvas state + any recent
    # failures so the planner can produce a targeted edit rather than
    # a greenfield draft. Both fields default to None so the legacy
    # "describe a scenario → generate from scratch" path is unchanged.
    current_workflow: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Existing canvas workflow for edit-mode generation. When omitted, "
            "the planner creates a new workflow from scratch."
        ),
    )
    recent_errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Recent validator/runtime errors to help the planner produce a targeted fix.",
    )
    # When the user has a node selected on the canvas and writes
    # something deictic ("remove this", "change this threshold") we
    # ship the selected node id so the LLM can resolve the referent
    # instead of guessing.
    selected_node_id: Optional[str] = Field(
        None,
        description=(
            "Canvas node id the user currently selected, used to resolve instructions "
            "like 'change this threshold'."
        ),
    )
