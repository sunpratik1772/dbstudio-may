"""
GeminiAdapter — the single Gemini seam for the whole backend.

Covers the two request shapes that exist in the codebase:

  * `chat_turn` — system prompt + message history + current user
    message. Used by the planner's workflow generation loop and by
    `/copilot/chat`.

  * `single_shot` — one prompt in, narrative text out. Used by
    `section_summary` and `consolidated_summary` node handlers.

Both paths delegate to `_build_client()` / `_call_model()` so vendor
config (API key, model selection, SDK imports) lives in exactly one
place. The google-genai import stays lazy so tests and environments
without the SDK installed still parse this file.

Deterministic pins:

  * Planner calls default to `temperature=0` + JSON response mime
    type — same prompt → same draft, which the repair loop relies on
    to be reproducible.
  * Narrative calls default to `temperature=0.2` with an
    `max_output_tokens` cap — prose gets slight variability but
    stays within NODE_SPEC budgets.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


# Keep the default model in ONE place. Overrides are explicit
# per-call so unusual sites (e.g. Pro for long summaries later)
# don't need to touch this constant.
DEFAULT_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class GeminiAdapter:
    """
    Thin wrapper around the google-genai SDK.

    Stateless on purpose: the adapter holds only config (default
    model + API-key env var name). One instance is typically enough
    for the whole process — see `get_default_adapter()`.
    """

    default_model: str = DEFAULT_MODEL
    api_key_env: str = "GEMINI_API_KEY"

    # ──────────────────────────────────────────────────────────────
    # Public shapes
    # ──────────────────────────────────────────────────────────────
    def chat_turn(
        self,
        *,
        system_prompt: str,
        history: list[dict],
        user_turn: str,
        model: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        """
        Send one user turn through Gemini's chat interface.

        `history` is a list of `{"role": "user"|"assistant", "content": str}`
        dicts (the shape the agent harness and chat endpoint both keep).
        We translate "assistant" → "model" for the SDK.

        Returns the raw response text (never None — empty string if
        the model produced nothing parsable).
        """
        genai, types = self._sdk()
        client = self._build_client(genai)

        contents = []
        for m in history:
            role = "user" if m.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=m.get("content", ""))]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_turn)]))

        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "temperature": temperature,
        }
        if json_mode:
            # Gemini's JSON mode asks the model to emit a JSON object
            # directly. Saves us from the markdown-fence extraction
            # dance on the happy path, while the planner still runs a
            # regex fallback just in case.
            config_kwargs["response_mime_type"] = "application/json"

        resp = client.models.generate_content(
            model=model or self.default_model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return resp.text or ""

    def single_shot(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Fire one prompt → one response. Used for narrative /
        summary generation where there's no conversation history.

        Exceptions bubble up — callers (the summary nodes) wrap in
        their own `try/except` to degrade to `"[LLM unavailable …]"`
        since those nodes must not fail the whole run when Gemini is
        down.
        """
        genai, types = self._sdk()
        client = self._build_client(genai)

        config_kwargs: dict = {"temperature": temperature}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens

        resp = client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return resp.text or ""

    # ──────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _sdk():
        """Lazy import so the module stays importable when the SDK
        isn't installed (e.g. lint-only CI containers)."""
        from google import genai
        from google.genai import types
        return genai, types

    def _build_client(self, genai):
        api_key = os.environ.get(self.api_key_env, "")
        if not api_key:
            logger.warning(
                "%s is empty; Gemini calls will fail until it's set",
                self.api_key_env,
            )
        return genai.Client(api_key=api_key)


@lru_cache(maxsize=1)
def get_default_adapter() -> GeminiAdapter:
    """
    Process-wide default adapter.

    Callers that want to inject a different instance (tests, or a
    future provider switch) build their own `GeminiAdapter(...)` and
    pass it into the relevant constructor. The `lru_cache` is just
    ergonomic — it does not gate testability because every caller
    that reaches it also accepts an explicit adapter.
    """
    return GeminiAdapter()
