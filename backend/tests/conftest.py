"""
Test harness setup.

We add the repository's `backend/` directory to `sys.path` so test
modules can import `engine`, `app`, `agent`, `data_sources` as
top-level packages — matching how the running service imports them.

Pytest is run from the repo root (`pytest backend/tests/`) or from
`backend/` (`pytest tests/`); both work.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Keep LLM calls out of the unit tests — anything that reaches for
# Gemini should either be mocked or skipped. Pinning the API key to
# empty makes any accidental real call fail fast.
os.environ.setdefault("GEMINI_API_KEY", "")
