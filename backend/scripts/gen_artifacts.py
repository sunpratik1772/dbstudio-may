"""
Regenerate derived artifacts from the node registry.

Produces two files that MUST be kept in sync with `engine.registry`:

  backend/contracts/node_contracts.json
      Human-readable copilot prompt material. Checked in.

  frontend/src/nodes/generated.ts
      TS module with NodeType union, NODE_UI (color/icon/description),
      NODE_CONFIG_TAGS, and exhaustive NODE_TYPES list. Imported by the
      rest of the frontend. Checked in.

Run after editing `engine/registry.py`:

    python backend/scripts/gen_artifacts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `import engine` work regardless of where this script is invoked from.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from engine.registry import NODE_SPECS, contracts_document, ui_manifest  # noqa: E402


ROOT = _BACKEND.parent
CONTRACTS_PATH = _BACKEND / "contracts" / "node_contracts.json"
FRONTEND_GEN_PATH = ROOT / "frontend" / "src" / "nodes" / "generated.ts"


def write_contracts() -> None:
    CONTRACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = contracts_document()
    CONTRACTS_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"  wrote {CONTRACTS_PATH.relative_to(ROOT)}")


def write_frontend_module() -> None:
    manifest = ui_manifest()
    nodes = manifest["nodes"]

    # Pair each UI entry with its contract so the frontend can render
    # an accurate Config inspector (inputs / outputs / config_schema)
    # without a network round-trip or a second source of truth.
    contracts_by_id = {spec.type_id: spec.contract for spec in NODE_SPECS.values()}

    # Collect all icon names so we can import them once at the top.
    icon_ids = sorted({n["icon"] for n in nodes})

    lines: list[str] = []
    lines.append("/**")
    lines.append(" * AUTO-GENERATED — do not edit by hand.")
    lines.append(" * Run `python backend/scripts/gen_artifacts.py` to regenerate.")
    lines.append(" * Source: backend/engine/registry.py")
    lines.append(" */")
    lines.append("import type { LucideIcon } from 'lucide-react'")
    lines.append("import {")
    for icon in icon_ids:
        lines.append(f"  {icon},")
    lines.append("} from 'lucide-react'")
    lines.append("")
    lines.append("export type NodeType =")
    for i, n in enumerate(nodes):
        sep = "" if i == len(nodes) - 1 else ""
        lines.append(f"  | '{n['type_id']}'")
    lines.append("")
    lines.append("export interface NodeUIMeta {")
    lines.append("  color: string")
    lines.append("  Icon: LucideIcon")
    lines.append("  description: string")
    lines.append("  /** Config keys whose values are rendered as chips on the node card. */")
    lines.append("  configTags: readonly string[]")
    lines.append("}")
    lines.append("")
    lines.append("export const NODE_UI: Record<NodeType, NodeUIMeta> = {")
    for n in nodes:
        tags = ", ".join([f"'{t}'" for t in n.get("config_tags", [])])
        lines.append(f"  {n['type_id']}: {{")
        lines.append(f"    color: '{n['color']}',")
        lines.append(f"    Icon: {n['icon']},")
        lines.append(f"    description: {json.dumps(n['description'])},")
        lines.append(f"    configTags: [{tags}] as const,")
        lines.append("  },")
    lines.append("}")
    lines.append("")
    lines.append("export const NODE_TYPES: readonly NodeType[] = [")
    for n in nodes:
        lines.append(f"  '{n['type_id']}',")
    lines.append("] as const")
    lines.append("")
    lines.append("/** Schema + constraints for a node type, surfaced in the Config inspector. */")
    lines.append("export interface NodeContract {")
    lines.append("  description: string")
    lines.append("  inputs: Record<string, string>")
    lines.append("  outputs: Record<string, string>")
    lines.append("  configSchema: Record<string, string>")
    lines.append("  constraints: readonly string[]")
    lines.append("}")
    lines.append("")
    lines.append("export const NODE_CONTRACTS: Record<NodeType, NodeContract> = {")
    for n in nodes:
        contract = contracts_by_id.get(n["type_id"], {})
        inputs = contract.get("inputs") or {}
        outputs = contract.get("outputs") or {}
        config_schema = contract.get("config_schema") or {}
        constraints = contract.get("constraints") or []
        lines.append(f"  {n['type_id']}: {{")
        lines.append(f"    description: {json.dumps(n['description'])},")
        lines.append(f"    inputs: {json.dumps(inputs, indent=6).replace(chr(10), chr(10) + '    ')},")
        lines.append(f"    outputs: {json.dumps(outputs, indent=6).replace(chr(10), chr(10) + '    ')},")
        lines.append(f"    configSchema: {json.dumps(config_schema, indent=6).replace(chr(10), chr(10) + '    ')},")
        lines.append(f"    constraints: {json.dumps(list(constraints))} as const,")
        lines.append("  },")
    lines.append("}")
    lines.append("")

    # -- Typed PortSpec / ParamSpec ------------------------------------
    # Shipped alongside the legacy contract shape so the config
    # inspector can render widgets from structured metadata instead of
    # string-sniffing descriptions.
    lines.append("/** Typed port — what flows along an edge. */")
    lines.append("export interface NodePortSpec {")
    lines.append("  name: string")
    lines.append("  type: 'dataframe' | 'scalar' | 'object' | 'text'")
    lines.append("  description: string")
    lines.append("  optional: boolean")
    lines.append("}")
    lines.append("")
    lines.append("/** Typed config param with UI hint. */")
    lines.append("export interface NodeParamSpec {")
    lines.append(
        "  name: string\n"
        "  type:\n"
        "    | 'string'\n"
        "    | 'integer'\n"
        "    | 'number'\n"
        "    | 'boolean'\n"
        "    | 'enum'\n"
        "    | 'string_list'\n"
        "    | 'object'\n"
        "    | 'array'\n"
        "    | 'input_ref'\n"
        "    | 'code'"
    )
    lines.append("  description: string")
    lines.append("  required: boolean")
    lines.append(
        "  widget:\n"
        "    | 'text'\n"
        "    | 'textarea'\n"
        "    | 'number'\n"
        "    | 'checkbox'\n"
        "    | 'select'\n"
        "    | 'chips'\n"
        "    | 'json'\n"
        "    | 'input_ref'\n"
        "    | 'code'"
    )
    lines.append("  default?: unknown")
    lines.append("  enum?: readonly string[]")
    lines.append("}")
    lines.append("")
    lines.append("export interface NodeTypedSpec {")
    lines.append("  inputPorts: readonly NodePortSpec[]")
    lines.append("  outputPorts: readonly NodePortSpec[]")
    lines.append("  params: readonly NodeParamSpec[]")
    lines.append("}")
    lines.append("")
    lines.append("export const NODE_TYPED: Record<NodeType, NodeTypedSpec> = {")
    for n in nodes:
        input_ports = n.get("input_ports", []) or []
        output_ports = n.get("output_ports", []) or []
        params = n.get("params", []) or []
        lines.append(f"  {n['type_id']}: {{")
        lines.append(f"    inputPorts: {json.dumps(input_ports)} as const,")
        lines.append(f"    outputPorts: {json.dumps(output_ports)} as const,")
        lines.append(f"    params: {json.dumps(params)} as const,")
        lines.append("  },")
    lines.append("}")
    lines.append("")

    FRONTEND_GEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_GEN_PATH.write_text("\n".join(lines))
    print(f"  wrote {FRONTEND_GEN_PATH.relative_to(ROOT)}")


def main() -> None:
    print("Regenerating node artifacts…")
    write_contracts()
    write_frontend_module()
    print("Done. Remember to `git add` both outputs.")


if __name__ == "__main__":
    main()
