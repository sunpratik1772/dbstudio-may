"""
Canonical inventory of validator / schema error codes.

Before this module, ~30 error-code string literals were sprinkled
across `validator.py`, `schema_version.py`, `auto_fixer.py`, and any
tests that asserted on codes. Typos failed silently (no import-time
check), the codes had no docstring, and renames required a grep.

`ValidationErrorCode` is a `str`-based enum so:

  * Existing JSON payloads, tests, and contracts don't change — a
    member's value IS the string that used to be hardcoded.
  * `issue.code == "UNKNOWN_TYPE"` still works for legacy callers.
  * Typos become import errors.
  * IDEs autocomplete the full list + docstring on hover.

Keep this sorted alphabetically. When adding a new rule, add the
member here first, then reference it at the call site — that
guarantees the audit trail stays in one place.
"""
from __future__ import annotations

from enum import Enum


class ValidationErrorCode(str, Enum):
    """Stable machine-readable identifiers for validator issues.

    Severity is NOT encoded here — the same code can fire as a
    warning (copilot auto-fixable) in one context and an error
    (blocks `/run`) in another. Severity lives on `ValidationIssue`.
    """

    # ── Schema / top-level shape ───────────────────────────────
    BAD_SCHEMA_VERSION = "BAD_SCHEMA_VERSION"
    """`schema_version` field is malformed (wrong type or not dotted-number)."""

    SCHEMA_TOO_NEW = "SCHEMA_TOO_NEW"
    """Workflow declares a schema newer than the engine supports."""

    SCHEMA_TOO_OLD = "SCHEMA_TOO_OLD"
    """Workflow declares a schema below the engine's minimum — migrate offline."""

    MIGRATION_MISSING = "MIGRATION_MISSING"
    """No migration path registered between two schema versions."""

    BAD_SHAPE = "BAD_SHAPE"
    """DAG is not a dict / has malformed top-level structure."""

    EMPTY_WORKFLOW = "EMPTY_WORKFLOW"
    """`nodes` list is empty — nothing to run."""

    MISSING_NODES = "MISSING_NODES"
    """`nodes` key is missing or not a list."""

    BAD_EDGES = "BAD_EDGES"
    """`edges` is not a list (or shaped wrong at the top level)."""

    # ── Per-node identity / registry ───────────────────────────
    MISSING_TYPE = "MISSING_TYPE"
    """A node has no `type` field."""

    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    """`type` doesn't resolve to any registered NodeSpec."""

    MISSING_LABEL = "MISSING_LABEL"
    """Node has no human-readable `label`."""

    # ── Per-node config / params ───────────────────────────────
    BAD_CONFIG = "BAD_CONFIG"
    """`config` is not a dict."""

    MISSING_REQUIRED_PARAM = "MISSING_REQUIRED_PARAM"
    """A ParamSpec with `required=True` has no value."""

    BAD_PARAM_TYPE = "BAD_PARAM_TYPE"
    """Config value doesn't match its ParamSpec type / is uncoercible."""

    BAD_PROMPT_TEMPLATE = "BAD_PROMPT_TEMPLATE"
    """Prompt template has malformed braces and cannot be rendered safely."""

    BAD_PROMPT_REF = "BAD_PROMPT_REF"
    """Prompt template references an unknown dataset column/ref."""

    BAD_ENUM_VALUE = "BAD_ENUM_VALUE"
    """Config value not in the ParamSpec's enum."""

    # ── Edges / wiring ─────────────────────────────────────────
    BAD_EDGE = "BAD_EDGE"
    """Single edge is malformed (missing `from`/`to`, wrong keys)."""

    EDGE_DANGLING = "EDGE_DANGLING"
    """Edge references a node id that doesn't exist."""

    CYCLE = "CYCLE"
    """DAG has a cycle — topological sort would fail."""

    ORPHAN_NODE = "ORPHAN_NODE"
    """Node has no incoming / outgoing edges and isn't entry/exit."""

    UNWIRED_INPUT = "UNWIRED_INPUT"
    """Node declares an input_name that no upstream output produces."""

    # ── Entry / exit invariants ────────────────────────────────
    NO_ENTRY = "NO_ENTRY"
    """No node is marked as the alert trigger / entry point."""

    MULTIPLE_ENTRIES = "MULTIPLE_ENTRIES"
    """More than one ALERT_TRIGGER present."""

    WRONG_ENTRY_ID = "WRONG_ENTRY_ID"
    """Entry trigger exists but its id isn't the expected `n01`."""

    ENTRY_HAS_INPUT = "ENTRY_HAS_INPUT"
    """Entry node has an incoming edge — it must be the root."""

    NO_EXIT = "NO_EXIT"
    """No REPORT_OUTPUT node present."""

    EXIT_HAS_OUTPUT = "EXIT_HAS_OUTPUT"
    """Exit node has an outgoing edge — it must be terminal."""

    # ── Column / schema validation ─────────────────────────────
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    """`field_bindings[].field` references a column not in the resolved DataSource."""

    # ── Surveillance hard rules ────────────────────────────────
    MISSING_TRADE_VERSION = "MISSING_TRADE_VERSION"
    """`hs_execution` query_template missing the hardcoded `trade_version:1`."""

    MISSING_SCRIPT = "MISSING_SCRIPT"
    """SIGNAL_CALCULATOR in `upload_script` mode without `script_content`."""

    SCRIPT_PATH_ONLY = "SCRIPT_PATH_ONLY"
    """Custom signal references a `script_path` that doesn't exist on disk."""

    UPLOAD_SCRIPT_DISABLED = "UPLOAD_SCRIPT_DISABLED"
    """SIGNAL_CALCULATOR.upload_script is disabled in this environment (DBSHERPA_ALLOW_UPLOAD_SCRIPT not set)."""


# Backwards-compat alias: some older imports reached for `ErrorCode`.
# Keep it resolving to `str` so type hints stay boolean-compatible.
ErrorCode = str
