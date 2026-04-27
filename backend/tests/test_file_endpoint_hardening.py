"""Regression tests for file-serving path boundaries.

These endpoints intentionally serve only files under configured backend
directories. Tests call the router functions directly so they catch the path
sanitisation rule even if a particular ASGI router would reject slashes first.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.copilot import get_skill
from app.routers.reports import download_report


def test_report_download_rejects_path_traversal() -> None:
    with pytest.raises(HTTPException) as exc:
        download_report("../secret.xlsx")

    assert exc.value.status_code == 400
    assert "bare filename" in exc.value.detail


def test_skill_download_rejects_path_traversal() -> None:
    with pytest.raises(HTTPException) as exc:
        get_skill("../secret")

    assert exc.value.status_code == 400
    assert "bare filename" in exc.value.detail
