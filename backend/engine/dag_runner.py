import json
import logging
import time
import traceback
from collections import defaultdict, deque
from typing import Iterator

import pandas as pd

from .context import RunContext
from .ports import PortSpec, PortType
from .registry import NODE_HANDLERS, NODE_SPECS  # single source of truth — see registry.py

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output port contract enforcement
# ---------------------------------------------------------------------------
def _resolve_output_value(port: PortSpec, node: dict, ctx: RunContext) -> tuple[object, str] | None:
    """
    Find where the handler stored the port's value so we can type-check
    it. Lookup is **type-driven** because each PortType has a different
    storage convention in our handlers:

      DATAFRAME → `ctx.datasets[output_name]` (primary port) or
                  `ctx.datasets[port.name]`.
      SCALAR    → `ctx.values[port.name]`,
                  `ctx.values[f"{output_name}_{port.name}"]` (the
                  `{output_name}_count` / `{output_name}_flag_count`
                  convention), or attribute on ctx.
      TEXT      → `ctx.values[port.name]` or attribute on ctx.

    Returns `(value, location)` or `None` if the port isn't produced
    (allowed when `port.optional` is true).
    """
    cfg = node.get("config", {}) or {}
    output_name = cfg.get("output_name")

    if port.type is PortType.DATAFRAME:
        if output_name and output_name in ctx.datasets:
            return ctx.datasets[output_name], f"ctx.datasets[{output_name!r}]"
        if port.name in ctx.datasets:
            return ctx.datasets[port.name], f"ctx.datasets[{port.name!r}]"
        return None

    if port.type in (PortType.SCALAR, PortType.TEXT):
        if port.name in ctx.values:
            return ctx.values[port.name], f"ctx.values[{port.name!r}]"
        if output_name:
            key = f"{output_name}_{port.name}"
            if key in ctx.values:
                return ctx.values[key], f"ctx.values[{key!r}]"
        attr = getattr(ctx, port.name, None)
        if attr not in (None, ""):
            return attr, f"ctx.{port.name}"
        return None

    return None


def _assert_port_type(port: PortSpec, value: object) -> str | None:
    """Return an error string if `value` doesn't satisfy `port.type`."""
    if port.type is PortType.DATAFRAME:
        if not isinstance(value, pd.DataFrame):
            return f"expected DataFrame, got {type(value).__name__}"
    elif port.type is PortType.SCALAR:
        if not isinstance(value, (int, float, bool)) or isinstance(value, bool):
            # bools are ints in Python; we accept either.
            if not isinstance(value, (int, float)):
                return f"expected scalar (int|float), got {type(value).__name__}"
    elif port.type is PortType.TEXT:
        if not isinstance(value, str):
            return f"expected str, got {type(value).__name__}"
    elif port.type is PortType.OBJECT:
        if not isinstance(value, dict):
            return f"expected object/dict, got {type(value).__name__}"
    return None


def check_output_contract(node: dict, ctx: RunContext) -> list[str]:
    """
    After a handler runs, verify the node produced each declared
    non-optional output port with the right runtime type. Returns a
    list of human-readable issue strings (empty on success).

    This is a defence-in-depth check. The pre-flight validator already
    ensures the graph is wired correctly; this catches handlers that
    *claim* to produce a DataFrame but actually drop a scalar in the
    same slot, or forget to write a value altogether. Without this,
    downstream nodes fail later with cryptic KeyErrors.

    Scope: we enforce only DATAFRAME / SCALAR / TEXT ports today. OBJECT
    ports in our registry are used as conceptual buckets (e.g. "datasets"
    = all datasets, "context_keys" = whatever the node bound) rather
    than a single keyed value, so runtime resolution would be noisy
    without genuine safety. When a node wants a strict OBJECT check it
    can set the port's name to the literal ctx.values key it writes.
    """
    node_type = node.get("type")
    spec = NODE_SPECS.get(node_type)
    if spec is None:
        return []
    issues: list[str] = []
    for port in spec.output_ports:
        if port.type is PortType.OBJECT:
            continue  # conceptual bucket — see docstring
        resolved = _resolve_output_value(port, node, ctx)
        if resolved is None:
            if not port.optional:
                issues.append(
                    f"output port '{port.name}' ({port.type.value}) not produced"
                )
            continue
        value, location = resolved
        err = _assert_port_type(port, value)
        if err:
            issues.append(f"output port '{port.name}' at {location}: {err}")
    return issues


def _edge_endpoints(edge: dict) -> tuple[str, str]:
    """Accept either {from,to} (dbSherpa native) or {source,target} (ReactFlow / LLM output)."""
    src = edge.get("from") or edge.get("source")
    dst = edge.get("to") or edge.get("target")
    if not src or not dst:
        raise ValueError(f"Edge missing endpoints: {edge!r}")
    return src, dst


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm — returns node IDs in execution order."""
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}

    for edge in edges:
        src, dst = _edge_endpoints(edge)
        graph[src].append(dst)
        in_degree[dst] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in graph[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("DAG contains a cycle — check your edges")

    return order


def run_workflow(dag: dict, alert_payload: dict) -> RunContext:
    nodes_by_id = {n["id"]: n for n in dag["nodes"]}
    edges = dag.get("edges", [])
    order = topological_sort(list(nodes_by_id.values()), edges)

    ctx = RunContext(alert_payload=alert_payload)

    logger.info(
        "=== dbSherpa Workflow: %s (run_id=%s) ===",
        dag.get("name", dag.get("workflow_id")),
        ctx.run_id,
    )
    logger.info("Execution order: %s", order)

    for node_id in order:
        node = nodes_by_id[node_id]
        node_type = node["type"]
        handler = NODE_HANDLERS.get(node_type)
        if not handler:
            raise ValueError(f"Unknown node type '{node_type}' on node '{node_id}'")
        label = node.get("label", node_type)
        logger.info("  → [%s] %s", node_id, label)
        handler(node, ctx)
        # Post-condition: the handler must have produced every
        # non-optional output port with the declared runtime type.
        contract_issues = check_output_contract(node, ctx)
        if contract_issues:
            raise ValueError(
                f"Node '{node_id}' ({node_type}) violated its output contract: "
                + "; ".join(contract_issues)
            )

    logger.info(
        "Workflow complete (run_id=%s). Disposition=%s | Report=%s",
        ctx.run_id,
        ctx.disposition,
        ctx.report_path,
    )
    return ctx


def load_and_run(dag_path: str, alert_payload: dict) -> RunContext:
    with open(dag_path) as f:
        dag = json.load(f)
    return run_workflow(dag, alert_payload)


# ── Streaming execution with per-node events ─────────────────────────────────

def _preview_dataset(df: pd.DataFrame, max_rows: int = 3) -> dict:
    """Small JSON-safe preview of a DataFrame for the UI."""
    try:
        head = df.head(max_rows).copy()
        for col in head.columns:
            if head[col].dtype.kind == "M":  # datetimes
                head[col] = head[col].astype(str)
            elif head[col].apply(lambda v: isinstance(v, (list, dict))).any():
                head[col] = head[col].apply(str)
        return {
            "rows": int(len(df)),
            "columns": list(map(str, df.columns)),
            "sample": head.to_dict(orient="records"),
        }
    except Exception:
        return {"rows": int(len(df)) if df is not None else 0, "columns": [], "sample": []}


def _snapshot_output(node: dict, ctx: RunContext, before: dict) -> dict:
    """Describe what changed in the context as a result of executing `node`."""
    node_type = node["type"]
    cfg = node.get("config", {})
    summary: dict = {}

    # New / changed datasets
    new_datasets = {}
    for name, df in ctx.datasets.items():
        sig = (id(df), len(df))
        if before["dataset_sigs"].get(name) != sig:
            new_datasets[name] = _preview_dataset(df)
    if new_datasets:
        summary["datasets"] = new_datasets

    # New / changed context values
    new_values = {k: v for k, v in ctx.values.items() if before["values"].get(k) != v}
    if new_values:
        summary["context"] = {k: _jsonable(v) for k, v in new_values.items()}

    # Node-type specific highlights
    if node_type == "DECISION_RULE":
        summary["disposition"] = ctx.disposition
        summary["flag_count"] = ctx.get("flag_count", 0)
        summary["output_branch"] = ctx.output_branch
    if node_type == "CONSOLIDATED_SUMMARY":
        es = ctx.executive_summary or ""
        summary["executive_summary_preview"] = es[:400] + ("…" if len(es) > 400 else "")
        summary["executive_summary_chars"] = len(es)
    if node_type == "SECTION_SUMMARY":
        section_name = cfg.get("section_name", "section")
        sec = ctx.sections.get(section_name)
        if sec:
            narrative = sec.get("narrative", "") or ""
            summary["section"] = {
                "name": section_name,
                "stats": _jsonable(sec.get("stats", {})),
                "narrative_preview": narrative[:240] + ("…" if len(narrative) > 240 else ""),
            }
    if node_type == "REPORT_OUTPUT":
        summary["report_path"] = ctx.report_path

    return summary


def _jsonable(v):
    """Best-effort conversion so SSE payload always JSON-serialises."""
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


def run_workflow_stream(
    dag: dict, alert_payload: dict
) -> Iterator[dict]:
    """
    Execute a workflow and yield an event per phase.

    Event shapes:
      {"type":"workflow_start", "name":..., "total_nodes":N, "order":[ids]}
      {"type":"node_start", "node_id", "node_type", "label", "index", "total", "started_at":<iso>}
      {"type":"node_complete", "node_id", "duration_ms", "status":"ok", "output":{...}}
      {"type":"node_error", "node_id", "duration_ms", "status":"error", "error":"...", "trace":"..."}
      {"type":"workflow_complete", "total_duration_ms", "result":{...}}   # shape matches /run response
      {"type":"workflow_error", "error":"..."}
    """
    from datetime import datetime, timezone
    t0 = time.perf_counter()

    # Allocate the RunContext early so the run_id is known even if
    # topological sort fails — any workflow_error frame below still
    # carries it, so the UI / audit log can correlate.
    ctx = RunContext(alert_payload=alert_payload)

    def _stamp(ev: dict) -> dict:
        """Every frame gets the run_id so a trace can be reconstructed."""
        ev.setdefault("run_id", ctx.run_id)
        return ev

    try:
        nodes_by_id = {n["id"]: n for n in dag["nodes"]}
        edges = dag.get("edges", [])
        order = topological_sort(list(nodes_by_id.values()), edges)
    except Exception as exc:
        yield _stamp({"type": "workflow_error", "error": str(exc)})
        return

    yield _stamp({
        "type": "workflow_start",
        "name": dag.get("name", dag.get("workflow_id", "workflow")),
        "total_nodes": len(order),
        "order": order,
    })

    for idx, node_id in enumerate(order, 1):
        node = nodes_by_id[node_id]
        node_type = node["type"]
        label = node.get("label", node_type)
        handler = NODE_HANDLERS.get(node_type)

        # Snapshot so we can describe what the node changed.
        before = {
            "dataset_sigs": {n: (id(df), len(df)) for n, df in ctx.datasets.items()},
            "values": dict(ctx.values),
        }

        started_at = datetime.now(timezone.utc).isoformat()
        yield _stamp({
            "type": "node_start",
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "index": idx,
            "total": len(order),
            "started_at": started_at,
        })

        if not handler:
            yield _stamp({
                "type": "node_error",
                "node_id": node_id,
                "duration_ms": 0,
                "status": "error",
                "error": f"Unknown node type '{node_type}'",
                "trace": "",
            })
            yield _stamp({"type": "workflow_error", "error": f"Unknown node type '{node_type}' on node '{node_id}'"})
            return

        node_t0 = time.perf_counter()
        try:
            handler(node, ctx)
            contract_issues = check_output_contract(node, ctx)
            if contract_issues:
                # Surface as a structured node_error so the UI can
                # show a red node immediately; the workflow_error
                # frame below closes the stream. No KeyError surprises
                # for downstream nodes.
                raise ValueError(
                    "output contract violated: " + "; ".join(contract_issues)
                )
        except Exception as exc:
            dur = int((time.perf_counter() - node_t0) * 1000)
            logger.exception("Node %s failed (run_id=%s)", node_id, ctx.run_id)
            yield _stamp({
                "type": "node_error",
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "duration_ms": dur,
                "status": "error",
                "error": str(exc),
                "trace": traceback.format_exc(limit=3),
            })
            yield _stamp({"type": "workflow_error", "error": f"{node_id} ({node_type}): {exc}"})
            return

        dur = int((time.perf_counter() - node_t0) * 1000)
        output = _snapshot_output(node, ctx, before)
        yield _stamp({
            "type": "node_complete",
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "duration_ms": dur,
            "status": "ok",
            "output": output,
        })

    total_ms = int((time.perf_counter() - t0) * 1000)
    result = {
        "run_id": ctx.run_id,
        "disposition": ctx.disposition,
        "flag_count": ctx.get("flag_count", 0),
        "output_branch": ctx.output_branch,
        "report_path": ctx.report_path,
        "datasets": list(ctx.datasets.keys()),
        "sections": {
            name: {"stats": _jsonable(s["stats"]), "narrative": s["narrative"]}
            for name, s in ctx.sections.items()
        },
        "executive_summary": ctx.executive_summary,
    }
    yield _stamp({
        "type": "workflow_complete",
        "total_duration_ms": total_ms,
        "result": result,
    })
