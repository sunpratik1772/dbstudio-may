"""
Golden-path test — loads the canonical FX Front-Running workflow,
runs it through the HTTP layer, and asserts the contract that
everything downstream (UI, audit, reports) relies on:

  * HTTP 200
  * disposition is one of the declared enum values
  * run_id is populated and stamped on the response
  * output port contract check passed (no exception)
  * report path points at a real xlsx on disk

This guards against handler regressions — if anyone breaks the
wiring between registry, dag_runner, validator or context, this
test fails loudly before the frontend ever sees it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


FX_WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "fx_fro_v2_workflow.json"

ALERT = {
    "trader_id": "T1",
    "book": "B1",
    "alert_date": "2024-01-01",
    "currency_pair": "EUR/USD",
    "alert_id": "A1",
    "event_time": "2024-01-01 09:00",
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def fx_dag():
    if not FX_WORKFLOW.exists():
        pytest.skip(f"fixture workflow not found: {FX_WORKFLOW}")
    return json.loads(FX_WORKFLOW.read_text())


class TestGoldenPath:
    def test_run_returns_200(self, client, fx_dag):
        r = client.post("/run", json={"dag": fx_dag, "alert_payload": ALERT})
        assert r.status_code == 200, r.text

    def test_run_id_is_present(self, client, fx_dag):
        r = client.post("/run", json={"dag": fx_dag, "alert_payload": ALERT})
        data = r.json()
        assert "run_id" in data
        assert isinstance(data["run_id"], str) and len(data["run_id"]) >= 16

    def test_disposition_is_valid(self, client, fx_dag):
        r = client.post("/run", json={"dag": fx_dag, "alert_payload": ALERT})
        data = r.json()
        assert data["disposition"] in {"DISMISS", "REVIEW", "ESCALATE"}

    def test_report_written_to_disk(self, client, fx_dag):
        r = client.post("/run", json={"dag": fx_dag, "alert_payload": ALERT})
        data = r.json()
        path = Path(data["report_path"])
        assert path.exists(), f"report missing: {path}"
        assert path.suffix == ".xlsx"


class TestStreamingRun:
    """Every SSE frame carries the same run_id as the final result."""

    def test_every_frame_stamped_with_run_id(self, client, fx_dag):
        frames: list[dict] = []
        with client.stream(
            "POST",
            "/run/stream",
            json={"dag": fx_dag, "alert_payload": ALERT},
        ) as resp:
            assert resp.status_code == 200
            buf = ""
            for chunk in resp.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    raw, buf = buf.split("\n\n", 1)
                    for line in raw.splitlines():
                        if line.startswith("data: "):
                            frames.append(json.loads(line[len("data: "):]))

        assert frames, "no SSE frames received"
        run_ids = {f.get("run_id") for f in frames}
        # Exactly one run_id across all frames, and it's non-empty.
        assert len(run_ids) == 1
        (rid,) = run_ids
        assert rid and isinstance(rid, str) and len(rid) >= 16

        # And we see the full lifecycle.
        kinds = {f["type"] for f in frames}
        assert {"workflow_start", "node_start", "node_complete", "workflow_complete"} <= kinds
