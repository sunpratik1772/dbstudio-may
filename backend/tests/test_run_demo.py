"""
Integration test for `POST /run/demo`.

This is the "reviewer demo" surface — a reviewer curling the endpoint
with an empty body should always get back a real xlsx attachment with
run metadata on the response headers. If any handler, the CSV
override wiring, or the report node regresses, this test catches it
before it hits a live deployment.
"""
from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_run_demo_returns_xlsx_attachment(client: TestClient) -> None:
    resp = client.post("/run/demo", json={})
    assert resp.status_code == 200, resp.text

    # Attachment metadata
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp and ".xlsx" in disp

    # Run metadata surfaced via custom headers — lets curl / fetch
    # users correlate with backend logs without opening the xlsx.
    run_id = resp.headers.get("X-Run-Id", "")
    assert len(run_id) == 32, f"unexpected run_id: {run_id!r}"
    assert resp.headers.get("X-Disposition") in {"ESCALATE", "REVIEW", "DISMISS"}
    assert int(resp.headers["X-Flag-Count"]) >= 0

    # Real xlsx = valid ZIP archive containing the standard OOXML
    # parts. Catches the case where the report accidentally becomes
    # an HTML file (old bug) or the transfer truncates.
    assert resp.content[:4] == b"PK\x03\x04", "body is not a ZIP"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
    assert "xl/workbook.xml" in names
    # Each workflow tab lands on its own sheet — we expect at least
    # the four data-tab sheets + the summary sheet.
    sheet_count = sum(1 for n in names if n.startswith("xl/worksheets/sheet"))
    assert sheet_count >= 4, f"too few sheets: {sheet_count}"


def test_run_demo_return_json_path(client: TestClient) -> None:
    resp = client.post("/run/demo", json={"return_json": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["disposition"] in {"ESCALATE", "REVIEW", "DISMISS"}
    assert body["run_id"] and len(body["run_id"]) == 32
    assert body["download_url"].startswith("/report/")
    # Demo runs the v2 chassis workflow → these are the canonical dataset names.
    for expected in ("orders", "executions", "comms", "market", "executions_signals"):
        assert expected in body["datasets"], body["datasets"]


def test_run_demo_rejects_path_traversal(client: TestClient) -> None:
    # Security sanity: callers must not be able to escape the
    # workflows directory via `../`.
    resp = client.post("/run/demo", json={"workflow_filename": "../etc/passwd"})
    assert resp.status_code == 400
    assert "bare filename" in resp.text
