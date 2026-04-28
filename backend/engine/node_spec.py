"""
The `NodeSpec` data type and the `_spec(...)` / `_spec_from_yaml(...)` factories.

These used to live in `engine/registry.py` next to the single giant
tuple of every node declaration. That made the registry a merge-conflict
hotspot — every new node added by any developer touched the same tuple.

Now each node module declares its own `NODE_SPEC` at the bottom of its
handler file via one of two patterns:

  # Legacy (Python inline):
  NODE_SPEC = _spec("TYPE_ID", handler, "description", color=..., ...)

  # YAML-driven (preferred for new nodes):
  NODE_SPEC = _spec_from_yaml(Path(__file__).with_suffix('.yaml'), handler)

Both return an identical `NodeSpec`. The YAML form externalises all
metadata so non-Python contributors can add or modify node specs without
touching Python.

Keeping `NodeSpec` + factories in a dedicated module avoids circular
imports: node modules import from here, `registry.py` imports node
modules. Nothing else in this module reaches into either direction.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import yaml as _yaml  # PyYAML — already a project dependency (data_sources uses it)

from .context import RunContext
from .ports import (
    ParamSpec,
    ParamType,
    PortSpec,
    PortType,
    Widget,
    params_from_legacy,
    ports_from_legacy,
)


Handler = Callable[[dict, RunContext], None]


@dataclass(frozen=True)
class NodeSpec:
    """
    Canonical description of one node type.

    Read this as the node's real contract:
      * `params` tells the validator/UI which config keys exist.
      * `input_ports` tells the runner what upstream data the node accepts.
      * `output_ports` tells the runner what the handler must produce.
      * `handler` is the implementation that must honour those declarations.

    The `contract` dict below is derived from the typed fields. It exists
    because Copilot, `/contracts`, and generated docs need a JSON-friendly
    view. Do not treat `node_contracts.json` as the source of truth; edit the
    YAML NodeSpec and regenerate artifacts instead.
    """

    type_id: str                # e.g. "ALERT_TRIGGER"
    description: str            # One-liner shown in palette tooltip
    handler: Handler            # Callable the dag_runner invokes

    # Derived JSON-friendly view for Copilot/API/docs. The canonical contract
    # is the typed params/ports above, usually loaded from YAML.
    contract: dict = field(default_factory=dict)

    # UI rendering hints (kept string-only so we can serialise to JSON /
    # TS without shipping the handler object across the wire).
    ui: dict = field(default_factory=dict)

    # Typed specs — source of truth for validation, runtime checks, and UI forms.
    input_ports: tuple[PortSpec, ...] = field(default_factory=tuple)
    output_ports: tuple[PortSpec, ...] = field(default_factory=tuple)
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)

    # Semantic tags this node requires from upstream datasets, e.g.
    # ("trader", "time"). Empty = no declared semantic requirements.
    # Populated from the YAML `semantics.requires` list; used by the
    # validator and agent prompt builder.
    semantics_requires: tuple[str, ...] = field(default_factory=tuple)


def _spec(
    type_id: str,
    handler: Handler,
    description: str,
    *,
    color: str,
    icon: str,
    config_tags: tuple[str, ...] = (),
    # Legacy string-dict form (still supported during migration).
    inputs: dict | None = None,
    outputs: dict | None = None,
    config_schema: dict | None = None,
    constraints: tuple[str, ...] = (),
    extras: dict | None = None,
    # New typed form. When supplied, takes precedence over the legacy
    # dicts and also synthesises them for backwards compatibility so
    # the copilot prompt + frontend contracts keep rendering correctly.
    input_ports: tuple[PortSpec, ...] | None = None,
    output_ports: tuple[PortSpec, ...] | None = None,
    params: tuple[ParamSpec, ...] | None = None,
    # Semantic tags this node requires from upstream datasets.
    semantics_requires: tuple[str, ...] = (),
) -> NodeSpec:
    # -- Resolve typed specs --------------------------------------------------
    typed_inputs = tuple(input_ports) if input_ports is not None else tuple(ports_from_legacy(inputs))
    typed_outputs = tuple(output_ports) if output_ports is not None else tuple(ports_from_legacy(outputs))
    typed_params = tuple(params) if params is not None else tuple(params_from_legacy(config_schema))

    # -- Build the legacy contract dict ---------------------------------------
    effective_inputs: dict = inputs if inputs is not None else {p.name: p.description for p in typed_inputs}
    effective_outputs: dict = outputs if outputs is not None else {p.name: p.description for p in typed_outputs}
    effective_config_schema: dict = (
        config_schema if config_schema is not None else {p.name: p.description for p in typed_params}
    )

    contract: dict[str, Any] = {"description": description}
    if effective_inputs:
        contract["inputs"] = effective_inputs
    if effective_outputs:
        contract["outputs"] = effective_outputs
    if effective_config_schema:
        contract["config_schema"] = effective_config_schema
    if constraints:
        contract["constraints"] = list(constraints)
    if extras:
        contract.update(extras)
    contract["ports"] = {
        "inputs": [p.to_json() for p in typed_inputs],
        "outputs": [p.to_json() for p in typed_outputs],
    }
    contract["params"] = [p.to_json() for p in typed_params]
    return NodeSpec(
        type_id=type_id,
        description=description,
        handler=handler,
        contract=contract,
        ui={"color": color, "icon": icon, "config_tags": list(config_tags)},
        input_ports=typed_inputs,
        output_ports=typed_outputs,
        params=typed_params,
        semantics_requires=tuple(semantics_requires),
    )


# ---------------------------------------------------------------------------
# YAML type alias table — maps common aliases to canonical ParamType values
# so YAML authors can write "float", "int", "bool" naturally.
# ---------------------------------------------------------------------------
_PARAM_TYPE_ALIASES: dict[str, str] = {
    "float":  "number",
    "int":    "integer",
    "bool":   "boolean",
    "str":    "string",
    "list":   "array",
    "dict":   "object",
}


def _spec_from_yaml(yaml_path: Path | str, handler: Handler) -> NodeSpec:
    """
    Load a node spec from a sibling YAML file and construct a NodeSpec
    identical to what ``_spec()`` would produce.

    The YAML is the single source of truth for all node metadata (type,
    description, ports, params, constraints, semantics). The handler
    function is the only thing YAML cannot encode — it is passed
    explicitly so the two stay paired by naming convention.

    Downstream consumers (registry, validator, gen_artifacts, copilot)
    receive an ordinary ``NodeSpec`` — they are unaware of whether it
    was produced by ``_spec()`` or ``_spec_from_yaml()``.
    """
    with open(yaml_path) as f:
        data = _yaml.safe_load(f)

    def _load_port(p: dict) -> PortSpec:
        rc = p.get("required_columns") or []
        rk = p.get("required_keys") or []
        sk = p.get("source_config_key")
        store_at = p.get("store_at")
        return PortSpec(
            name=p["name"],
            type=PortType(p["type"].lower()),
            description=p.get("description", ""),
            optional=bool(p.get("optional", False)),
            required_columns=tuple(str(c) for c in rc),
            required_keys=tuple(str(k) for k in rk),
            source_config_key=str(sk) if sk else None,
            store_at=str(store_at) if store_at else None,
        )

    def _load_param(p: dict) -> ParamSpec:
        raw = p["type"].lower()
        raw = _PARAM_TYPE_ALIASES.get(raw, raw)
        ptype = ParamType(raw)
        # Widget can sit directly under "widget" or nested as "ui.control"
        raw_widget = p.get("widget") or (p.get("ui") or {}).get("control")
        widget = Widget(raw_widget.lower()) if raw_widget else None
        return ParamSpec(
            name=p["name"],
            type=ptype,
            description=p.get("description", ""),
            default=p.get("default"),
            required=bool(p.get("required", True)),
            enum=tuple(str(v) for v in (p.get("enum") or [])),
            widget=widget,
        )

    ui = data.get("ui") or {}
    sem = data.get("semantics") or {}

    type_id = data.get("type_id") or data.get("id")
    if not type_id:
        raise ValueError(
            f"Node YAML {yaml_path!s} must set 'type_id' (or alias 'id')"
        )

    spec = _spec(
        type_id,
        handler,
        data["description"],
        color=ui.get("color", "#6B7280"),
        icon=ui.get("icon", "Box"),
        config_tags=tuple(ui.get("config_tags") or []),
        input_ports=tuple(_load_port(p) for p in (data.get("input_ports") or [])),
        output_ports=tuple(_load_port(p) for p in (data.get("output_ports") or [])),
        params=tuple(_load_param(p) for p in (data.get("params") or [])),
        constraints=tuple(data.get("constraints") or []),
        extras=data.get("extras"),
        semantics_requires=tuple(sem.get("requires") or []),
    )
    palette_meta = _palette_meta_from_ui(ui, type_id=str(type_id))
    if palette_meta:
        spec = replace(spec, ui={**spec.ui, **palette_meta})
    return spec


def _palette_meta_from_ui(ui: dict, *, type_id: str) -> dict[str, str | int]:
    """Studio palette: all metadata under ui.palette (NodeSpec-only).

    ui.palette.section — {id, label, color, order} shared by every node in
    that rail section (must match across nodes; gen_artifacts validates).

    ui.palette.node_order — sort within the section.

    ui.display_name — optional short card title.
    """
    out: dict[str, str | int] = {}
    pal = ui.get("palette")
    if isinstance(pal, dict):
        sec = pal.get("section") or {}
        sid = sec.get("id")
        if not sid:
            raise ValueError(
                f"Node {type_id}: ui.palette.section.id is required when ui.palette is set"
            )
        out["palette_group"] = str(sid)
        out["palette_section_label"] = str(sec.get("label", sid))
        out["palette_section_color"] = str(sec.get("color", "#6B7280"))
        out["palette_section_order"] = int(sec.get("order", 0))
        if pal.get("node_order") is None:
            raise ValueError(f"Node {type_id}: ui.palette.node_order is required")
        out["palette_order"] = int(pal["node_order"])
    else:
        raise ValueError(
            f"Node {type_id}: ui.palette is required "
            f"(section: id/label/color/order, node_order)"
        )
    if ui.get("display_name"):
        out["display_name"] = str(ui["display_name"])
    return out


__all__ = ["NodeSpec", "Handler", "_spec", "_spec_from_yaml"]
