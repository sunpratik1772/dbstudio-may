"""
FastAPI dependencies shared across routers.

Kept intentionally small — the WorkflowCopilot is expensive to construct
(it loads skills + contracts into a system prompt) so we build it once
and pass it around.

Writable paths (`WORKFLOWS_DIR`, `DRAFTS_DIR`, `OUTPUT_DIR`) are
environment-driven so the same image runs locally (writes under the
repo) and on Cloud Run (writes under `/tmp`, or a mounted GCS FUSE
path). `SKILLS_DIR` and `CONTRACTS_PATH` are read-only and always
resolve relative to the source tree baked into the container.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from copilot import WorkflowCopilot

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _writable_path(env_var: str, default: Path) -> Path:
    """
    Resolve a writable directory from `env_var`, falling back to the
    repo-local default. Used to move persistent-ish state off the
    read-only container image and onto a volume Cloud Run can write.
    """
    override = os.environ.get(env_var)
    return Path(override) if override else default


SKILLS_DIR = _BACKEND_ROOT / "skills"
CONTRACTS_PATH = _BACKEND_ROOT / "contracts" / "node_contracts.json"

WORKFLOWS_DIR = _writable_path("DBSHERPA_WORKFLOWS_DIR", _BACKEND_ROOT / "workflows")
DRAFTS_DIR = _writable_path("DBSHERPA_DRAFTS_DIR", _BACKEND_ROOT / "drafts")
OUTPUT_DIR = _writable_path("DBSHERPA_OUTPUT_DIR", _BACKEND_ROOT / "output")

# Ensure the writable dirs exist on boot. On Cloud Run these point at
# `/tmp/...` (via env vars) and the container needs them mkdir-ed before
# the first request; locally they already exist in the repo.
for _p in (WORKFLOWS_DIR, DRAFTS_DIR, OUTPUT_DIR):
    _p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_copilot() -> WorkflowCopilot:
    return WorkflowCopilot(
        skills_dir=str(SKILLS_DIR),
        contracts_path=str(CONTRACTS_PATH),
    )
