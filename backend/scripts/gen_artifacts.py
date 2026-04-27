"""
Regenerate derived artifacts from the node registry.

Produces two files that MUST be kept in sync with `engine.registry`:

  backend/contracts/node_contracts.json
      Human-readable copilot prompt material. Checked in.

  frontend/src/nodes/generated.ts
      TS module with NodeType union, NODE_UI (color/icon/description),
      NODE_CONFIG_TAGS, and exhaustive NODE_TYPES list. Imported by the
      rest of the frontend. Checked in.

Also writes **engine/node_type_ids.py** (auto-generated DRY constants from NODE_SPECS keys).
Also writes **node_detail.md**, the human-readable NodeSpec catalogue.

Run after adding or renaming a node under engine/nodes/:

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

from engine.registry import NODE_SPECS, contracts_document, studio_manifest, ui_manifest  # noqa: E402


ROOT = _BACKEND.parent
NODE_TYPE_IDS_PATH = _BACKEND / "engine" / "node_type_ids.py"
CONTRACTS_PATH = _BACKEND / "contracts" / "node_contracts.json"
FRONTEND_GEN_PATH = ROOT / "frontend" / "src" / "nodes" / "generated.ts"
NODE_DETAIL_PATH = ROOT / "node_detail.md"


def _palette_sections_from_manifest(nodes: list[dict]) -> list[dict]:
    """
    Dedupe rail sections from each node's ui.palette metadata (flattened
    into the manifest as palette_group / palette_section_*).
    """
    by_id: dict[str, dict[str, str | int]] = {}
    for n in nodes:
        sid = n.get("palette_group")
        if not sid:
            raise ValueError(
                f"gen_artifacts: node {n['type_id']!r} missing palette_group "
                f"(set ui.palette in YAML)"
            )
        sid = str(sid)
        label = str(n.get("palette_section_label", sid))
        color = str(n.get("palette_section_color", "#6B7280"))
        order = int(n.get("palette_section_order", 0))
        row = {"id": sid, "label": label, "order": order, "color": color}
        prev = by_id.get(sid)
        if prev is None:
            by_id[sid] = row
            continue
        if prev != row:
            raise ValueError(
                f"gen_artifacts: palette section {sid!r} has conflicting "
                f"metadata across nodes (e.g. {n['type_id']!r} vs another); "
                f"ui.palette.section must match for every node in a section"
            )
    return list(by_id.values())


def write_node_type_ids() -> None:
    """
    Generate module-level constants from :data:`engine.registry.NODE_SPECS`
    so ``hard_rules``, tests, and other code never duplicate type_id strings.
    """
    lines: list[str] = [
        '"""',
        "Canonical :func:`NodeSpec.type_id` strings for engine topology and hard-rules.",
        "",
        "**AUTO-GENERATED** — run ``python backend/scripts/gen_artifacts.py``.",
        "The canonical set is :data:`engine.registry.NODE_SPECS` keys; import from here",
        "instead of string literals. Do not edit by hand.",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    for tid in sorted(NODE_SPECS.keys()):
        if not tid.isidentifier():
            raise ValueError(
                f"type_id {tid!r} must be a valid Python identifier for node_type_ids"
            )
        lines.append(f'{tid} = "{tid}"')
    names = sorted(NODE_SPECS.keys())
    lines.append("")
    lines.append("__all__ = [")
    for n in names:
        lines.append(f'    "{n}",')
    lines.append("]")
    lines.append("")

    NODE_TYPE_IDS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {NODE_TYPE_IDS_PATH.relative_to(ROOT)}")


def write_contracts() -> None:
    CONTRACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = contracts_document()
    CONTRACTS_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"  wrote {CONTRACTS_PATH.relative_to(ROOT)}")


def write_frontend_module() -> None:
    manifest = ui_manifest()
    nodes = manifest["nodes"]
    palette_sections = _palette_sections_from_manifest(nodes)

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
    lines.append("  /** Palette group id — must match PaletteSection.id */")
    lines.append("  paletteGroup: string")
    lines.append("  /** Sort key within the palette group (lower first). */")
    lines.append("  paletteOrder: number")
    lines.append("  /** Short card title; when omitted, UI title-cases type_id. */")
    lines.append("  displayName?: string")
    lines.append("}")
    lines.append("")
    lines.append("export interface PaletteSection {")
    lines.append("  id: string")
    lines.append("  label: string")
    lines.append("  order: number")
    lines.append("  color: string")
    lines.append("}")
    lines.append("")
    palette_json = json.dumps(
        [
            {
                "id": s["id"],
                "label": s["label"],
                "order": int(s["order"]),
                "color": s["color"],
            }
            for s in sorted(palette_sections, key=lambda x: int(x["order"]))
        ],
        indent=2,
    )
    lines.append(
        "export const PALETTE_SECTIONS: readonly PaletteSection[] = "
        + palette_json
        + " as const"
    )
    lines.append("")
    lines.append("export const NODE_UI: Record<NodeType, NodeUIMeta> = {")
    for n in nodes:
        pg = n.get("palette_group")
        if not pg:
            raise ValueError(
                f"gen_artifacts: node {n['type_id']!r} missing palette_group "
                f"(set ui.palette in YAML)"
            )
        tags = ", ".join([f"'{t}'" for t in n.get("config_tags", [])])
        p_order = int(n.get("palette_order", 0))
        disp = n.get("display_name")
        disp_line = f"    displayName: {json.dumps(disp)}," if disp else ""
        lines.append(f"  {n['type_id']}: {{")
        lines.append(f"    color: '{n['color']}',")
        lines.append(f"    Icon: {n['icon']},")
        lines.append(f"    description: {json.dumps(n['description'])},")
        lines.append(f"    configTags: [{tags}] as const,")
        lines.append(f"    paletteGroup: {json.dumps(str(pg))},")
        lines.append(f"    paletteOrder: {p_order},")
        if disp_line:
            lines.append(disp_line)
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
    lines.append("  required_columns?: readonly string[]")
    lines.append("  required_keys?: readonly string[]")
    lines.append("  source_config_key?: string")
    lines.append("  store_at?: string")
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


def _md_escape(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", "<br>")


def _title_from_type(type_id: str) -> str:
    return type_id.replace("_", " ").title()


def _default_md(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return "`" + _md_escape(json.dumps(value, separators=(",", ":"))) + "`"
    if value == "":
        return '`""`'
    return f"`{_md_escape(value)}`"


def _port_requirements(port: dict) -> str:
    bits: list[str] = []
    if port.get("required_columns"):
        bits.append("columns: " + ", ".join(f"`{c}`" for c in port["required_columns"]))
    if port.get("required_keys"):
        bits.append("keys: " + ", ".join(f"`{k}`" for k in port["required_keys"]))
    if port.get("source_config_key"):
        bits.append(f"source config: `{port['source_config_key']}`")
    return "; ".join(bits)


def write_node_detail() -> None:
    """Generate the human-readable node catalogue from the live NodeSpec manifest."""
    manifest = studio_manifest()
    nodes = manifest["nodes"]
    lines: list[str] = [
        "# Node Detail",
        "",
        "Generated from the live backend `NodeSpec` registry (`engine.registry.studio_manifest`).",
        "This file documents every node: what it does, inputs, outputs, static UI metadata, and config parameters.",
        "",
        "## Node Index",
        "",
        "| Node | Display | Section | Use |",
        "| --- | --- | --- | --- |",
    ]
    for n in nodes:
        display = n.get("display_name") or _title_from_type(n["type_id"])
        lines.append(
            f"| `{n['type_id']}` | {_md_escape(display)} | "
            f"`{_md_escape(n.get('palette_group'))}` | {_md_escape(n.get('description'))} |"
        )
    lines.append("")

    for n in nodes:
        display = n.get("display_name") or _title_from_type(n["type_id"])
        lines.extend([
            f"## `{n['type_id']}` — {display}",
            "",
            f"**Use:** {_md_escape(n.get('description'))}",
            "",
            "**Static metadata**",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Type | `{n['type_id']}` |",
            f"| Display name | {_md_escape(n.get('display_name') or display)} |",
            f"| UI section | `{_md_escape(n.get('palette_group'))}` |",
            f"| Palette order | `{_md_escape(n.get('palette_order'))}` |",
            f"| Color | `{_md_escape(n.get('color'))}` |",
            f"| Icon | `{_md_escape(n.get('icon'))}` |",
            f"| Config tags | {', '.join(f'`{t}`' for t in (n.get('config_tags') or []))} |",
            "",
            "**Inputs**",
            "",
        ])
        inputs = n.get("input_ports") or []
        if inputs:
            lines.extend(["| Name | Type | Required | Description | Requirements |", "| --- | --- | --- | --- | --- |"])
            for p in inputs:
                lines.append(
                    f"| `{_md_escape(p.get('name'))}` | `{_md_escape(p.get('type'))}` | "
                    f"{'no' if p.get('optional') else 'yes'} | {_md_escape(p.get('description'))} | "
                    f"{_port_requirements(p)} |"
                )
        else:
            lines.append("No declared inputs.")

        lines.extend(["", "**Outputs**", ""])
        outputs = n.get("output_ports") or []
        if outputs:
            lines.extend([
                "| Name | Type | Optional | Stored at | Description | Requirements |",
                "| --- | --- | --- | --- | --- | --- |",
            ])
            for p in outputs:
                lines.append(
                    f"| `{_md_escape(p.get('name'))}` | `{_md_escape(p.get('type'))}` | "
                    f"{'yes' if p.get('optional') else 'no'} | `{_md_escape(p.get('store_at') or '')}` | "
                    f"{_md_escape(p.get('description'))} | {_port_requirements(p)} |"
                )
        else:
            lines.append("No declared outputs.")

        lines.extend(["", "**Config parameters**", ""])
        params = n.get("params") or []
        if params:
            lines.extend([
                "| Name | Type | Required | Widget | Default | Enum/options | Description |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ])
            for p in params:
                enum = ", ".join(f"`{x}`" for x in (p.get("enum") or []))
                lines.append(
                    f"| `{_md_escape(p.get('name'))}` | `{_md_escape(p.get('type'))}` | "
                    f"{'yes' if p.get('required') else 'no'} | `{_md_escape(p.get('widget'))}` | "
                    f"{_default_md(p.get('default'))} | {enum} | {_md_escape(p.get('description'))} |"
                )
        else:
            lines.append("No config parameters.")

        constraints = n.get("contract", {}).get("constraints") or []
        if constraints:
            lines.extend(["", "**Constraints**", ""])
            lines.extend(f"- {_md_escape(c)}" for c in constraints)
        lines.append("")

    NODE_DETAIL_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {NODE_DETAIL_PATH.relative_to(ROOT)}")


def main() -> None:
    print("Regenerating node artifacts…")
    write_node_type_ids()
    write_contracts()
    write_frontend_module()
    write_node_detail()
    print("Done. Remember to `git add` outputs (incl. `engine/node_type_ids.py` and `node_detail.md`).")


if __name__ == "__main__":
    main()
