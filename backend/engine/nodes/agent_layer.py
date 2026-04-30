"""
Agent-layer nodes.

These nodes let generated workflows express the cognitive control pattern:
plan -> action -> deterministic execution -> critic -> evaluator -> synthesize.
They are deterministic by default so local E2E runs can verify artifacts without
requiring an LLM provider, but the LLM-facing nodes can opt into model calls via
``config.use_llm``.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..prompt_context import build_slots, render_prompt


_BUILTIN_TOOLS = {
    "aggregation",
    "data_quality_checks",
    "multi_source_join",
    "transform",
    "emit_artifact",
    "passthrough",
}

_DEFAULT_SYSTEM_PROMPTS = {
    "LLM_PLANNER": (
        "You are the planner in a ReAct-style workflow engine. Produce a small, "
        "acyclic, executable JSON plan using only registered tools and provided context. "
        "Do not execute tools. Do not invent unavailable data."
    ),
    "LLM_ACTION": (
        "You are the action selector in a ReAct-style workflow engine. Convert the "
        "current plan step and critic feedback into exactly one tool call. The next "
        "action must change when validation feedback identifies a flaw."
    ),
    "LLM_CRITIC": (
        "You are the critic for a deterministic execution engine. Judge the last "
        "action and result against the expected schema. Return actionable suggestions "
        "that can directly improve the next action."
    ),
    "LLM_EVALUATOR": (
        "You are the evaluator. Decide whether the workflow goal is satisfied from "
        "the current state. Be strict about missing evidence and low-confidence results."
    ),
    "LLM_SYNTHESIZER": (
        "You are the synthesizer. Convert validated intermediate results into a concise "
        "final artifact payload. Preserve concrete facts, row counts, paths, and issues."
    ),
    "LLM_CONTEXTUALIZER": (
        "You are the contextualizer. Combine the user query, retrieved documents, and "
        "workflow state into compact context for downstream planning."
    ),
}


def _cfg(node: dict) -> dict:
    return node.get("config") or {}


def _output_name(node: dict, default: str) -> str:
    return str(_cfg(node).get("output_name") or default)


def _state(ctx: RunContext, key: str, default: Any = None) -> Any:
    return ctx.values.get(key, default)


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return {
            "rows": int(len(value)),
            "columns": list(map(str, value.columns)),
            "sample": value.head(5).to_dict(orient="records"),
        }
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return str(value)


def _first_dataset(ctx: RunContext) -> tuple[str, pd.DataFrame] | tuple[None, None]:
    for name, df in ctx.datasets.items():
        if isinstance(df, pd.DataFrame):
            return name, df
    return None, None


def _prompt_slots(ctx: RunContext, cfg: dict, **extra: Any) -> dict[str, Any]:
    slots = {
        "goal": cfg.get("goal") or ctx.get("goal") or ctx.alert_payload.get("goal", ""),
        "alert_payload": json.dumps(ctx.alert_payload, default=str),
        "state": json.dumps({k: _jsonable(v) for k, v in ctx.values.items()}, default=str),
        "datasets": json.dumps({name: _jsonable(df) for name, df in ctx.datasets.items()}, default=str),
    }
    slots.update({k: _jsonable(v) for k, v in ctx.alert_payload.items()})
    slots.update({k: _jsonable(v) for k, v in ctx.values.items()})
    for name, df in ctx.datasets.items():
        if isinstance(df, pd.DataFrame):
            slots.setdefault(f"{name}_count", int(len(df)))
            if name == "market_data":
                slots.setdefault("market_data_tick_count", int(len(df)))
    slots.update(build_slots(cfg.get("prompt_context"), ctx))
    for key, value in extra.items():
        slots[key] = value if isinstance(value, str) else json.dumps(_jsonable(value), default=str)
    return slots


def _render_config_text(template: str, ctx: RunContext, cfg: dict, **extra: Any) -> str:
    return render_prompt(template, ctx, **_prompt_slots(ctx, cfg, **extra))


def _template(cfg: dict, default: str) -> str:
    return cfg.get("prompt_template") or cfg.get("llm_prompt_template") or default


def _use_llm(cfg: dict) -> bool:
    if "use_llm" in cfg:
        return bool(cfg.get("use_llm"))
    return bool(cfg.get("system_prompt") or cfg.get("prompt_template") or cfg.get("llm_prompt_template"))


def _llm_json(
    prompt: str,
    fallback: dict,
    *,
    use_llm: bool,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_output_tokens: int = 1200,
) -> dict:
    if not use_llm:
        return fallback
    try:
        from llm import get_default_adapter

        raw = get_default_adapter().single_shot(
            prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
        )
        match = re.search(r"\{[\s\S]*\}", raw or "")
        if not match:
            return {**fallback, "llm_raw": raw}
        parsed = json.loads(match.group())
        return parsed if isinstance(parsed, dict) else fallback
    except Exception as exc:
        return {**fallback, "llm_error": str(exc)}


def _validation(valid: bool, issues: list[str] | None = None, suggestions: list[str] | None = None, confidence: float = 1.0) -> dict:
    return {
        "valid": bool(valid),
        "issues": issues or [],
        "suggestions": suggestions or [],
        "confidence": float(confidence),
    }


def _normalise_tool(tool: str) -> str:
    return (tool or "").strip()


def _tool_exists(tool: str) -> bool:
    if not tool:
        return False
    if tool.lower() in _BUILTIN_TOOLS:
        return True
    try:
        from ..registry import NODE_HANDLERS

        return tool.upper() in NODE_HANDLERS
    except Exception:
        return False


def _plan_steps(goal: str, cfg: dict) -> list[dict]:
    if isinstance(cfg.get("plan"), list):
        return list(cfg["plan"])
    tool = cfg.get("tool") or "aggregation"
    return [
        {
            "step_id": "step_1",
            "action": cfg.get("action") or goal or "Run requested analysis",
            "tool": tool,
            "inputs": cfg.get("inputs") or {},
            "dependencies": [],
        }
    ]


def handle_llm_planner(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    goal = cfg.get("goal") or ctx.get("goal") or ctx.alert_payload.get("goal") or "Run workflow"
    fallback = {"goal": goal, "steps": _plan_steps(str(goal), cfg)}
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_PLANNER"],
        ctx,
        cfg,
        plan_schema={"goal": "string", "steps": [{"step_id": "string", "action": "string", "tool": "string", "inputs": {}, "dependencies": []}]},
    )
    prompt = _render_config_text(
        cfg.get("prompt_template") or "Goal: {goal}\nState:\n{state}\nReturn only JSON matching {plan_schema}.",
        ctx,
        cfg,
        goal=goal,
    )
    plan = _llm_json(
        prompt,
        fallback,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.0)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1200)),
    )
    ctx.set(_output_name(node, "plan"), plan)
    ctx.set("plan", plan)


def handle_llm_action(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    plan = _state(ctx, cfg.get("plan_key", "plan"), {}) or {}
    validation = _state(ctx, cfg.get("validation_key", "validation"), {}) or {}
    retry_context = _state(ctx, cfg.get("retry_context_key", "retry_context"), {}) or {}
    steps = plan.get("steps") if isinstance(plan, dict) else []
    step = cfg.get("current_step") or (steps[0] if steps else {})
    fallback = {
        "tool": cfg.get("tool") or step.get("tool") or "aggregation",
        "args": {**(step.get("inputs") or {}), **(cfg.get("args") or {})},
        "reasoning": "Use the current plan step, incorporating critic feedback.",
        "confidence": 0.75,
    }
    suggestions = validation.get("suggestions") or []
    if suggestions:
        fallback["args"]["validation_feedback"] = suggestions
    if retry_context.get("previous_attempts"):
        fallback["args"]["attempt"] = len(retry_context["previous_attempts"]) + 1
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_ACTION"],
        ctx,
        cfg,
    )
    prompt = _render_config_text(
        _template(
            cfg,
            "Current step:\n{current_step}\n\nValidation feedback:\n{validation_feedback}\n\nRetry context:\n{retry_context}\n\nReturn only JSON with fields: tool, args, reasoning, confidence.",
        ),
        ctx,
        cfg,
        current_step=step,
        validation_feedback=suggestions,
        retry_context=retry_context,
    )
    action = _llm_json(
        prompt,
        fallback,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.0)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1200)),
    )
    ctx.set(_output_name(node, "action"), action)
    ctx.set("last_action", action)


def handle_action_validator(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    action = _state(ctx, cfg.get("action_key", "last_action"), {}) or {}
    tool = _normalise_tool(str(action.get("tool") or cfg.get("tool") or ""))
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    errors: list[str] = []
    if not _tool_exists(tool):
        errors.append(f"Unknown tool '{tool}'.")
    if not isinstance(args, dict):
        errors.append("Action args must be an object.")
    input_name = args.get("input_name")
    if input_name and input_name not in ctx.datasets:
        errors.append(f"input_name '{input_name}' is not present in ctx.datasets.")
    result = {"valid": not errors, "errors": errors, "tool": tool, "args": args}
    ctx.set(_output_name(node, "action_validation"), result)
    ctx.set("action_validation", result)
    if errors and cfg.get("block_on_invalid"):
        raise ValueError("; ".join(errors))


def _run_aggregation(ctx: RunContext, args: dict) -> dict:
    input_name = args.get("input_name")
    if input_name:
        df = ctx.datasets.get(str(input_name))
    else:
        input_name, df = _first_dataset(ctx)
    output_name = str(args.get("output_name") or "aggregation_result")
    if df is None:
        out = pd.DataFrame()
        ctx.datasets[output_name] = out
        return {"status": "empty", "output_name": output_name, "rows": 0, "warning": "No input dataset available."}
    group_by = args.get("group_by")
    metrics = args.get("metrics") or args.get("metric") or []
    if isinstance(metrics, str):
        metrics = [metrics]
    metrics = [m for m in metrics if m in df.columns]
    if group_by and group_by in df.columns and metrics:
        out = df.groupby(group_by, dropna=False)[metrics].sum(numeric_only=True).reset_index()
    elif metrics:
        out = pd.DataFrame([{m: df[m].sum() if pd.api.types.is_numeric_dtype(df[m]) else df[m].count() for m in metrics}])
    else:
        out = pd.DataFrame([{"row_count": int(len(df))}])
    ctx.datasets[output_name] = out
    return {"status": "ok", "output_name": output_name, "rows": int(len(out)), "columns": list(map(str, out.columns))}


def _run_quality(ctx: RunContext, args: dict) -> dict:
    input_name = args.get("input_name") or args.get("dataset_name")
    df = ctx.datasets.get(str(input_name)) if input_name else _first_dataset(ctx)[1]
    checks = args.get("checks") or ["duplicates", "nulls"]
    output_name = str(args.get("output_name") or "quality_report")
    if df is None:
        report = {
            "row_count": 0,
            "duplicates": 0,
            "nulls": {},
            "issues": ["No input dataset available."],
            "warning": "No input dataset available.",
        }
    else:
        report = {"row_count": int(len(df)), "issues": []}
        if "duplicates" in checks or any(c.get("type") == "duplicates" for c in checks if isinstance(c, dict)):
            report["duplicates"] = _duplicate_count(df)
        if "nulls" in checks or any(c.get("type") == "null_columns" for c in checks if isinstance(c, dict)):
            report["nulls"] = {str(k): int(v) for k, v in df.isna().sum().to_dict().items()}
        for check in checks:
            if not isinstance(check, dict):
                continue
            check_type = check.get("type")
            if check_type == "row_count_min":
                minimum = int(check.get("value") or 0)
                if len(df) < minimum:
                    report["issues"].append(
                        f"row_count {len(df)} below minimum {minimum}"
                    )
            elif check_type == "null_columns":
                threshold = float(check.get("threshold", 0.0))
                null_issues: dict[str, float] = {}
                for column in check.get("columns") or []:
                    if column not in df.columns:
                        null_issues[str(column)] = 1.0
                        report["issues"].append(f"missing required column {column!r}")
                        continue
                    ratio = float(df[column].isna().mean()) if len(df) else 0.0
                    if ratio > threshold:
                        null_issues[str(column)] = ratio
                        report["issues"].append(
                            f"null ratio for {column!r} {ratio:.2%} exceeds {threshold:.2%}"
                        )
                if null_issues:
                    report.setdefault("null_column_issues", {}).update(null_issues)
    if input_name:
        ctx.set(f"{input_name}_count", int(report.get("row_count", 0)))
        if input_name == "market_data":
            ctx.set("market_data_tick_count", int(report.get("row_count", 0)))
    ctx.set(output_name, report)
    return {
        "status": "ok" if not report.get("issues") else "issues",
        "output_name": output_name,
        "input_name": input_name,
        "report": report,
    }


def _duplicate_count(df: pd.DataFrame) -> int:
    """Count duplicates even when object cells contain unhashable lists/dicts."""
    try:
        return int(df.duplicated().sum())
    except TypeError:
        comparable = df.copy()
        for col in comparable.columns:
            if comparable[col].map(lambda v: isinstance(v, (list, dict))).any():
                comparable[col] = comparable[col].map(
                    lambda v: json.dumps(v, sort_keys=True, default=str)
                    if isinstance(v, (list, dict))
                    else v
                )
        return int(comparable.duplicated().sum())


def _run_join(ctx: RunContext, args: dict) -> dict:
    sources = list(args.get("sources") or [])
    join_key = args.get("join_key")
    output_name = str(args.get("output_name") or "joined_data")
    frames = [ctx.datasets[s] for s in sources if s in ctx.datasets]
    if not frames:
        ctx.datasets[output_name] = pd.DataFrame()
        return {"status": "empty", "output_name": output_name, "rows": 0}
    out = frames[0]
    for frame in frames[1:]:
        if join_key and join_key in out.columns and join_key in frame.columns:
            out = out.merge(frame, on=join_key, how=args.get("how", "inner"))
        else:
            out = pd.concat([out, frame], ignore_index=True, sort=False)
    ctx.datasets[output_name] = out
    return {"status": "ok", "output_name": output_name, "rows": int(len(out)), "columns": list(map(str, out.columns))}


def _run_transform(ctx: RunContext, args: dict) -> dict:
    input_name = args.get("input_name")
    df = ctx.datasets.get(str(input_name)) if input_name else _first_dataset(ctx)[1]
    output_name = str(args.get("output_name") or input_name or "transformed_data")
    if df is None:
        ctx.datasets[output_name] = pd.DataFrame()
        return {"status": "empty", "output_name": output_name, "rows": 0}
    out = df.copy()
    column = args.get("column") or args.get("target_column") or "price"
    factor = args.get("factor")
    if factor is None and isinstance(args.get("operation"), str):
        match = re.search(r"\*\s*([0-9.]+)", args["operation"])
        factor = float(match.group(1)) if match else None
    if column in out.columns and factor is not None:
        out[column] = pd.to_numeric(out[column], errors="coerce") * float(factor)
    ctx.datasets[output_name] = out
    return {"status": "ok", "output_name": output_name, "rows": int(len(out)), "columns": list(map(str, out.columns))}


def _write_artifact(ctx: RunContext, args: dict, payload: Any) -> str:
    raw_path = str(args.get("output_path") or f"output/{ctx.run_id}_artifact.json")
    output_root = os.environ.get("DBSHERPA_OUTPUT_DIR")
    if output_root and not os.path.isabs(raw_path):
        raw_path = raw_path[len("output/"):] if raw_path.startswith("output/") else raw_path
        raw_path = os.path.join(output_root, raw_path)
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")
    return str(path)


def handle_tool_executor(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    action = _state(ctx, cfg.get("action_key", "last_action"), {}) or {}
    tool = _normalise_tool(str(cfg.get("tool") or action.get("tool") or "passthrough"))
    args = {**(action.get("args") if isinstance(action.get("args"), dict) else {}), **(cfg.get("args") or {})}
    lower = tool.lower()
    if lower == "aggregation":
        result = _run_aggregation(ctx, args)
    elif lower == "data_quality_checks":
        result = _run_quality(ctx, args)
    elif lower == "multi_source_join":
        result = _run_join(ctx, args)
    elif lower == "transform":
        result = _run_transform(ctx, args)
    elif lower == "emit_artifact":
        payload = args.get("payload", _jsonable(ctx.values))
        path = _write_artifact(ctx, args, payload)
        result = {"status": "ok", "artifact_path": path}
        ctx.set("artifact_path", path)
    elif lower == "passthrough":
        result = {"status": "ok", "action": action}
    else:
        from ..registry import NODE_HANDLERS

        node_type = tool.upper()
        handler = NODE_HANDLERS.get(node_type)
        if not handler:
            raise ValueError(f"Unknown tool '{tool}'")
        handler({"id": f"{node.get('id', 'tool')}_inner", "type": node_type, "label": tool, "config": args}, ctx)
        result = {"status": "ok", "node_type": node_type}
    ctx.set(_output_name(node, "last_result"), result)
    ctx.set("last_result", result)


def handle_llm_critic(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    action = _state(ctx, cfg.get("action_key", "last_action"), {}) or {}
    result = _state(ctx, cfg.get("result_key", "last_result"), {}) or {}
    issues: list[str] = []
    suggestions: list[str] = []
    if result.get("status") in {"error", "empty"}:
        issues.append(result.get("warning") or result.get("error") or "Tool did not produce a usable result.")
        suggestions.append("Choose a simpler tool configuration or verify input_name/source data.")
    elif result.get("status") == "issues":
        report = result.get("report") or {}
        issues.extend(str(i) for i in report.get("issues") or [])
        suggestions.append("Address data quality gaps or expand the collection window/source coverage.")
    if cfg.get("require_action", False) and not action.get("tool"):
        issues.append("Action did not specify a tool.")
        suggestions.append("Set action.tool to a registered tool or built-in tool name.")
    fallback = _validation(not issues, issues, suggestions, 0.95 if not issues else 0.55)
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_CRITIC"],
        ctx,
        cfg,
    )
    prompt = _render_config_text(
        _template(
            cfg,
            "Last action:\n{last_action}\n\nLast result:\n{last_result}\n\nExpected schema:\n{expected_schema}\n\nReturn only JSON with fields: valid, issues, suggestions, confidence.",
        ),
        ctx,
        cfg,
        last_action=action,
        last_result=result,
        expected_schema=cfg.get("expected_schema"),
    )
    validation = _llm_json(
        prompt,
        fallback,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.0)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1200)),
    )
    ctx.set(_output_name(node, "validation"), validation)
    ctx.set("validation", validation)


def handle_state_manager(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    retry_context = dict(_state(ctx, cfg.get("retry_context_key", "retry_context"), {}) or {})
    attempts = list(retry_context.get("previous_attempts") or [])
    attempts.append(
        {
            "action": _jsonable(ctx.get("last_action", {})),
            "result": _jsonable(ctx.get("last_result", {})),
            "validation": _jsonable(ctx.get("validation", {})),
        }
    )
    retry_context["previous_attempts"] = attempts[-int(cfg.get("history_limit", 5)):]
    retry_context["iteration"] = int(retry_context.get("iteration", 0)) + 1
    ctx.set(_output_name(node, "retry_context"), retry_context)
    ctx.set("retry_context", retry_context)


def handle_llm_evaluator(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    validation = _state(ctx, cfg.get("validation_key", "validation"), {}) or {}
    result = _state(ctx, cfg.get("result_key", "last_result"), {}) or {}
    done = bool(validation.get("valid", False)) and result.get("status") not in {"error", "empty"}
    status = {
        "done": done,
        "missing": [] if done else validation.get("suggestions", ["valid result"]),
        "confidence": float(validation.get("confidence", 0.0) or 0.0),
    }
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_EVALUATOR"],
        ctx,
        cfg,
    )
    prompt = _render_config_text(
        _template(
            cfg,
            "Goal: {goal}\nValidation:\n{validation}\nResult:\n{last_result}\n\nReturn only JSON with fields: done, missing, confidence.",
        ),
        ctx,
        cfg,
        validation=validation,
        last_result=result,
    )
    status = _llm_json(
        prompt,
        status,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.0)),
        max_output_tokens=int(cfg.get("max_output_tokens", 800)),
    )
    ctx.set(_output_name(node, "evaluator_status"), status)
    ctx.set("evaluator", status)


def handle_loop_controller(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    retry_context = _state(ctx, cfg.get("retry_context_key", "retry_context"), {}) or {}
    evaluator = _state(ctx, cfg.get("evaluator_key", "evaluator"), {}) or {}
    validation = _state(ctx, cfg.get("validation_key", "validation"), {}) or {}
    iteration = int(retry_context.get("iteration", 0))
    max_iterations = int(cfg.get("max_iterations", 5))
    confidence = float(validation.get("confidence", 0.0) or 0.0)
    continue_loop = iteration < max_iterations and not evaluator.get("done") and confidence < float(cfg.get("confidence_threshold", 0.9))
    decision = {
        "continue": continue_loop,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "stop_reason": "continue" if continue_loop else ("done" if evaluator.get("done") else "iteration_or_confidence_limit"),
    }
    ctx.set(_output_name(node, "loop_decision"), decision)
    ctx.set("loop_controller", decision)


def handle_llm_synthesizer(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    payload = {
        "goal": cfg.get("goal") or ctx.get("goal"),
        "result": _jsonable(ctx.get(cfg.get("result_key", "last_result"), {})),
        "validation": _jsonable(ctx.get("validation", {})),
        "datasets": {name: _jsonable(df) for name, df in ctx.datasets.items()},
    }
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_SYNTHESIZER"],
        ctx,
        cfg,
    )
    prompt = _render_config_text(
        _template(
            cfg,
            "Synthesize a concise final output from this payload:\n{payload}\n\nReturn JSON with useful summary fields.",
        ),
        ctx,
        cfg,
        payload=payload,
    )
    final_output = cfg.get("final_output") or _llm_json(
        prompt,
        payload,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.2)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1600)),
    )
    if cfg.get("output_path"):
        path = _write_artifact(ctx, cfg, final_output)
        ctx.set("artifact_path", path)
        if not ctx.report_path:
            ctx.report_path = path
    ctx.set(_output_name(node, "final_output"), final_output)
    ctx.set("final_output", final_output)


def handle_llm_contextualizer(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    query = cfg.get("query") or ctx.get("query") or ctx.alert_payload.get("query") or ""
    docs = cfg.get("retrieved_docs") or ctx.get(cfg.get("docs_key", "retrieved_docs"), [])
    fallback = {"query": query, "retrieved_docs": docs, "context": cfg.get("context") or {}, "text": f"{query}\n\n{json.dumps(docs, default=str)}"}
    system_prompt = _render_config_text(
        cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPTS["LLM_CONTEXTUALIZER"],
        ctx,
        cfg,
    )
    prompt = _render_config_text(
        _template(
            cfg,
            "Query:\n{query}\n\nRetrieved docs:\n{retrieved_docs}\n\nReturn JSON with enriched_context and key facts.",
        ),
        ctx,
        cfg,
        query=query,
        retrieved_docs=docs,
    )
    enriched = _llm_json(
        prompt,
        fallback,
        use_llm=_use_llm(cfg),
        system_prompt=system_prompt,
        model=cfg.get("model"),
        temperature=float(cfg.get("temperature", 0.0)),
        max_output_tokens=int(cfg.get("max_output_tokens", 1200)),
    )
    ctx.set(_output_name(node, "enriched_context"), enriched)
    ctx.set("enriched_context", enriched)


def handle_guardrail(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    action = _state(ctx, cfg.get("action_key", "last_action"), {}) or {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    rules = cfg.get("rules") or ["no_sensitive_data", "no_full_scan"]
    issues: list[str] = []
    pii_fields = set(cfg.get("pii_fields") or ["ssn", "email", "phone", "customer_name", "customer_id"])
    group_by = args.get("group_by")
    if "no_sensitive_data" in rules and group_by in pii_fields:
        issues.append(f"group_by '{group_by}' may expose sensitive data.")
    if "no_full_scan" in rules and not args.get("limit") and not args.get("time_filter") and cfg.get("require_bounded_query", False):
        issues.append("Action is unbounded; add limit or time_filter.")
    result = {"valid": not issues, "issues": issues, "rules": rules}
    ctx.set(_output_name(node, "guardrail_result"), result)
    ctx.set("guardrail_result", result)
    if issues and cfg.get("block_on_violation", True):
        raise ValueError("; ".join(issues))


def handle_plan_validator(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    plan = _state(ctx, cfg.get("plan_key", "plan"), {}) or {}
    steps = plan.get("steps") if isinstance(plan, dict) else []
    issues: list[str] = []
    step_ids = {s.get("step_id") for s in steps if isinstance(s, dict)}
    for step in steps:
        if not isinstance(step, dict):
            issues.append("Plan step must be an object.")
            continue
        if not _tool_exists(str(step.get("tool") or "")):
            issues.append(f"Step '{step.get('step_id')}' references unknown tool '{step.get('tool')}'.")
        for dep in step.get("dependencies") or []:
            if dep not in step_ids:
                issues.append(f"Step '{step.get('step_id')}' depends on unknown step '{dep}'.")
    validation = {"valid": not issues, "issues": issues, "step_count": len(steps)}
    ctx.set(_output_name(node, "plan_validation"), validation)
    ctx.set("plan_validation", validation)
    if issues and cfg.get("block_on_invalid"):
        raise ValueError("; ".join(issues))


def handle_aggregator_node(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    output_name = _output_name(node, "aggregated_state")
    keys = cfg.get("value_keys") or ["last_result", "validation", "evaluator", "artifact_path"]
    aggregate = {key: _jsonable(ctx.get(key)) for key in keys if key in ctx.values}
    dataset_names = cfg.get("datasets") or []
    if dataset_names:
        frames = [ctx.datasets[name] for name in dataset_names if name in ctx.datasets]
        if frames:
            ctx.datasets[output_name] = pd.concat(frames, ignore_index=True, sort=False)
    ctx.set(output_name, aggregate)


def handle_data_reducer(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    input_name = cfg.get("input_name")
    name, df = (str(input_name), ctx.datasets.get(str(input_name))) if input_name else _first_dataset(ctx)
    output_name = _output_name(node, "reduced_data")
    max_rows = int(cfg.get("max_rows", 100))
    if df is None:
        reduced = pd.DataFrame()
    else:
        reduced = df.head(max_rows).copy()
    ctx.datasets[output_name] = reduced
    rows = int(len(reduced))
    ctx.set(f"{output_name}_summary", {"source": name, "rows": rows, "columns": list(map(str, reduced.columns))})
    if name:
        ctx.set(f"{name}_count", rows)
        if name == "market_data":
            ctx.set("market_data_tick_count", rows)


def handle_error_handler(node: dict, ctx: RunContext) -> None:
    cfg = _cfg(node)
    error = cfg.get("error") or ctx.get("last_error") or {}
    validation = ctx.get("validation") or {}
    issues = validation.get("issues") or validation.get("errors") or []
    text = " ".join(map(str, issues or [error])).lower()
    if "syntax" in text or "parse" in text:
        error_type = "syntax"
    elif "missing" in text or "not present" in text:
        error_type = "data_missing"
    elif text:
        error_type = "semantic"
    else:
        error_type = "none"
    strategy = "retry" if error_type in {"syntax", "semantic"} else ("fallback" if error_type == "data_missing" else "continue")
    recovery = {"error_type": error_type, "strategy": strategy, "issues": issues}
    ctx.set(_output_name(node, "recovery_strategy"), recovery)
    ctx.set("recovery_strategy", recovery)


def _agent_spec(
    type_id: str,
    handler: Callable[[dict, RunContext], None],
    description: str,
    *,
    icon: str,
    order: int,
    params: dict[str, str] | None = None,
    outputs: dict[str, str] | None = None,
    inputs: dict[str, str] | None = None,
) -> NodeSpec:
    spec = _spec(
        type_id,
        handler,
        description,
        color="#7C3AED",
        icon=icon,
        config_tags=("output_name",),
        inputs=inputs or {"state": "object from RunContext"},
        outputs=outputs or {"output": "object stored in ctx.values"},
        config_schema=params or {"output_name": "string — ctx.values key to write"},
    )
    return replace(
        spec,
        ui={
            **spec.ui,
            "palette_group": "agent",
            "palette_section_label": "Agent Layer",
            "palette_section_color": "#7C3AED",
            "palette_section_order": 25,
            "palette_order": order,
            "display_name": type_id.replace("_", ".").lower() if type_id.startswith("LLM_") else type_id.replace("_", " ").title(),
        },
    )


_COMMON_LLM_PARAMS = {
    "use_llm": "boolean — call configured LLM when true; otherwise use deterministic fallback",
    "system_prompt": "string — system instruction for this LLM role; rendered with prompt_context and state placeholders",
    "prompt_template": "string — user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
    "prompt_context": "object — optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
    "model": "string — optional model override",
    "temperature": "number — model temperature",
    "max_output_tokens": "integer — output token cap",
    "output_name": "string — ctx.values key to write",
}


NODE_SPECS: tuple[NodeSpec, ...] = (
    _agent_spec("LLM_PLANNER", handle_llm_planner, "llm.planner — create a step plan from goal and context", icon="NotebookText", order=10, params={**_COMMON_LLM_PARAMS, "goal": "string — user goal", "plan": "array — optional deterministic plan override"}),
    _agent_spec("PLAN_VALIDATOR", handle_plan_validator, "Validate generated plan structure, dependencies, and tool names", icon="Gavel", order=20),
    _agent_spec("LLM_ACTION", handle_llm_action, "llm.action — choose the next tool call using critic feedback and retry context", icon="Crosshair", order=30, params={**_COMMON_LLM_PARAMS, "plan_key": "string — ctx.values key for plan", "validation_key": "string — ctx.values key for critic feedback", "retry_context_key": "string — ctx.values key for retry history", "args": "object — static tool args merged into action", "tool": "string — fallback tool"}),
    _agent_spec("ACTION_VALIDATOR", handle_action_validator, "Validate LLM-selected tool and args before execution", icon="Gavel", order=40),
    _agent_spec("GUARDRAIL", handle_guardrail, "Apply deterministic safety checks to action/result state", icon="Siren", order=50),
    _agent_spec("TOOL_EXECUTOR", handle_tool_executor, "Bridge an LLM action into deterministic built-in or registered node execution", icon="SlidersHorizontal", order=60, params={"action_key": "string — ctx.values action key", "tool": "string — optional static tool override", "args": "object — static args merged into action args", "output_name": "string — defaults to last_result"}),
    _agent_spec("LLM_CRITIC", handle_llm_critic, "llm.critic — validate the latest action result and emit actionable feedback", icon="Gavel", order=70, params={**_COMMON_LLM_PARAMS, "action_key": "string — ctx.values key for last action", "result_key": "string — ctx.values key for last result", "expected_schema": "object — expected result/schema hints"}),
    _agent_spec("STATE_MANAGER", handle_state_manager, "Track retry history and iteration state", icon="FileStack", order=80),
    _agent_spec("LLM_EVALUATOR", handle_llm_evaluator, "llm.evaluator — decide whether the current workflow goal is satisfied", icon="Crosshair", order=90, params={**_COMMON_LLM_PARAMS, "validation_key": "string — ctx.values key for critic validation", "result_key": "string — ctx.values key for result to evaluate"}),
    _agent_spec("LOOP_CONTROLLER", handle_loop_controller, "Compute retry-loop continuation from iteration, done, and confidence state", icon="Repeat", order=100),
    _agent_spec("LLM_SYNTHESIZER", handle_llm_synthesizer, "llm.synthesizer — produce final output and optional JSON/text artifact", icon="NotebookText", order=110, params={**_COMMON_LLM_PARAMS, "output_path": "string — optional artifact path", "result_key": "string — ctx.values key to summarize", "final_output": "object — optional deterministic final output override"}),
    _agent_spec("LLM_CONTEXTUALIZER", handle_llm_contextualizer, "llm.contextualizer — combine query and retrieved docs into enriched context", icon="MessageSquareText", order=120, params={**_COMMON_LLM_PARAMS, "query": "string — query text", "retrieved_docs": "array — documents to contextualize", "docs_key": "string — ctx.values key containing retrieved docs"}),
    _agent_spec("AGGREGATOR_NODE", handle_aggregator_node, "Merge selected values and optionally concatenate datasets", icon="FileStack", order=130),
    _agent_spec("DATA_REDUCER", handle_data_reducer, "Reduce a dataset to a bounded preview and summary for downstream LLM nodes", icon="ListFilter", order=140, outputs={"reduced_data": "DataFrame stored in ctx.datasets[output_name]"}),
    _agent_spec("ERROR_HANDLER", handle_error_handler, "Classify failures and select retry, fallback, abort, or continue strategy", icon="Gavel", order=150),
)
