"""Tests for the Copilot guardrail manifest shown in the Plan UI."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_copilot_guardrails_exposes_live_constraints(monkeypatch) -> None:
    monkeypatch.delenv("DBSHERPA_ALLOW_UPLOAD_SCRIPT", raising=False)

    resp = TestClient(app).get("/copilot/guardrails")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(n["type_id"] == "SIGNAL_CALCULATOR" for n in body["nodes"])
    assert body["data_sources"]
    assert body["skills"]
    assert body["capabilities"]["upload_script_enabled"] is False
    assert body["capabilities"]["allowed_signal_modes"] == ["configure"]
    assert any("NodeSpec" in rule for rule in body["rules"])
