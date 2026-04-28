"""Workflow YAML/JSON conversion helpers.

The engine, validator, and runner all operate on the same in-memory Python
dict shape. YAML is only a human-facing authoring format at the edges:
files on disk, import/export, and docs. Keeping conversion here prevents YAML
parsing details from leaking into the runner.
"""
from __future__ import annotations

from typing import Any

import yaml


def workflow_from_yaml(text: str) -> dict[str, Any]:
    """Parse a workflow YAML document into the JSON-compatible DAG dict."""
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("Workflow YAML must contain a mapping/object at the top level")
    return loaded


def workflow_to_yaml(dag: dict[str, Any]) -> str:
    """Render a workflow DAG dict as readable YAML."""
    return yaml.safe_dump(
        dag,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )

