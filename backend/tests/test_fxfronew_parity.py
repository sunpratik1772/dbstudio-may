"""
fxfronew: POST /run and direct engine run agree; /validate accepts on-disk relative mock paths.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers.run import _resolve_workflow_mock_csv_paths
from engine.dag_runner import run_workflow

BACKEND = Path(__file__).resolve().parents[1]
FXFRONEW = BACKEND / "workflows" / "fxfronew_workflow.json"
ALERT = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "currency_pair": "EUR/USD",
    "alert_date": "2024-01-15",
    "alert_id": "P-1",
}


def _raw_dag() -> dict:
    return json.loads(FXFRONEW.read_text())


def test_post_run_matches_engine_for_fxfronew() -> None:
    """UI sends the same JSON as the file; /run resolves demo_data/ paths like the test helper."""
    raw = _raw_dag()
    ctx = run_workflow(_resolve_workflow_mock_csv_paths(json.loads(json.dumps(raw))), ALERT)

    client = TestClient(app)
    r = client.post("/run", json={"dag": raw, "alert_payload": ALERT})
    assert r.status_code == 200, r.text
    data = r.json()
    assert sorted(data["datasets"]) == sorted(ctx.datasets.keys())
    assert data["disposition"] == ctx.disposition
    assert data["flag_count"] == ctx.get("flag_count", 0)
    assert (
        Path(data["report_path"]).name
        == Path(ctx.report_path).name
        == "fxfronew_report.xlsx"
    )
    p_api = Path(data["report_path"])
    p_eng = Path(ctx.report_path)
    assert p_api.exists() and p_eng.exists()
    assert p_api.stat().st_size > 0 and p_eng.stat().st_size > 0


def test_post_validate_succeeds_on_unresolved_mock_paths() -> None:
    r = TestClient(app).post("/validate", json={"dag": _raw_dag()})
    assert r.status_code == 200
    out = r.json()
    assert out.get("valid") is True, out
