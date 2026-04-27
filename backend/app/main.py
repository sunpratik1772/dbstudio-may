"""
dbSherpa FastAPI app.

Routers are intentionally one-per-concern so different engineers can own
and evolve them independently without stepping on each other:

    /workflows       → app.routers.workflows   (saved CRUD)
    /drafts          → app.routers.workflows   (scratch CRUD + promote)
    /run, /run/stream→ app.routers.run         (DAG execution)
    /validate        → app.routers.validate    (deterministic DAG validation)
    /report/*        → app.routers.reports     (generated xlsx downloads)
    /copilot/*       → app.routers.copilot     (LLM generation + skills)
    /contracts       → app.routers.copilot     (node schemas)
    /agent/*         → app.routers.agent       (harness metrics + introspection)

All cross-cutting plumbing (CORS, logging, shared state like the
copilot singleton) lives here. Nothing domain-specific.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before any code reads os.environ (Gemini, output dir, etc.).
# Uvicorn does not load dotenv by default; IDE/cursor runs often skip start.sh.
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import agent as agent_routes
from .routers import copilot as copilot_routes
from .routers import reports as reports_routes
from .routers import run as run_routes
from .routers import validate as validate_routes
from .routers import workflows as workflow_routes

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="dbSherpa API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {"service": "dbSherpa", "status": "running", "version": app.version}


app.include_router(workflow_routes.router)
app.include_router(workflow_routes.drafts_router)
app.include_router(run_routes.router)
app.include_router(validate_routes.router)
app.include_router(reports_routes.router)
app.include_router(copilot_routes.router)
app.include_router(copilot_routes.contracts_router)
app.include_router(agent_routes.router)
