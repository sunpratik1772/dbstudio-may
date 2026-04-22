"""
Adapter over `engine.validator.validate_dag`.

This layer exists so the harness depends on a small stable interface
rather than directly on the engine. Swapping in a different validator
(or adding post-validator scoring) becomes a local change here.
"""
from __future__ import annotations

from engine.validator import validate_dag


class ValidatorAdapter:
    """Stateless wrapper around the deterministic DAG validator."""

    def validate(self, workflow: dict | None) -> dict:
        """Return a `ValidationResult.to_json()` payload.

        When the workflow is `None` (model produced unparseable JSON)
        we return a synthetic failure so the harness can still reason
        about it uniformly.
        """
        if workflow is None:
            return {
                "valid": False,
                "errors": [
                    {
                        "code": "UNPARSEABLE_JSON",
                        "message": (
                            "Model output did not contain a parseable JSON object."
                        ),
                        "severity": "error",
                        "node_id": None,
                        "field": None,
                    }
                ],
                "warnings": [],
                "summary": "unparseable JSON",
            }
        return validate_dag(workflow).to_json()
