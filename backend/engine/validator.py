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

from .collector_source import COLLECTOR_TYPE_TO_SOURCE_ID, collector_source_ref
from .dag_runner import _edge_endpoints, topological_sort
from .node_type_ids import (
    ALERT_TRIGGER,
    FEATURE_ENGINE,
    REPORT_OUTPUT,
    SECTION_SUMMARY,
    SIGNAL_CALCULATOR,
)
from .hard_rules import run_hard_rules
from .ports import ParamType
from .registry import NODE_SPECS, NodeSpec
from .schema_version import SchemaVersionError, migrate_to_current
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
    """Run all checks. Callers use `result.valid` or surface `result.issues`."""
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

    # --- Node-specific hard rules we can enforce programmatically. ---
    # Rules register themselves via `@register_hard_rule` in
    # `engine/hard_rules.py`. Adding a new rule is a decorator call,
    # not an edit to this file.
    run_hard_rules(nodes_by_id, dag, result)

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
    alert_triggers = [nid for nid, n in nodes_by_id.items() if n.get("type") == ALERT_TRIGGER]
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
    report_nodes = [nid for nid, n in nodes_by_id.items() if n.get("type") == REPORT_OUTPUT]
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

        # Collect all output_names produced by ancestors.
        produced: list[tuple[str, str]] = []
        for pid in preds[nid]:
            pcfg = nodes_by_id[pid].get("config") or {}
            if isinstance(pcfg, dict) and pcfg.get("output_name"):
                produced.append((pid, pcfg["output_name"]))

        produced_names = {name for _, name in produced}
        # Some upstream nodes (like FEATURE_ENGINE) pass through a
        # dataset under the same name — so also accept cases where the
        # named dataset matches *any* ancestor's output.
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
# Collector → data source id: single map in `collector_source` (runtime + validator).
# Transformers (FEATURE_ENGINE, SIGNAL_CALCULATOR) are followed backward from
# `SECTION_SUMMARY.input_name` to recover the same base, plus well-known extras.
_SIGNAL_EXTRAS: frozenset[str] = frozenset(
    {
        "_signal_flag",
        "_signal_score",
        "_signal_reason",
        "_signal_type",
        "_signal_window",
    }
)
_NORMALISE_EXTRAS: frozenset[str] = frozenset(
    {
        "signed_notional",
        "_prev_status",
        "_status_changed",
        "_lifecycle_event",
    }
)


def _producing_node_for_output(
    output_name: str, nodes_by_id: dict[str, dict]
) -> dict[str, Any] | None:
    for n in nodes_by_id.values():
        if (n.get("config") or {}).get("output_name") == output_name:
            return n
    return None


def _trace_dataset_to_registry(
    dataset_name: str,
    nodes_by_id: dict[str, dict],
    reg: Any,
) -> tuple[Any, str | None, set[str]]:
    """Walk from a table name to the base :class:`DataSource` and extras."""
    n = _producing_node_for_output(dataset_name, nodes_by_id)
    if n is None:
        return (None, None, set())
    t = n.get("type", "")
    cfg = n.get("config") or {}
    if t in COLLECTOR_TYPE_TO_SOURCE_ID:
        source_ref = collector_source_ref(t, cfg)
        return (reg.get(source_ref), source_ref, set())
    if t == SIGNAL_CALCULATOR:
        prev = cfg.get("input_name")
        if not prev or not isinstance(prev, str):
            return (None, None, set())
        ds, source_ref, ex = _trace_dataset_to_registry(prev, nodes_by_id, reg)
        return (ds, source_ref, ex | set(_SIGNAL_EXTRAS))
    if t == FEATURE_ENGINE:
        prev = cfg.get("input_name")
        if not prev or not isinstance(prev, str):
            return (None, None, set())
        ds, source_ref, ex = _trace_dataset_to_registry(prev, nodes_by_id, reg)
        return (ds, source_ref, ex | set(_NORMALISE_EXTRAS))
    return (None, None, set())


def _field_resolves(
    field: str,
    ds: Any,
    source_ref: str | None,
    extra_cols: set[str],
) -> bool:
    if field in extra_cols:
        return True
    source_name = None
    if source_ref and ":" in source_ref:
        _, source_name = source_ref.split(":", 1)
    if ds is not None and ds.resolve_field(field, source_name) is not None:
        return True
    return False


def _validate_field_bindings(
    nodes_by_id: dict[str, dict],
    result: ValidationResult,
) -> None:
    """Error when a SECTION_SUMMARY field name is not a registry column/semantic
    (for the traced base data source) nor a well-known extra from upstream
    transformers. Datasets that do not trace to a collector are skipped.
    """
    from data_sources import get_registry
    reg = get_registry()

    for nid, node in nodes_by_id.items():
        if node.get("type") != SECTION_SUMMARY:
            continue
        cfg = node.get("config") or {}
        input_name = cfg.get("input_name")
        if not input_name or not isinstance(input_name, str):
            continue
        ds, source_ref, extras = _trace_dataset_to_registry(input_name, nodes_by_id, reg)
        if ds is None:
            continue
        for i, binding in enumerate(cfg.get("field_bindings") or []):
            if not isinstance(binding, dict):
                continue
            field = binding.get("field")
            if not field:
                continue
            if not _field_resolves(field, ds, source_ref, extras):
                result.add(
                    _VC.UNKNOWN_COLUMN,
                    f"Node '{nid}' field_bindings[{i}].field='{field}' is not a column, "
                    f"registered semantic, or known transformer field for the traced source "
                    f"(`{source_ref or ds.id}`). Allowed names include registry columns, semantic tags, and "
                    f"extras: {sorted(extras)}.",
                    severity="error",
                    node_id=nid,
                    field=f"config.field_bindings[{i}].field",
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
