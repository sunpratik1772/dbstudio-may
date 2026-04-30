"""
DAG runner — executes a workflow definition against a RunContext.

This is the heart of the engine. The contract it implements is small:

  1. Validate the DAG is acyclic (topological_sort raises on cycles).
  2. Walk nodes in topo order; for each, look up its handler in
     `NODE_HANDLERS` and call `handler(node_dict, ctx)`.
  3. After each handler returns, type-check the values it stored at
     each declared output_port (see `_resolve_output_value`). A
     handler that lies about its outputs fails fast — preferable to a
     mysterious KeyError ten nodes downstream.
  4. Stream events (`workflow_start`, `node_start`, `node_complete`,
     `node_error`, `workflow_complete`, `workflow_error`) to anyone
     subscribing through the SSE generator (`run_workflow_stream`).
     The non-streaming `run_workflow` is just the same loop without
     yielding events.

If you're new here:

  * Start at `run_workflow` (bottom of file). It's the canonical
    entry point used by HTTP `/run` and most tests.
  * The `topological_sort` and `_edge_endpoints` helpers are pure
    graph utilities — also used by the validator, hence kept here.
  * Output-port enforcement is pedantic on purpose: it's our only
    automated check that a handler actually produced what its YAML
    declared. Without it, the wiring grammar `{dataset.col.agg}`
    silently breaks two scenarios later.

Nothing in this file knows about specific node types. New nodes plug
in via the registry — no edits needed here.
"""
import json
import logging
import re
import time
import traceback
from collections import defaultdict, deque
from typing import Iterator

from .node_spec import NodeSpec

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


def _resolve_object_port_value(
    port: PortSpec, node: dict, ctx: RunContext
) -> tuple[object, str] | None:
    """Locate a stored OBJECT output using `port.store_at` (subset of patterns)."""
    if port.type is not PortType.OBJECT or not port.store_at:
        return None
    cfg = node.get("config") or {}
    sa = port.store_at
    m = re.fullmatch(r"ctx\.sections\[\{(\w+)\}\]", sa)
    if m:
        key = cfg.get(m.group(1))
        if key is None:
            return None
        return ctx.sections.get(key), f"ctx.sections[{key!r}]"
    m = re.fullmatch(r"ctx\.values\[(\w+)\]", sa)
    if m:
        name = m.group(1)
        return ctx.values.get(name), f"ctx.values[{name!r}]"
    return None


def _output_dataframe_required_columns(
    port: PortSpec, spec: NodeSpec, node: dict
) -> tuple[str, ...]:
    """
    Declared columns for a dataframe output port — either static
    `port.required_columns` or `contract.output_columns_by_source` when
    the node opts into source-keyed schemas (see EXECUTION_DATA_COLLECTOR).
    """
    contract = spec.contract or {}
    schema_port = contract.get("source_keyed_schema_port")
    if schema_port and port.name == schema_port:
        by_source = contract.get("output_columns_by_source") or {}
        param = contract.get("source_param_for_schema", "source")
        default = contract.get("source_schema_default")
        cfg = node.get("config") or {}
        source = cfg.get(param, default)
        if source is None:
            source = ""
        cols = by_source.get(str(source), ())
        return tuple(str(c) for c in cols)
    return port.required_columns


def check_input_port_schema(node: dict, ctx: RunContext) -> list[str]:
    """
    Before/after wiring checks: for each input DATAFRAME port that declares
    `required_columns`, ensure the referenced dataset (via
    `source_config_key` or default ``input_name``) exists in ctx and
    contains those columns.

    If the dataset is absent, returns no issues — some nodes pull inputs
    from alternate paths (e.g. scalar fallbacks).
    """
    node_type = node.get("type")
    spec = NODE_SPECS.get(node_type)
    if spec is None:
        return []
    cfg = node.get("config") or {}
    issues: list[str] = []
    for port in spec.input_ports:
        if port.type is not PortType.DATAFRAME or not port.required_columns:
            continue
        key_field = port.source_config_key or "input_name"
        ds_name = cfg.get(key_field)
        if not ds_name:
            continue
        df = ctx.datasets.get(ds_name)
        if df is None:
            continue
        if not isinstance(df, pd.DataFrame):
            issues.append(
                f"input port '{port.name}': expected DataFrame at ctx.datasets[{ds_name!r}], "
                f"got {type(df).__name__}"
            )
            continue
        for col in port.required_columns:
            if col not in df.columns:
                issues.append(
                    f"input port '{port.name}' dataset {ds_name!r}: missing column {col!r}"
                )
    return issues


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

    OBJECT ports are skipped unless they declare `required_keys` and a
    `store_at` path we can resolve (strict sections / values objects).
    """
    node_type = node.get("type")
    spec = NODE_SPECS.get(node_type)
    if spec is None:
        return []
    issues: list[str] = []
    for port in spec.output_ports:
        if port.type is PortType.OBJECT:
            if not port.required_keys:
                continue
            resolved = _resolve_object_port_value(port, node, ctx)
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
                continue
            if not isinstance(value, dict):
                continue
            for rk in port.required_keys:
                if rk not in value:
                    issues.append(
                        f"output port '{port.name}' at {location}: missing key {rk!r}"
                    )
            continue
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
            continue
        if (
            port.type is PortType.DATAFRAME
            and port.required_columns
            and isinstance(value, pd.DataFrame)
        ):
            for col in port.required_columns:
                if col not in value.columns:
                    issues.append(
                        f"output port '{port.name}' at {location}: missing column {col!r}"
                    )
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


def execute_nodes(nodes: list[dict], edges: list[dict], ctx: RunContext) -> None:
    """
    Run a set of nodes against an existing RunContext.

    Extracted from `run_workflow` so the MAP primitive (and future
    SUB_WORKFLOW / IF primitives) can execute a nested DAG inside the
    same runtime path. Callers own ctx lifecycle — this helper just
    advances it through the nodes in topological order and enforces
    the per-node output contract.
    """
    nodes_by_id = {n["id"]: n for n in nodes}
    order = topological_sort(nodes, edges)
    for node_id in order:
        node = nodes_by_id[node_id]
        node_type = node["type"]
        handler = NODE_HANDLERS.get(node_type)
        if not handler:
            raise ValueError(f"Unknown node type '{node_type}' on node '{node_id}'")
        label = node.get("label", node_type)
        logger.info("  → [%s] %s", node_id, label)
        input_issues = check_input_port_schema(node, ctx)
        if input_issues:
            raise ValueError(
                f"Node '{node_id}' ({node_type}) violated its input contract: "
                + "; ".join(input_issues)
            )
        handler(node, ctx)
        contract_issues = check_output_contract(node, ctx)
        if contract_issues:
            raise ValueError(
                f"Node '{node_id}' ({node_type}) violated its output contract: "
                + "; ".join(contract_issues)
            )


def run_workflow(dag: dict, alert_payload: dict) -> RunContext:
    """Synchronously run a DAG to completion. The standard entry point.

    `dag` is the parsed workflow JSON (nodes + edges). `alert_payload`
    is the immutable input — trader_id, event_time, etc. — that the
    ALERT_TRIGGER node copies into ctx.values.

    Returns the populated RunContext. Inspect `.disposition`,
    `.report_path`, `.sections`, `.executive_summary`, and
    `.datasets[...]` to verify outputs in tests.

    Raises whatever the failing handler raised — the runner does not
    swallow exceptions in the non-streaming path. Use
    `run_workflow_stream` if you want per-node events instead.
    """
    nodes = dag["nodes"]
    edges = dag.get("edges", [])

    ctx = RunContext(alert_payload=alert_payload)

    logger.info(
        "=== dbSherpa Workflow: %s (run_id=%s) ===",
        dag.get("name", dag.get("workflow_id")),
        ctx.run_id,
    )
    logger.info("Execution order: %s", topological_sort(nodes, edges))

    execute_nodes(nodes, edges, ctx)

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

    agent_response = _agent_response(node, new_values, ctx)
    if agent_response:
        summary["agent_response"] = agent_response

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


def _agent_response(node: dict, new_values: dict, ctx: RunContext) -> str | None:
    """Return a concise human-readable response for agent-layer nodes."""
    node_type = node.get("type")
    if not _is_agent_node(node_type):
        return None
    cfg = node.get("config") or {}

    def pick(default_key: str) -> object:
        key = str(cfg.get("output_name") or default_key)
        if key in new_values:
            return new_values[key]
        return ctx.get(key)

    if node_type == "LLM_PLANNER":
        plan = pick("plan")
        steps = plan.get("steps") if isinstance(plan, dict) else []
        if steps:
            first = steps[0]
            action = first.get("action") or first.get("tool") or "next step"
            return f"Planned {len(steps)} step(s). First step: {action}."
        return "Created an investigation plan."

    if node_type == "PLAN_VALIDATOR":
        result = pick("plan_validation")
        return _validity_sentence(result, "Plan")

    if node_type == "LLM_ACTION":
        action = pick("action")
        if isinstance(action, dict):
            tool = action.get("tool") or "tool"
            reasoning = action.get("reasoning")
            confidence = action.get("confidence")
            suffix = f" Confidence: {confidence}." if confidence is not None else ""
            return f"Selected `{tool}` as the next action.{suffix}" + (f" {reasoning}" if reasoning else "")
        return "Selected the next action."

    if node_type == "ACTION_VALIDATOR":
        result = pick("action_validation")
        return _validity_sentence(result, "Action")

    if node_type == "GUARDRAIL":
        result = pick("guardrail_result")
        return _validity_sentence(result, "Safety guardrail")

    if node_type == "TOOL_EXECUTOR":
        result = pick("last_result")
        if isinstance(result, dict):
            status = result.get("status", "ok")
            output = result.get("output_name") or result.get("artifact_path") or result.get("node_type")
            rows = result.get("rows")
            bits = [f"Tool execution finished with status `{status}`."]
            if output:
                bits.append(f"Output: {output}.")
            if rows is not None:
                bits.append(f"Rows: {rows}.")
            return " ".join(bits)
        return "Executed the selected tool."

    if node_type == "LLM_CRITIC":
        result = pick("validation")
        if isinstance(result, dict):
            valid = bool(result.get("valid"))
            confidence = result.get("confidence")
            issues = result.get("issues") or []
            suggestions = result.get("suggestions") or []
            status = "accepted the result" if valid else "found issues"
            text = f"The critic {status}"
            if confidence is not None:
                text += f" with confidence {confidence}"
            text += "."
            if issues:
                text += " Issues: " + "; ".join(map(str, issues[:3])) + "."
            if suggestions:
                text += " Suggestions: " + "; ".join(map(str, suggestions[:3])) + "."
            return text
        return "Critiqued the latest result."

    if node_type == "STATE_MANAGER":
        state = pick("retry_context")
        iteration = state.get("iteration") if isinstance(state, dict) else None
        return f"Updated agent memory." + (f" Iteration is now {iteration}." if iteration is not None else "")

    if node_type == "LLM_EVALUATOR":
        result = pick("evaluator_status")
        if isinstance(result, dict):
            done = bool(result.get("done"))
            confidence = result.get("confidence")
            missing = result.get("missing") or []
            text = "The goal is satisfied" if done else "The goal is not satisfied yet"
            if confidence is not None:
                text += f" with confidence {confidence}"
            text += "."
            if missing:
                text += " Missing: " + "; ".join(map(str, missing[:3])) + "."
            return text
        return "Evaluated goal satisfaction."

    if node_type == "LOOP_CONTROLLER":
        result = pick("loop_decision")
        if isinstance(result, dict):
            action = "continue" if result.get("continue") else "stop"
            reason = result.get("stop_reason") or "decision made"
            iteration = result.get("iteration")
            return f"Loop controller decided to {action}. Reason: {reason}. Iteration: {iteration}."
        return "Updated loop control."

    if node_type == "LLM_SYNTHESIZER":
        result = pick("final_output")
        return _payload_text(result) or "Synthesized the final response."

    if node_type == "LLM_CONTEXTUALIZER":
        result = pick("enriched_context")
        return _payload_text(result) or "Enriched the context for downstream reasoning."

    if node_type == "AGGREGATOR_NODE":
        return "Aggregated selected context values and datasets."

    if node_type == "DATA_REDUCER":
        summary_key = f"{str(cfg.get('output_name') or 'reduced_data')}_summary"
        result = new_values.get(summary_key) or ctx.get(summary_key)
        return _payload_text(result) or "Reduced the dataset for agent review."

    if node_type == "ERROR_HANDLER":
        result = pick("recovery_strategy")
        return _payload_text(result) or "Selected a recovery strategy."

    return None


def _is_agent_node(node_type: object) -> bool:
    if not isinstance(node_type, str):
        return False
    spec = NODE_SPECS.get(node_type)
    return bool(spec and spec.ui.get("palette_group") == "agent")


def _validity_sentence(result: object, subject: str) -> str:
    if not isinstance(result, dict):
        return f"{subject} validation completed."
    valid = bool(result.get("valid"))
    errors = result.get("errors") or result.get("issues") or []
    text = f"{subject} validation {'passed' if valid else 'failed'}."
    if errors:
        text += " " + "; ".join(map(str, errors[:3])) + "."
    return text


def _payload_text(payload: object) -> str | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("response", "text", "summary", "memo", "narrative", "answer", "final_output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        result = payload.get("result")
        if isinstance(result, dict):
            done = result.get("done")
            confidence = result.get("confidence")
            missing = result.get("missing") or []
            if done is not None or confidence is not None or missing:
                text = f"Escalation readiness is {'complete' if done else 'incomplete'}"
                if confidence is not None:
                    text += f" with confidence {confidence}"
                text += "."
                if missing:
                    text += " Missing: " + "; ".join(map(str, missing[:3])) + "."
                return text
    return None


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
            input_issues = check_input_port_schema(node, ctx)
            if input_issues:
                raise ValueError(
                    "input contract violated: " + "; ".join(input_issues)
                )
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
