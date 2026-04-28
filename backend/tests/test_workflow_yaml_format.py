from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers.workflows import _load, _save
from engine.workflow_format import workflow_from_yaml, workflow_to_yaml


def _sample_workflow() -> dict:
    return {
        "schema_version": "1.0",
        "workflow_id": "yaml_demo",
        "name": "YAML Demo",
        "version": "0.1.0",
        "nodes": [
            {
                "id": "n01",
                "type": "ALERT_TRIGGER",
                "label": "Alert",
                "config": {},
            }
        ],
        "edges": [],
    }


def test_workflow_yaml_round_trip_preserves_runtime_shape() -> None:
    workflow = _sample_workflow()

    text = workflow_to_yaml(workflow)
    assert "workflow_id: yaml_demo" in text
    assert "type: ALERT_TRIGGER" in text

    assert workflow_from_yaml(text) == workflow


def test_workflow_format_endpoints_convert_yaml_and_json() -> None:
    client = TestClient(app)
    workflow = _sample_workflow()
    yaml_text = workflow_to_yaml(workflow)

    parsed = client.post("/workflow-format/yaml-to-json", json={"content": yaml_text})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["workflow"] == workflow

    rendered = client.post("/workflow-format/json-to-yaml", json={"workflow": workflow})
    assert rendered.status_code == 200, rendered.text
    assert workflow_from_yaml(rendered.json()["content"]) == workflow


def test_workflow_store_helpers_read_and_write_yaml(tmp_path: Path) -> None:
    filename = "yaml-demo.yaml"
    workflow = _sample_workflow()

    saved = _save(tmp_path, filename, workflow)
    assert saved["saved"] == filename
    assert (tmp_path / filename).read_text().startswith("schema_version:")
    assert _load(tmp_path, filename) == workflow

