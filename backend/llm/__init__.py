"""
Single seam for every LLM call in the codebase.

Before this module, four files (planner, chat endpoint, section
summary node, consolidated summary node) each instantiated the
google-genai client, built `contents`, and called `generate_content`.
That's duplication on three axes:

  * API-key config (all four sniffed `os.environ["GEMINI_API_KEY"]`)
  * SDK coupling (`from google import genai` repeated everywhere)
  * Request shape (history rendering, token budgets, response mode)

`GeminiAdapter` consolidates these into two entry-points that cover
every shape we actually use:

  * `chat_turn(system, history, user)`   — multi-turn with history
  * `single_shot(prompt, …)`             — one-prompt narrative

Callers depend on the adapter module — they don't know google-genai
exists. Swapping vendors is a one-file change.
"""
from .gemini_adapter import GeminiAdapter, get_default_adapter

__all__ = ["GeminiAdapter", "get_default_adapter"]
