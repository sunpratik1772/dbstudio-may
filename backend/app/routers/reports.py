"""Report downloads — serves generated Excel files to the browser.

Report files are written by REPORT_OUTPUT under `OUTPUT_DIR` from
`app.deps` (`DBSHERPA_OUTPUT_DIR`, defaulting to backend/output). The
frontend receives a URL containing only the report basename, not an
arbitrary path. Keep this router narrow: it is a file download boundary,
not a general static-file server.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..deps import OUTPUT_DIR

router = APIRouter(tags=["reports"])


@router.get("/report/{filename}")
def download_report(filename: str) -> FileResponse:
    """Download a generated Excel report (.xlsx) by basename."""
    safe = Path(filename).name
    if safe != filename:
        raise HTTPException(status_code=400, detail="filename must be a bare filename")
    path = OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{safe}' not found")
    # Force attachment disposition + proper xlsx mime so browsers never
    # sniff it as HTML (which was producing `.xlsx.html` saves).
    return FileResponse(
        str(path),
        filename=safe,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
