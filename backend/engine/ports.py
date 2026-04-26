"""
Typed port + parameter specifications.

The legacy registry (engine/registry.py) describes a node's inputs, outputs
and config fields as `dict[str, str]` — keys are the name, values are a
free-text description. That's good enough for a human-readable contracts
document, but:

  * We can't validate wiring programmatically (no `type` field).
  * The UI has to string-sniff the description to guess widget types
    ("contains the word boolean → render a checkbox"). Fragile.
  * The copilot self-corrector can only be a textual checklist; it can't
    consume structured feedback like "input `trades` expected dataframe,
    upstream produced scalar".

This module introduces `PortSpec` (typed IO) and `ParamSpec` (typed config
with UI hints). A node can opt in one at a time — until it does, the
registry synthesises best-effort specs from the legacy dicts so nothing
downstream breaks.

The types here intentionally have zero coupling to FastAPI, pandas, the
dag_runner or the copilot. They're pure, picklable data classes that can
be serialised to JSON for the frontend and for the contracts document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Type enums — closed sets. Add values here rather than using magic strings
# elsewhere; every layer (executor, validator, UI) consumes these.
# ---------------------------------------------------------------------------
class PortType(str, Enum):
    """What flows along an edge between two nodes."""

    DATAFRAME = "dataframe"   # pandas.DataFrame carried in ctx.datasets
    SCALAR = "scalar"         # int/float/str stored in ctx.values
    OBJECT = "object"         # dict / nested structure (e.g. sections)
    TEXT = "text"             # free-form string (e.g. executive_summary)


class ParamType(str, Enum):
    """What a config field holds."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    STRING_LIST = "string_list"
    OBJECT = "object"         # JSON object (dict)
    ARRAY = "array"           # JSON array (list of objects or mixed)
    INPUT_REF = "input_ref"   # references an upstream output_name
    CODE = "code"             # inline Python snippet


class Widget(str, Enum):
    """UI rendering hint for a ParamSpec. The frontend chooses an editor
    based on this; nothing else on the backend cares."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    SELECT = "select"
    CHIPS = "chips"           # string_list as removable chips
    JSON = "json"             # object as monaco-json
    INPUT_REF = "input_ref"   # dropdown of upstream output_names
    CODE = "code"             # monaco-python


# ---------------------------------------------------------------------------
# Port + Param specs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PortSpec:
    """A typed input or output of a function/node."""

    name: str
    type: PortType
    description: str = ""
    optional: bool = False
    # For DATAFRAME — enforced on the resolved DataFrame (input or output).
    required_columns: tuple[str, ...] = field(default_factory=tuple)
    # For OBJECT — enforced when a dict is resolved for this port.
    required_keys: tuple[str, ...] = field(default_factory=tuple)
    # For input DATAFRAME — which config key holds the ctx.datasets name
    # (default in the runner: "input_name" when required_columns is set).
    source_config_key: str | None = None
    # For output ports — explicit storage path used by dag_runner contract
    # checks, e.g. "ctx.datasets[{output_name}]" or "ctx.values[flag_count]".
    store_at: str | None = None

    def to_json(self) -> dict:
        out: dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "optional": self.optional,
        }
        if self.required_columns:
            out["required_columns"] = list(self.required_columns)
        if self.required_keys:
            out["required_keys"] = list(self.required_keys)
        if self.source_config_key:
            out["source_config_key"] = self.source_config_key
        if self.store_at:
            out["store_at"] = self.store_at
        return out


@dataclass(frozen=True)
class ParamSpec:
    """A typed config field, UI-aware."""

    name: str
    type: ParamType
    description: str = ""
    default: Any = None
    required: bool = True
    # For ParamType.ENUM — the closed list of legal values.
    enum: tuple[str, ...] = field(default_factory=tuple)
    # Override the default widget inferred from `type`.
    widget: Widget | None = None
    # True when this spec was synthesised from a legacy string
    # description rather than declared explicitly. Downstream
    # consumers (validator, UI) should be lenient with inferred specs
    # — type mismatches become warnings, not errors — because the
    # guess may be wrong until the node is migrated.
    inferred: bool = False

    def effective_widget(self) -> Widget:
        if self.widget is not None:
            return self.widget
        return _DEFAULT_WIDGET[self.type]

    def to_json(self) -> dict:
        out: dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "required": self.required,
            "widget": self.effective_widget().value,
        }
        if self.default is not None:
            out["default"] = self.default
        if self.enum:
            out["enum"] = list(self.enum)
        return out


_DEFAULT_WIDGET: dict[ParamType, Widget] = {
    ParamType.STRING: Widget.TEXT,
    ParamType.INTEGER: Widget.NUMBER,
    ParamType.NUMBER: Widget.NUMBER,
    ParamType.BOOLEAN: Widget.CHECKBOX,
    ParamType.ENUM: Widget.SELECT,
    ParamType.STRING_LIST: Widget.CHIPS,
    ParamType.OBJECT: Widget.JSON,
    ParamType.ARRAY: Widget.JSON,
    ParamType.INPUT_REF: Widget.INPUT_REF,
    ParamType.CODE: Widget.CODE,
}


# ---------------------------------------------------------------------------
# Legacy bridge helpers — while we migrate node handlers tier-by-tier, the
# registry needs to synthesise *something* typed from the old string dicts
# so the UI and the copilot can already benefit from the new shape.
# The synthesis is best-effort: types default to DATAFRAME / STRING unless
# the description contains a hint we can detect.
# ---------------------------------------------------------------------------
def _guess_port_type(description: str, name: str) -> PortType:
    d = description.lower()
    if "dataframe" in d or "df" in name.lower():
        return PortType.DATAFRAME
    if "string" in d or "text" in d or "summary" in name.lower():
        return PortType.TEXT
    if "integer" in d or "count" in name.lower() or "number" in d:
        return PortType.SCALAR
    if "object" in d or "dict" in d or name.endswith("s") and "section" in name:
        return PortType.OBJECT
    return PortType.OBJECT


def _guess_param_type(description: str) -> ParamType:
    d = description.lower()
    if d.startswith("boolean") or "— if true" in d or "— true " in d:
        return ParamType.BOOLEAN
    if d.startswith("integer") or "integer —" in d:
        return ParamType.INTEGER
    if d.startswith("number") or "number —" in d:
        return ParamType.NUMBER
    if d.startswith("array of strings") or "array of strings" in d:
        return ParamType.STRING_LIST
    if d.startswith("object") or d.startswith("map ") or "— map of" in d or "object —" in d:
        return ParamType.OBJECT
    if d.startswith("array of {") or "array of {" in d or "array of " in d:
        return ParamType.ARRAY
    return ParamType.STRING


def ports_from_legacy(legacy: dict[str, str] | None) -> list[PortSpec]:
    """Best-effort conversion of a legacy `{name: description}` dict
    into `PortSpec`s. Migrating nodes replace the call site with an
    explicit list; unmigrated nodes keep this shim."""
    if not legacy:
        return []
    return [
        PortSpec(name=name, type=_guess_port_type(desc, name), description=desc)
        for name, desc in legacy.items()
    ]


def params_from_legacy(legacy: dict[str, str] | None) -> list[ParamSpec]:
    """Same shim for config_schema dicts."""
    if not legacy:
        return []
    return [
        ParamSpec(
            name=name,
            type=_guess_param_type(desc),
            description=desc,
            required=False,
            inferred=True,
        )
        for name, desc in legacy.items()
    ]


__all__ = [
    "PortType",
    "ParamType",
    "Widget",
    "PortSpec",
    "ParamSpec",
    "ports_from_legacy",
    "params_from_legacy",
]
