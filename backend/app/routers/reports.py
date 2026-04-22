"""Report downloads — serves generated Excel files to the browser."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..deps import OUTPUT_DIR

router = APIRouter(tags=["reports"])


@router.get("/report/{filename}")
def download_report(filename: str) -> FileResponse:
    """Download a generated Excel report (.xlsx)."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{filename}' not found")
    # Force attachment disposition + proper xlsx mime so browsers never
    # sniff it as HTML (which was producing `.xlsx.html` saves).
    return FileResponse(
        str(path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
