"""
Deterministic workflow validator.

Until now the only validation a workflow got was an LLM checklist in the
copilot prompt plus a runtime "unknown node type" check in the dag
runner. That's not enough:

  * A workflow could pass the LLM critic and still blow up halfway
    through a real run (e.g. SIGNAL_CALCULATOR with no input_name).
  * The copilot had no structured feedback to act on — it re-parsed its
    own text and guessed.

This module walks a DAG against the registry and typed ParamSpec /
PortSpec contracts and returns a structured list of issues. It is the
single source of truth for "is this workflow safe to run?" — called
pre-run inside `/run` and `/run/stream`, exposed publicly at
`POST /validate`, and consumable by the copilot self-corrector.

It is intentionally pure (no FastAPI, no HTTP, no pandas). Callers
choose how to surface the results.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .dag_runner import _edge_endpoints, topological_sort
from .hard_rules import run_hard_rules
from .ports import ParamType
from .prompt_context import validate_prompt_template
from .registry import NODE_SPECS, NodeSpec
from .refs import AGG_FUNCS, REF_RE
from .schema_version import SchemaVersionError, migrate_to_current
from .signal_contract import get_signal_output_columns
from .validation_codes import ValidationErrorCode

# `code` is a stable machine-readable identifier. The frontend / copilot
# can switch on it; humans read `message`. See `engine/validation_codes.py`
# for the canonical inventory — `ValidationErrorCode` is a str-based enum,
# so `issue.code == _VC.UNKNOWN_TYPE` and `issue.code is ValidationErrorCode.UNKNOWN_TYPE`
# both succeed. Severities are:
#   error   — blocks execution. /run returns 422, UI shows red.
#   warning — non-blocking. UI shows amber; the copilot may auto-fix.

# Backwards-compat alias for any caller still importing ErrorCode.
ErrorCode = str
# Shorter binding so call sites stay readable — `VC.UNKNOWN_TYPE` is
# common enough that `ValidationErrorCode.UNKNOWN_TYPE` would add noise.
_VC = ValidationErrorCode


@dataclass(frozen=True)
class ValidationIssue:
    code: ErrorCode
    message: str
    severity: str = "error"        # "error" | "warning"
    node_id: str | None = None
    field: str | None = None       # e.g. "config.input_name"

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_json(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [i.to_json() for i in self.errors],
            "warnings": [i.to_json() for i in self.warnings],
            "summary": f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)",
        }

    def add(
        self,
        code: ErrorCode,
        message: str,
        *,
        severity: str = "error",
        node_id: str | None = None,
        field: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code, message=message, severity=severity, node_id=node_id, field=field
            )
        )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------
def validate_dag(dag: dict) -> ValidationResult:
    """Validate a workflow without executing it.

    Read this as a pipeline:
      1. Migrate/reject schema versions.
      2. Check top-level DAG shape, registered node types, edges, and cycles.
      3. Enforce topology conventions (entry/exit/orphans).
      4. Validate each node config against typed NodeSpec params.
      5. Validate wiring and field bindings using declared outputs.
      6. Run registered hard rules.
      7. Recursively validate MAP sub-workflows and re-scope their issues
         under the parent MAP node for UI highlighting.

    Callers use `result.valid` to gate execution or serialize
    `result.issues` for the UI/copilot.
    """
    result = ValidationResult()

    # --- Schema version gate -------------------------------------------------
    # Reject workflows authored against an incompatible schema *before*
    # any structural checks — otherwise we risk reporting misleading
    # errors against a DAG that was never meant for this engine build.
    try:
        dag = migrate_to_current(dag) if isinstance(dag, dict) else dag
    except SchemaVersionError as exc:
        result.add(exc.code, exc.message, field="schema_version")
        return result

    # --- Structural: the DAG must be well-formed after migration. -----------
    nodes = _validate_top_level_shape(dag, result)
    if not nodes:
        return result

    nodes_by_id: dict[str, dict] = {n["id"]: n for n in nodes if isinstance(n, dict) and "id" in n}
    edges = dag.get("edges", []) or []

    _validate_nodes_registered(nodes_by_id, result)
    _validate_edges(edges, nodes_by_id, result)

    # Abort further checks if the structural ones failed — later passes
    # assume a well-formed DAG.
    if not result.valid:
        return result

    _validate_acyclic(nodes_by_id, edges, result)
    if not result.valid:
        return result

    # --- Topology: entry / exit nodes, orphans. ---
    _validate_topology(nodes_by_id, edges, result)

    # --- Per-node configs against the typed ParamSpec contracts. ---
    for node_id, node in nodes_by_id.items():
        _validate_node_config(node, result)

    # --- Wiring: input_name params must reference upstream outputs. ---
    _validate_wiring(nodes_by_id, edges, result)

    # --- Column names: field_bindings must reference real columns. ---
    _validate_field_bindings(nodes_by_id, result)
    _validate_prompt_refs(nodes_by_id, result)

    # --- Node-specific hard rules we can enforce programmatically. ---
    # Rules register themselves via `@register_hard_rule` in
    # `engine/hard_rules.py`. Adding a new rule is a decorator call,
    # not an edit to this file.
    run_hard_rules(nodes_by_id, dag, result)

    # --- MAP sub-workflow: validate nested DAGs with the same rules,
    # minus the top-level topology check (a sub-workflow has no
    # ALERT_TRIGGER / REPORT_OUTPUT). Issues are re-scoped under the
    # parent MAP node's id so the UI can locate them.
    _validate_map_sub_workflows(nodes_by_id, result)

    return result


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------
def _validate_top_level_shape(dag: dict, result: ValidationResult) -> list[dict]:
    if not isinstance(dag, dict):
        result.add(_VC.BAD_SHAPE, "Workflow must be a JSON object with nodes and edges.")
        return []
    nodes = dag.get("nodes")
    if not isinstance(nodes, list):
        result.add(_VC.MISSING_NODES, "Workflow is missing a 'nodes' array.")
        return []
    if not nodes:
        result.add(_VC.EMPTY_WORKFLOW, "Workflow has no nodes.")
        return []
    edges = dag.get("edges")
    if edges is not None and not isinstance(edges, list):
        result.add(_VC.BAD_EDGES, "'edges' must be an array of {from, to} objects.")
    return nodes


def _validate_nodes_registered(nodes_by_id: dict[str, dict], result: ValidationResult) -> None:
    for nid, n in nodes_by_id.items():
        node_type = n.get("type")
        if not node_type:
            result.add(_VC.MISSING_TYPE, f"Node '{nid}' has no 'type' field.", node_id=nid)
            continue
        if node_type not in NODE_SPECS:
            known = ", ".join(sorted(NODE_SPECS.keys()))
            result.add(
                _VC.UNKNOWN_TYPE,
                f"Node '{nid}' has unknown type '{node_type}'. Known types: {known}",
                node_id=nid,
                field="type",
            )
        if "label" not in n or not n.get("label"):
            result.add(
                _VC.MISSING_LABEL,
                f"Node '{nid}' is missing a 'label'.",
                severity="warning",
                node_id=nid,
                field="label",
            )


def _validate_edges(
    edges: list, nodes_by_id: dict[str, dict], result: ValidationResult
) -> None:
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            result.add(_VC.BAD_EDGE, f"Edge at index {i} is not an object.")
            continue
        try:
            src, dst = _edge_endpoints(edge)
        except ValueError as exc:
            result.add(_VC.BAD_EDGE, str(exc))
            continue
        if src not in nodes_by_id:
            result.add(
                _VC.EDGE_DANGLING,
                f"Edge references missing source node '{src}'.",
                field=f"edges[{i}].from",
            )
        if dst not in nodes_by_id:
            result.add(
                _VC.EDGE_DANGLING,
                f"Edge references missing target node '{dst}'.",
                field=f"edges[{i}].to",
            )


def _validate_acyclic(
    nodes_by_id: dict[str, dict], edges: list, result: ValidationResult
) -> None:
    try:
        topological_sort(list(nodes_by_id.values()), edges)
    except ValueError as exc:
        result.add(_VC.CYCLE, str(exc))


# ---------------------------------------------------------------------------
# Topology — entry, exit, orphans
# ---------------------------------------------------------------------------
def _validate_topology(
    nodes_by_id: dict[str, dict], edges: list, result: ValidationResult
) -> None:
    incoming: dict[str, int] = {nid: 0 for nid in nodes_by_id}
    outgoing: dict[str, int] = {nid: 0 for nid in nodes_by_id}
    for e in edges:
        try:
            src, dst = _edge_endpoints(e)
        except ValueError:
            continue
        if src in outgoing:
            outgoing[src] += 1
        if dst in incoming:
            incoming[dst] += 1

    # Exactly one ALERT_TRIGGER, first in the graph, id 'n01'.
    alert_triggers = [nid for nid, n in nodes_by_id.items() if n.get("type") == "ALERT_TRIGGER"]
    if not alert_triggers:
        result.add(_VC.NO_ENTRY, "Workflow must contain an ALERT_TRIGGER node.")
    elif len(alert_triggers) > 1:
        result.add(
            _VC.MULTIPLE_ENTRIES,
            f"Workflow has {len(alert_triggers)} ALERT_TRIGGER nodes; expected exactly one.",
        )
    else:
        entry_id = alert_triggers[0]
        if entry_id != "n01":
            result.add(
                _VC.WRONG_ENTRY_ID,
                f"ALERT_TRIGGER must have id 'n01' (found '{entry_id}').",
                node_id=entry_id,
                field="id",
            )
        if incoming.get(entry_id, 0) > 0:
            result.add(
                _VC.ENTRY_HAS_INPUT,
                "ALERT_TRIGGER must be the first node; it has incoming edges.",
                node_id=entry_id,
            )

    # At least one REPORT_OUTPUT at the exit.
    report_nodes = [nid for nid, n in nodes_by_id.items() if n.get("type") == "REPORT_OUTPUT"]
    if not report_nodes:
        result.add(
            _VC.NO_EXIT,
            "Workflow must end with a REPORT_OUTPUT node.",
            severity="warning",
        )
    else:
        for nid in report_nodes:
            if outgoing.get(nid, 0) > 0:
                result.add(
                    _VC.EXIT_HAS_OUTPUT,
                    "REPORT_OUTPUT must be a terminal node; it has outgoing edges.",
                    node_id=nid,
                )

    # Orphan detection — every node except ALERT_TRIGGER should have an
    # upstream edge, and every non-terminal node should have a downstream
    # edge. These are warnings rather than errors because transient
    # orphans are legal while a user is mid-build.
    for nid, node in nodes_by_id.items():
        node_type = node.get("type")
        if node_type == "ALERT_TRIGGER":
            continue
        if incoming.get(nid, 0) == 0:
            result.add(
                _VC.ORPHAN_NODE,
                f"Node '{nid}' ({node_type}) has no incoming edge.",
                severity="warning",
                node_id=nid,
            )


# ---------------------------------------------------------------------------
# Per-node config validation against ParamSpec
# ---------------------------------------------------------------------------
def _validate_node_config(node: dict, result: ValidationResult) -> None:
    node_id = node.get("id", "<unknown>")
    node_type = node.get("type")
    spec: NodeSpec | None = NODE_SPECS.get(node_type) if node_type else None
    if not spec:
        return  # already flagged in _validate_nodes_registered

    config = node.get("config") or {}
    if not isinstance(config, dict):
        result.add(
            _VC.BAD_CONFIG,
            f"Node '{node_id}' has non-object 'config'.",
            node_id=node_id,
            field="config",
        )
        return

    for param in spec.params:
        value = config.get(param.name)
        missing = value is None or (isinstance(value, str) and value == "")
        if missing:
            if param.required:
                result.add(
                    _VC.MISSING_REQUIRED_PARAM,
                    f"Node '{node_id}' is missing required config '{param.name}'.",
                    node_id=node_id,
                    field=f"config.{param.name}",
                )
            # Optional + missing → skip further checks
            continue

        # Inferred specs (synthesised from legacy string descriptions)
        # might have guessed the wrong type; report mismatches as
        # warnings until the node is migrated to declare a typed spec.
        type_severity = "warning" if param.inferred else "error"
        type_code = _VC.BAD_PARAM_TYPE

        expected = param.type
        if expected == ParamType.ENUM and param.enum:
            if value not in param.enum:
                result.add(
                    _VC.BAD_ENUM_VALUE,
                    f"Node '{node_id}' config '{param.name}'={value!r} not in {list(param.enum)}.",
                    severity=type_severity,
                    node_id=node_id,
                    field=f"config.{param.name}",
                )
        elif expected == ParamType.BOOLEAN and not isinstance(value, bool):
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be boolean, got {_type(value)}.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        elif expected == ParamType.INTEGER and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            # bool is a subclass of int in Python — exclude it explicitly.
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be integer, got {_type(value)}.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        elif expected == ParamType.NUMBER and (
            not isinstance(value, (int, float)) or isinstance(value, bool)
        ):
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be number, got {_type(value)}.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        elif expected == ParamType.STRING and not isinstance(value, str):
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be string, got {_type(value)}.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        elif expected == ParamType.STRING_LIST:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                result.add(
                    type_code,
                    f"Node '{node_id}' config '{param.name}' should be array of strings.",
                    severity=type_severity,
                    node_id=node_id,
                    field=f"config.{param.name}",
                )
        elif expected == ParamType.OBJECT and not isinstance(value, dict):
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be an object.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        elif expected == ParamType.ARRAY and not isinstance(value, list):
            result.add(
                type_code,
                f"Node '{node_id}' config '{param.name}' should be an array.",
                severity=type_severity,
                node_id=node_id,
                field=f"config.{param.name}",
            )
        if param.name in {"prompt_template", "llm_prompt_template", "system_prompt"} and isinstance(value, str):
            issue = validate_prompt_template(value)
            if issue:
                result.add(
                    _VC.BAD_PROMPT_TEMPLATE,
                    f"Node '{node_id}' config '{param.name}' has malformed template braces: {issue}. "
                    "Escape literal JSON braces as '{{' and '}}' or remove raw brace examples.",
                    node_id=node_id,
                    field=f"config.{param.name}",
                )


# ---------------------------------------------------------------------------
# Wiring — input_name params must point at an upstream output
# ---------------------------------------------------------------------------
def _validate_wiring(
    nodes_by_id: dict[str, dict], edges: list, result: ValidationResult
) -> None:
    """
    Walk every (node, upstream_path) pair. For nodes whose config
    includes an `input_name`, verify that *some* upstream node produces
    a dataset under that name (via its `output_name` config).

    This enforces the "input of one === output of the next" principle
    from the blueprint without requiring port-based handlers yet.
    """
    # Build adjacency: node_id → list of predecessor node_ids (transitively).
    preds: dict[str, set[str]] = {nid: set() for nid in nodes_by_id}
    immediate: dict[str, list[str]] = {nid: [] for nid in nodes_by_id}
    for e in edges:
        try:
            src, dst = _edge_endpoints(e)
        except ValueError:
            continue
        if src in immediate and dst in preds:
            immediate[dst].append(src)

    def expand(nid: str) -> set[str]:
        # BFS of ancestors
        stack = list(immediate.get(nid, []))
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(immediate.get(cur, []))
        return seen

    for nid in nodes_by_id:
        preds[nid] = expand(nid)

    for nid, node in nodes_by_id.items():
        config = node.get("config") or {}
        if not isinstance(config, dict):
            continue
        input_name = config.get("input_name")
        if not input_name:
            continue

        # Collect all output_names produced by ancestors. Some collectors
        # publish auxiliary datasets too (e.g. COMMS_COLLECTOR with
        # emit_hits_only=true also publishes f"{output_name}_hits").
        produced: list[tuple[str, str]] = []
        for pid in preds[nid]:
            ptype = nodes_by_id[pid].get("type")
            pcfg = nodes_by_id[pid].get("config") or {}
            if not isinstance(pcfg, dict):
                continue
            base = pcfg.get("output_name")
            if base:
                produced.append((pid, base))
            if ptype == "COMMS_COLLECTOR" and base and pcfg.get("emit_hits_only"):
                produced.append((pid, f"{base}_hits"))

        produced_names = {name for _, name in produced}
        # Some upstream nodes pass through a dataset under the same
        # name — so also accept cases where the named dataset matches
        # *any* ancestor's output.
        if input_name not in produced_names:
            hint = (
                f" Upstream produces: {sorted(produced_names)}."
                if produced_names
                else " No upstream node produces any named dataset."
            )
            result.add(
                _VC.UNWIRED_INPUT,
                f"Node '{nid}' expects input_name='{input_name}' but no upstream node"
                f" writes that dataset.{hint}",
                node_id=nid,
                field="config.input_name",
            )


# ---------------------------------------------------------------------------
# Field-binding column validation
# ---------------------------------------------------------------------------
# Maps the node type that *produces* a dataset to its DataSource ID in the
# registry.  Only collector nodes are listed because transformers (NORMALISE_
# ENRICH, SIGNAL_CALCULATOR) pass the dataset through under the same name —
# the base schema is still the collector's schema plus appended columns.
_COLLECTOR_SOURCE: dict[str, str] = {
    "EXECUTION_DATA_COLLECTOR": "trades",
    "TRADE_DATA_COLLECTOR": "trades",
    "MARKET_DATA_COLLECTOR": "market",
    "COMMS_COLLECTOR": "comms",
    "ORACLE_DATA_COLLECTOR": "oracle",
}


def _primary_output_name(node: dict) -> str | None:
    cfg = node.get("config") or {}
    if node.get("type") == "FEATURE_ENGINE":
        inn = cfg.get("input_name")
        if not inn:
            return None
        out = cfg.get("output_name")
        return str(out) if out else str(inn)
    out = cfg.get("output_name")
    return str(out) if out else None


def _build_output_to_node(nodes_by_id: dict[str, dict]) -> dict[str, dict]:
    m: dict[str, dict] = {}
    for n in nodes_by_id.values():
        pname = _primary_output_name(n)
        if pname:
            m[pname] = n
    return m


def _feature_engine_added_columns(cfg: dict) -> set[str]:
    out: set[str] = set()
    for op in cfg.get("ops") or []:
        if isinstance(op, dict) and op.get("out_col"):
            out.add(str(op["out_col"]))
    return out


def _trace_registry_ds(
    dataset_name: str,
    output_to_node: dict[str, dict],
    reg: Any,
) -> Any | None:
    """Walk producer chain from a dataset name back to a collector DataSource."""
    seen: set[str] = set()
    current: str | None = dataset_name
    while current and current not in seen:
        seen.add(current)
        node = output_to_node.get(current)
        if node is None:
            return None
        t = node.get("type", "")
        cfg = node.get("config") or {}
        if t in ("FEATURE_ENGINE", "SIGNAL_CALCULATOR", "DATA_HIGHLIGHTER"):
            current = cfg.get("input_name")
            continue
        if t in _COLLECTOR_SOURCE:
            return reg.get(_COLLECTOR_SOURCE[t])
        current = cfg.get("input_name")
    return None


def _known_columns_for_dataset_name(
    output_name: str,
    output_to_node: dict[str, dict],
    reg: Any,
    cache: dict[str, frozenset[str] | None],
    visiting: set[str],
) -> frozenset[str] | None:
    if output_name in cache:
        return cache[output_name]
    if output_name in visiting:
        cache[output_name] = None
        return None
    visiting.add(output_name)
    node = output_to_node.get(output_name)
    if node is None:
        cache[output_name] = None
        visiting.remove(output_name)
        return None
    t = node.get("type", "")
    cfg = node.get("config") or {}
    result: frozenset[str] | None = None

    if t in _COLLECTOR_SOURCE:
        ds = reg.get(_COLLECTOR_SOURCE[t])
        if ds is not None:
            src = cfg.get("source")
            result = frozenset(ds.column_names(src))
    elif t == "SIGNAL_CALCULATOR":
        inn = cfg.get("input_name")
        sig_cols = frozenset(get_signal_output_columns())
        if inn:
            base = _known_columns_for_dataset_name(
                inn, output_to_node, reg, cache, visiting
            )
            result = (base | sig_cols) if base is not None else None
        else:
            result = None
    elif t == "FEATURE_ENGINE":
        inn = cfg.get("input_name")
        extras = frozenset(_feature_engine_added_columns(cfg))
        if inn:
            base = _known_columns_for_dataset_name(
                inn, output_to_node, reg, cache, visiting
            )
            result = (base | extras) if base is not None else None
        else:
            result = None
    elif t == "DATA_HIGHLIGHTER":
        inn = cfg.get("input_name")
        if inn:
            result = _known_columns_for_dataset_name(
                inn, output_to_node, reg, cache, visiting
            )
    else:
        inn = cfg.get("input_name")
        if inn:
            result = _known_columns_for_dataset_name(
                inn, output_to_node, reg, cache, visiting
            )

    cache[output_name] = result
    visiting.remove(output_name)
    return result


def _field_binding_references_known_column(
    field: str,
    known: set[str],
    semantics_ds: Any | None,
) -> bool:
    if not field or field in known:
        return True
    if semantics_ds is None:
        return False
    physical = semantics_ds.resolve_field(field, None)
    return physical is not None and physical in known


def _validate_field_bindings(
    nodes_by_id: dict[str, dict],
    result: ValidationResult,
) -> None:
    """Flag SECTION_SUMMARY field_bindings that don't resolve to a known column.

    Lineage is traced through FEATURE_ENGINE, SIGNAL_CALCULATOR, and
    DATA_HIGHLIGHTER so passthrough and derived columns are included.
    Semantic tags (e.g. ``size``) resolve via the traced collector's
    DataSource. Severity is *error* — unknown columns break stats at runtime.
    """
    from data_sources import get_registry

    reg = get_registry()
    output_to_node = _build_output_to_node(nodes_by_id)

    for nid, node in nodes_by_id.items():
        if node.get("type") != "SECTION_SUMMARY":
            continue
        cfg = node.get("config") or {}
        input_name = cfg.get("input_name")
        if not input_name:
            continue
        cache: dict[str, frozenset[str] | None] = {}
        known_f = _known_columns_for_dataset_name(
            input_name, output_to_node, reg, cache, set()
        )
        if known_f is None:
            continue
        known = set(known_f)
        semantics_ds = _trace_registry_ds(input_name, output_to_node, reg)

        for i, binding in enumerate(cfg.get("field_bindings") or []):
            if not isinstance(binding, dict):
                continue
            field = binding.get("field")
            if field and not _field_binding_references_known_column(
                field, known, semantics_ds
            ):
                ds_id = semantics_ds.id if semantics_ds is not None else input_name
                result.add(
                    _VC.UNKNOWN_COLUMN,
                    f"Node '{nid}' field_bindings[{i}].field='{field}' is not a known "
                    f"column for dataset '{input_name}' (traced source '{ds_id}'). "
                    f"Known: {sorted(known)}.",
                    severity="error",
                    node_id=nid,
                    field=f"config.field_bindings[{i}].field",
                )


def _validate_prompt_refs(
    nodes_by_id: dict[str, dict],
    result: ValidationResult,
) -> None:
    """Validate prompt refs that point at known datasets.

    We intentionally allow bare slots like {client_orders_count}: those may be
    supplied by prompt_context.vars. But when a ref head is a known dataset
    output, the rest of the ref must match the dataset schema/lineage.
    """
    from data_sources import get_registry

    reg = get_registry()
    output_to_node = _build_output_to_node(nodes_by_id)
    cache: dict[str, frozenset[str] | None] = {}

    def validate_ref(node_id: str, node: dict, field_path: str, ref: str) -> None:
        parts = ref.split(".")
        head = parts[0]
        if head == "context":
            return
        if head == "stats" and node.get("type") == "SECTION_SUMMARY":
            _validate_section_summary_stats_ref(node_id, node, field_path, ref, result)
            return
        if head not in output_to_node:
            return
        if len(parts) == 1:
            return

        known_f = _known_columns_for_dataset_name(
            head, output_to_node, reg, cache, set()
        )
        if known_f is None:
            return
        known = set(known_f)
        semantics_ds = _trace_registry_ds(head, output_to_node, reg)
        col = parts[1]

        if col.startswith("@"):
            if col != "@row_count":
                result.add(
                    _VC.BAD_PROMPT_REF,
                    f"Node '{node_id}' prompt ref '{{{ref}}}' uses unknown special ref "
                    f"'{col}' for dataset '{head}'. Supported special refs: @row_count.",
                    node_id=node_id,
                    field=field_path,
                )
            return

        if not _field_binding_references_known_column(col, known, semantics_ds):
            ds_id = semantics_ds.id if semantics_ds is not None else head
            result.add(
                _VC.BAD_PROMPT_REF,
                f"Node '{node_id}' prompt ref '{{{ref}}}' references unknown column "
                f"'{col}' for dataset '{head}' (traced source '{ds_id}'). "
                f"Known: {sorted(known)}.",
                node_id=node_id,
                field=field_path,
            )
            return

        if len(parts) >= 3:
            agg = parts[2]
            if agg not in AGG_FUNCS:
                result.add(
                    _VC.BAD_PROMPT_REF,
                    f"Node '{node_id}' prompt ref '{{{ref}}}' uses unknown aggregation "
                    f"'{agg}'. Known aggregations: {sorted(AGG_FUNCS)}.",
                    node_id=node_id,
                    field=field_path,
                )

    for nid, node in nodes_by_id.items():
        cfg = node.get("config") or {}
        if not isinstance(cfg, dict):
            continue

        for key in ("prompt_template", "llm_prompt_template", "system_prompt"):
            value = cfg.get(key)
            if not isinstance(value, str):
                continue
            for match in REF_RE.finditer(value):
                validate_ref(nid, node, f"config.{key}", match.group(1))

        prompt_context = cfg.get("prompt_context")
        if not isinstance(prompt_context, dict):
            continue
        vars_cfg = prompt_context.get("vars") or {}
        if not isinstance(vars_cfg, dict):
            continue
        for name, value in vars_cfg.items():
            if not isinstance(value, str):
                continue
            for match in REF_RE.finditer(value):
                validate_ref(
                    nid,
                    node,
                    f"config.prompt_context.vars.{name}",
                    match.group(1),
                )


def _validate_section_summary_stats_ref(
    node_id: str,
    node: dict,
    field_path: str,
    ref: str,
    result: ValidationResult,
) -> None:
    parts = ref.split(".")
    if len(parts) != 2:
        result.add(
            _VC.BAD_PROMPT_REF,
            f"Node '{node_id}' prompt ref '{{{ref}}}' is not a supported SECTION_SUMMARY stats ref. "
            "Use {stats} or {stats.<field>_<agg>}.",
            node_id=node_id,
            field=field_path,
        )
        return

    cfg = node.get("config") or {}
    mode = (cfg.get("mode") or "templated").lower()
    stat_name = parts[1]
    allowed = {"row_count", "signal_hits", "comm_keyword_hits"}

    if mode == "templated":
        for binding in cfg.get("field_bindings") or []:
            if not isinstance(binding, dict):
                continue
            field = binding.get("field")
            agg = binding.get("agg", "count")
            if not field:
                continue
            allowed.add(str(field))
            allowed.add(f"{field}_{agg}")
    elif mode == "fact_pack_llm":
        for fact in cfg.get("facts") or []:
            if isinstance(fact, dict) and fact.get("name"):
                allowed.add(str(fact["name"]))

    if stat_name not in allowed:
        result.add(
            _VC.BAD_PROMPT_REF,
            f"Node '{node_id}' prompt ref '{{{ref}}}' does not match computed SECTION_SUMMARY stats. "
            f"Known stats for this config: {sorted(allowed)}.",
            node_id=node_id,
            field=field_path,
        )


# ---------------------------------------------------------------------------
# MAP sub-workflow recursion
# ---------------------------------------------------------------------------
def _validate_map_sub_workflows(
    nodes_by_id: dict[str, dict], result: ValidationResult
) -> None:
    """Recursively validate every MAP node's inline sub_workflow.

    The inner DAG is a bounded scenario: its own nodes run once per
    iteration, it has no ALERT_TRIGGER (the iteration key is injected
    by MAP itself), and no REPORT_OUTPUT (reports are emitted by the
    parent workflow). We skip the `_validate_topology` pass and every
    other check still applies. Issues are prefixed with the MAP node's
    id so the UI can point to the right place.
    """
    for parent_id, parent in nodes_by_id.items():
        if parent.get("type") != "MAP":
            continue
        sub = (parent.get("config") or {}).get("sub_workflow")
        if not isinstance(sub, dict):
            continue  # shape was already flagged in _validate_node_config
        sub_nodes = sub.get("nodes") or []
        if not isinstance(sub_nodes, list) or not sub_nodes:
            result.add(
                _VC.EMPTY_WORKFLOW,
                f"MAP node '{parent_id}' sub_workflow has no nodes.",
                node_id=parent_id,
                field="config.sub_workflow.nodes",
            )
            continue

        sub_by_id = {n["id"]: n for n in sub_nodes if isinstance(n, dict) and "id" in n}
        sub_edges = sub.get("edges") or []

        # Structural: each node registered, edges endpoints valid,
        # acyclic. Reuse the same helpers so error codes stay consistent.
        local = ValidationResult()
        _validate_nodes_registered(sub_by_id, local)
        _validate_edges(sub_edges, sub_by_id, local)
        if local.valid:
            _validate_acyclic(sub_by_id, sub_edges, local)
        if local.valid:
            for nid, n in sub_by_id.items():
                _validate_node_config(n, local)
            # Wiring (input_name → upstream output_name) is skipped
            # inside a sub-workflow: MAP aliases a parent dataset into
            # the child ctx via iteration_dataset_alias, so the inner
            # nodes legitimately reference names that no sub-workflow
            # node produces. The parent DAG's wiring check still runs.
            _validate_field_bindings(sub_by_id, local)
            run_hard_rules(sub_by_id, {"nodes": sub_nodes, "edges": sub_edges}, local)
            # Recurse one more level for nested MAPs.
            _validate_map_sub_workflows(sub_by_id, local)

        # Re-scope sub-workflow issues under the parent MAP node.
        for issue in local.issues:
            result.add(
                issue.code,
                f"[MAP '{parent_id}' sub_workflow] {issue.message}",
                severity=issue.severity,
                node_id=parent_id,
                field="config.sub_workflow" if not issue.field else f"config.sub_workflow.{issue.field}",
            )


# ---------------------------------------------------------------------------
# Hard rules
# ---------------------------------------------------------------------------
# Node-type-specific hard rules live in `engine/hard_rules.py`.  Each
# rule is a decorator-registered callable that the `run_hard_rules`
# dispatcher (called in `validate_dag`) iterates over.  Nothing to
# add or edit here when a new rule ships.


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------
def _type(v: Any) -> str:
    return type(v).__name__


__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "validate_dag",
]
