"""
Guardrails for the ValidationErrorCode enum.

These tests don't exercise validator *logic* (that's covered by
test_validator.py) — they pin the wire-compatibility of the enum so
a future refactor can't silently break clients that still compare
against plain strings.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from engine.validation_codes import ValidationErrorCode
from engine.validator import ValidationIssue, ValidationResult, validate_dag


def test_enum_value_is_identical_to_its_name() -> None:
    """Every member's value must equal its name. This is the invariant
    that lets string literals and enum members be used interchangeably
    in dict keys, comparisons, and JSON."""
    for member in ValidationErrorCode:
        assert member.value == member.name


def test_enum_member_equals_plain_string() -> None:
    """Wire compat: clients / frontend code that stores string codes
    from historical JSON must still match against enum members."""
    assert ValidationErrorCode.UNKNOWN_TYPE == "UNKNOWN_TYPE"
    assert "UNKNOWN_TYPE" == ValidationErrorCode.UNKNOWN_TYPE


def test_enum_hashes_as_string() -> None:
    """Dict-key compat: `_RULES.get(err_code_string)` must find an
    entry keyed by the enum member, and vice versa."""
    d: dict = {ValidationErrorCode.BAD_CONFIG: 1}
    assert d["BAD_CONFIG"] == 1
    assert d[ValidationErrorCode.BAD_CONFIG] == 1


def test_validation_issue_serialises_to_plain_string() -> None:
    """`ValidationIssue.to_json()` must produce a JSON-serialisable dict
    with the code as a plain string — the frontend contract depends on
    exactly this. (asdict + json.dumps should round-trip cleanly.)"""
    issue = ValidationIssue(
        code=ValidationErrorCode.UNKNOWN_TYPE,
        message="Node 'n02' has unknown type 'WIDGET'.",
        node_id="n02",
        field="type",
    )
    as_dict = issue.to_json()
    encoded = json.dumps(as_dict)
    decoded = json.loads(encoded)
    assert decoded["code"] == "UNKNOWN_TYPE"
    assert isinstance(decoded["code"], str)


def test_full_validate_path_emits_enum_codes() -> None:
    """End-to-end: submit a deliberately broken DAG through the
    public validator API and confirm every reported issue carries
    a code that resolves back to an enum member."""
    result: ValidationResult = validate_dag({
        "nodes": [{"id": "n01", "type": "NOT_A_REAL_NODE", "label": "x"}],
        "edges": [],
    })
    assert not result.valid
    for issue in result.issues:
        # Every code must be a recognised enum value — this catches
        # any future rule that forgets to add a new ValidationErrorCode.
        assert issue.code in {m.value for m in ValidationErrorCode}, (
            f"Unknown code {issue.code!r} leaked past the validator"
        )


def test_every_rule_in_autofixer_is_a_valid_code() -> None:
    """The auto-fixer dispatch table must only key on codes the
    validator could actually emit. This is a 'no orphan rules' check."""
    from agent.repair.auto_fixer import _RULES

    valid = {m for m in ValidationErrorCode}
    unknown = set(_RULES.keys()) - valid
    assert not unknown, f"Auto-fixer keyed on unknown codes: {unknown}"


def test_asdict_preserves_code_as_string() -> None:
    """`dataclasses.asdict` on a ValidationIssue must not produce an
    enum instance in the dict — JSON serialisation downstream assumes
    a plain string."""
    issue = ValidationIssue(code=ValidationErrorCode.CYCLE, message="cycle")
    as_dict = asdict(issue)
    # Still a str at the type level (str-enum subclasses str), so it
    # serialises through json.dumps cleanly.
    assert isinstance(as_dict["code"], str)
    assert as_dict["code"] == "CYCLE"
