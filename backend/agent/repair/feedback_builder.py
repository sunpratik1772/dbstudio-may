"""
Render validator errors into a focused repair brief for the LLM.

Rule of thumb: the LLM fixes *specific* issues far more reliably than
it re-evaluates a checklist. We give it a structured fault list keyed
by `code`, `node_id`, and `field`, and tell it to return the complete
corrected JSON — nothing else.
"""
from __future__ import annotations

# Truncating avoids overwhelming the model when a skeleton workflow has
# hundreds of cascading errors — the structural ones come first, and
# fixing them usually eliminates the rest.
_MAX_ERRORS_PER_BRIEF = 12


def build_feedback(errors: list[dict], attempt: int, total: int) -> str:
    """Build the user-turn repair prompt from a validator error list."""
    if not errors:
        # Shouldn't happen — caller should only invoke us when invalid —
        # but belt-and-braces for unexpected empty lists.
        return (
            f"REPAIR {attempt}/{total}: validator still reported issues but the "
            "error list is empty. Re-emit the complete workflow JSON."
        )

    # Special case: when the previous attempt produced unparseable JSON,
    # the single error tells the model everything it needs to know.
    if len(errors) == 1 and errors[0].get("code") == "UNPARSEABLE_JSON":
        return (
            "Your previous response was not valid JSON. Re-emit the complete "
            "workflow as a single JSON object with no prose, no markdown "
            "fences, no commentary."
        )

    lines = [
        f"REPAIR {attempt}/{total}: The deterministic validator found the "
        "following issues. Fix ONLY these; keep everything else intact. "
        "Return the COMPLETE corrected JSON (not a diff, no markdown, no prose):",
        "",
    ]
    for e in errors[:_MAX_ERRORS_PER_BRIEF]:
        bits = [f"[{e.get('code','ERROR')}]"]
        if e.get("node_id"):
            bits.append(f"node={e['node_id']}")
        if e.get("field"):
            bits.append(f"field={e['field']}")
        bits.append(e.get("message", ""))
        lines.append(f"- {' '.join(bits)}")
    overflow = len(errors) - _MAX_ERRORS_PER_BRIEF
    if overflow > 0:
        lines.append(f"- …and {overflow} more (fix the above first).")
    lines.append("")
    lines.append("Produce the full workflow JSON now.")
    return "\n".join(lines)
