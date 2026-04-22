"""
The `NodeSpec` data type and the `_spec(...)` factory.

These used to live in `engine/registry.py` next to the single giant
tuple of every node declaration. That made the registry a merge-conflict
hotspot — every new node added by any developer touched the same tuple.

Now each node module declares its own `NODE_SPEC = _spec(...)` at the
bottom of its handler file, and `registry.py` is a tiny auto-discovery
module that collects them. Two developers adding two nodes touch two
different files.

Keeping `NodeSpec` + `_spec` in a dedicated module (rather than
`engine/ports.py` or `engine/registry.py`) avoids circular imports:
node modules import from here, and `registry.py` imports the node
modules. Nothing else in this module reaches into either direction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .context import RunContext
from .ports import (
    ParamSpec,
    PortSpec,
    params_from_legacy,
    ports_from_legacy,
)


Handler = Callable[[dict, RunContext], None]


@dataclass(frozen=True)
class NodeSpec:
    """
    Full description of a node type. The runtime side needs `handler`;
    the copilot needs `contract`; the frontend needs `ui`. One record,
    one place to change.

    Typed fields (`input_ports`, `output_ports`, `params`) are filled in
    either explicitly (for migrated nodes) or synthesised from the
    legacy `contract["inputs"]/["outputs"]/["config_schema"]` string
    dicts for nodes still waiting to be migrated.
    """

    type_id: str                # e.g. "ALERT_TRIGGER"
    description: str            # One-liner shown in palette tooltip
    handler: Handler            # Callable the dag_runner invokes

    # Copilot contract (schema/constraints — mirrors node_contracts.json).
    contract: dict = field(default_factory=dict)

    # UI rendering hints (kept string-only so we can serialise to JSON /
    # TS without shipping the handler object across the wire).
    ui: dict = field(default_factory=dict)

    # Typed specs — the new source of truth. Legacy string dicts are
    # synthesised from these on demand for backward-compatible consumers.
    input_ports: tuple[PortSpec, ...] = field(default_factory=tuple)
    output_ports: tuple[PortSpec, ...] = field(default_factory=tuple)
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)


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
    )


__all__ = ["NodeSpec", "Handler", "_spec"]
