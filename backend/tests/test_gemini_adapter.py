"""
Unit tests for `GeminiAdapter`.

We don't hit the real API — a fake `google.genai` module is injected
via `sys.modules` so every request shape is asserted against a mock
client. The tests pin the behaviours downstream code depends on:

* `chat_turn` renders history with "assistant" → "model" role mapping.
* `chat_turn` pins `temperature=0` + JSON mime by default (the planner
  depends on reproducibility).
* `single_shot` passes `max_output_tokens` through when set.
* The adapter is stateless / freezable — it's a `@dataclass(frozen=True)`.
* Lazy SDK import: building an adapter instance must NOT import google.genai.
"""
from __future__ import annotations

import sys
import types
from dataclasses import FrozenInstanceError
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fake google.genai SDK — installed into sys.modules before the adapter
# ever calls `_sdk()`, so the real package is never loaded in this test.
# ---------------------------------------------------------------------------
class _FakeContent:
    def __init__(self, role: str, parts: list[Any]) -> None:
        self.role = role
        self.parts = parts

    def __repr__(self) -> str:  # pragma: no cover - debug only
        text = "|".join(getattr(p, "text", "") for p in self.parts)
        return f"Content(role={self.role!r}, text={text!r})"


class _FakePart:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, recorder: dict) -> None:
        self._recorder = recorder

    def generate_content(self, *, model: str, contents: Any, config: Any) -> _FakeResponse:
        self._recorder["model"] = model
        self._recorder["contents"] = contents
        self._recorder["config"] = config.kwargs
        return _FakeResponse(text=self._recorder.get("reply", "ok"))


class _FakeClient:
    def __init__(self, *, api_key: str, recorder: dict) -> None:
        recorder["api_key"] = api_key
        self.models = _FakeModels(recorder)


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Install a fake `google` + `google.genai` + `google.genai.types`
    into sys.modules. Returns a recorder dict the tests inspect after
    the adapter fires a request."""
    recorder: dict = {}

    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    types_mod = types.ModuleType("google.genai.types")

    genai_mod.Client = lambda api_key: _FakeClient(api_key=api_key, recorder=recorder)
    types_mod.Content = _FakeContent
    types_mod.Part = _FakePart
    types_mod.GenerateContentConfig = _FakeConfig

    # Wire the tree so `from google import genai` resolves.
    google_mod.genai = genai_mod
    genai_mod.types = types_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)

    # Ensure the adapter can read an API key deterministically.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return recorder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_adapter_is_frozen() -> None:
    """Adapter is a frozen dataclass — safe to stash in a global / module."""
    from llm import GeminiAdapter

    a = GeminiAdapter()
    with pytest.raises(FrozenInstanceError):
        a.default_model = "other-model"  # type: ignore[misc]


def test_chat_turn_translates_history_roles(fake_sdk: dict) -> None:
    from llm import GeminiAdapter

    fake_sdk["reply"] = "{\"ok\": true}"
    out = GeminiAdapter().chat_turn(
        system_prompt="SYS",
        history=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ],
        user_turn="now",
    )
    assert out == "{\"ok\": true}"

    contents = fake_sdk["contents"]
    # 3 entries: the 2 history turns + the current user_turn.
    assert [c.role for c in contents] == ["user", "model", "user"]
    # Roles and text round-trip cleanly.
    assert contents[0].parts[0].text == "u1"
    assert contents[1].parts[0].text == "a1"
    assert contents[2].parts[0].text == "now"


def test_chat_turn_default_pins_determinism(fake_sdk: dict) -> None:
    """Planner relies on temperature=0 + JSON mime for reproducible drafts."""
    from llm import GeminiAdapter

    GeminiAdapter().chat_turn(system_prompt="S", history=[], user_turn="hi")
    cfg = fake_sdk["config"]
    assert cfg["system_instruction"] == "S"
    assert cfg["temperature"] == 0.0
    assert cfg["response_mime_type"] == "application/json"


def test_chat_turn_can_opt_out_of_json(fake_sdk: dict) -> None:
    """Chat endpoint wants prose, not JSON — json_mode=False must NOT
    attach `response_mime_type`."""
    from llm import GeminiAdapter

    GeminiAdapter().chat_turn(
        system_prompt="S", history=[], user_turn="hi",
        temperature=0.3, json_mode=False,
    )
    cfg = fake_sdk["config"]
    assert "response_mime_type" not in cfg
    assert cfg["temperature"] == 0.3


def test_single_shot_passes_token_budget(fake_sdk: dict) -> None:
    """Summary nodes cap tokens via NODE_SPEC — the adapter must forward it."""
    from llm import GeminiAdapter

    fake_sdk["reply"] = "narrative"
    out = GeminiAdapter().single_shot(
        "write a summary",
        temperature=0.2,
        max_output_tokens=600,
    )
    assert out == "narrative"
    cfg = fake_sdk["config"]
    assert cfg["temperature"] == 0.2
    assert cfg["max_output_tokens"] == 600
    # No system prompt was passed, so it must NOT be in the config.
    assert "system_instruction" not in cfg
    # Single-shot passes the raw prompt string as contents.
    assert fake_sdk["contents"] == "write a summary"


def test_single_shot_omits_optional_fields(fake_sdk: dict) -> None:
    """Both `system_prompt` and `max_output_tokens` are opt-in — default
    calls should not populate them."""
    from llm import GeminiAdapter

    GeminiAdapter().single_shot("p")
    cfg = fake_sdk["config"]
    assert "system_instruction" not in cfg
    assert "max_output_tokens" not in cfg


def test_api_key_pulled_from_configured_env(monkeypatch: pytest.MonkeyPatch, fake_sdk: dict) -> None:
    """Overriding `api_key_env` lets callers pick a different key per
    adapter (useful for dev/prod split without code changes)."""
    from llm import GeminiAdapter

    monkeypatch.setenv("CUSTOM_GEMINI_KEY", "prod-key")
    GeminiAdapter(api_key_env="CUSTOM_GEMINI_KEY").single_shot("p")
    assert fake_sdk["api_key"] == "prod-key"


def test_get_default_adapter_is_cached() -> None:
    """Process-wide singleton — repeated lookups return the same instance."""
    from llm import get_default_adapter

    a = get_default_adapter()
    b = get_default_adapter()
    assert a is b


def test_planner_uses_adapter(fake_sdk: dict) -> None:
    """End-to-end: Planner now routes through the adapter, so a single
    fake SDK covers every workflow-generation call site."""
    from agent.planner import Planner

    fake_sdk["reply"] = '{"workflow_id": "x", "nodes": [], "edges": []}'
    result = Planner().generate(
        system_prompt="S", history=[], user_turn="make one",
    )
    assert result.raw.startswith("{")
    assert result.workflow == {"workflow_id": "x", "nodes": [], "edges": []}
    # The planner must have used JSON mode (determinism guarantee).
    assert fake_sdk["config"]["response_mime_type"] == "application/json"
    assert fake_sdk["config"]["temperature"] == 0.0
