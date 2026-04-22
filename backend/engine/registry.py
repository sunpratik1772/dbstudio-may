"""
Central node registry — built by *auto-discovering* `NODE_SPEC` from
every module under `backend/engine/nodes/`.

Design goal: adding a new node must be a **single-file** change. Drop
a new file in `engine/nodes/`, put `handle_<type>(node, ctx)` and a
module-level `NODE_SPEC = _spec(...)` in it, and the registry picks it
up on the next import. No tuple to edit, no import line to add here,
no merge conflict with other in-flight node work.

At import time we walk the `engine.nodes` package with
`pkgutil.iter_modules`, import each submodule, and collect every
module-level `NODE_SPEC`. Modules without a `NODE_SPEC` are skipped
silently (so internal helper modules can coexist).

Everything downstream — `engine.dag_runner`, `engine.validator`,
`engine.jobs`, `app.routers.copilot` — consumes the lookup dicts
exposed here. None of them know about individual node modules.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import asdict
from typing import Iterable

from . import nodes as _nodes_pkg
from .node_spec import Handler, NodeSpec, _spec
from .ports import ParamSpec, ParamType, PortSpec, PortType, Widget


# -----------------------------------------------------------------------------
# Auto-discovery
# -----------------------------------------------------------------------------
def _discover_specs() -> tuple[NodeSpec, ...]:
    """
    Walk the `engine.nodes` package and collect every top-level
    `NODE_SPEC` attribute. Results are sorted by `type_id` so the
    palette order is stable regardless of filesystem iteration order.
    """
    found: dict[str, NodeSpec] = {}
    for module_info in pkgutil.iter_modules(_nodes_pkg.__path__):
        if module_info.name.startswith("_"):
            continue  # skip dunder / private helper modules
        module = importlib.import_module(f"{_nodes_pkg.__name__}.{module_info.name}")
        spec = getattr(module, "NODE_SPEC", None)
        if isinstance(spec, NodeSpec):
            if spec.type_id in found:
                raise RuntimeError(
                    f"Duplicate NODE_SPEC type_id '{spec.type_id}' — "
                    f"defined in both engine/nodes/{module_info.name}.py and "
                    f"another node module."
                )
            found[spec.type_id] = spec
    return tuple(sorted(found.values(), key=lambda s: s.type_id))


_SPECS: tuple[NodeSpec, ...] = _discover_specs()


# -----------------------------------------------------------------------------
# Public lookups
# -----------------------------------------------------------------------------
NODE_SPECS: dict[str, NodeSpec] = {s.type_id: s for s in _SPECS}

NODE_HANDLERS: dict[str, Handler] = {s.type_id: s.handler for s in _SPECS}
"""Drop-in replacement for the old dag_runner map."""


def all_specs() -> Iterable[NodeSpec]:
    """Iterate specs in palette order (sorted by type_id)."""
    return _SPECS


def get_spec(type_id: str) -> NodeSpec:
    try:
        return NODE_SPECS[type_id]
    except KeyError:
        raise ValueError(f"Unknown node type '{type_id}'") from None


def contracts_document(version: str = "1.0") -> dict:
    """
    Serialisable contracts document — served live by the
    `/contracts` endpoint and consumed by the frontend artifact
    generator. Structurally identical to the legacy static
    `node_contracts.json` so existing consumers do not need to
    change.
    """
    return {
        "version": version,
        "description": (
            "I/O contracts for all dbSherpa node types. All datasets are pandas "
            "DataFrames passed by name through the shared RunContext."
        ),
        "nodes": {s.type_id: s.contract for s in _SPECS},
    }


def ui_manifest() -> dict:
    """
    UI-facing manifest consumed by the frontend generator. Keeps the
    frontend free from any Python/backend coupling.
    """
    return {
        "version": 2,
        "nodes": [
            {
                "type_id": s.type_id,
                "description": s.description,
                **s.ui,
                "input_ports": [p.to_json() for p in s.input_ports],
                "output_ports": [p.to_json() for p in s.output_ports],
                "params": [p.to_json() for p in s.params],
            }
            for s in _SPECS
        ],
    }


# Re-export the primitives so node modules that want to stay within
# the `engine.registry` namespace still can. The canonical import path
# for new code is `engine.node_spec` / `engine.ports`.
__all__ = [
    "NodeSpec",
    "Handler",
    "_spec",
    "ParamSpec",
    "ParamType",
    "PortSpec",
    "PortType",
    "Widget",
    "NODE_SPECS",
    "NODE_HANDLERS",
    "all_specs",
    "get_spec",
    "contracts_document",
    "ui_manifest",
    "asdict",  # re-export for scripts that dump specs
]
