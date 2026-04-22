"""
Backwards-compat shim — the real app now lives in `app.main`.

Kept so that existing tooling (`uvicorn api:app`, start.sh, test scripts)
continues to work while the codebase transitions to the routered layout.
New routes should be added under `app/routers/` rather than here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.main import app  # noqa: F401  -- re-exported for `uvicorn api:app`


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
