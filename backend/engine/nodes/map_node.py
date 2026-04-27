"""
MAP — control-flow primitive. Runs a nested sub-workflow once per key.

Pattern:
    GROUP_BY(orders, column=book, prefix=orders_by_book)
       → MAP(keys_key=orders_keys, dataset_prefix=orders_by_book,
             iteration_dataset_alias=orders,
             sub_workflow={...signal + summary per book...})

Each iteration runs against a **child RunContext** forked from the
parent. The child shares the parent's datasets dict (so the
sub-workflow can read upstream collector outputs) but owns its own
values dict (so iteration-local values don't pollute sibling runs).
After each iteration we harvest the declared collect_values /
collect_datasets back into the parent aggregate.

Only MAP, IF, SUB_WORKFLOW are allowed as control-flow primitives —
keep the vocabulary bounded so an engineer reading a DAG can predict
its execution shape without reading handler code.
"""
from __future__ import annotations

import copy
from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _child_ctx(parent: RunContext) -> RunContext:
    """Fork a child ctx. Datasets are shared by reference (read-mostly; MAP may
    attach per-iteration aliases and collected outputs to the parent, not
    in-place DataFrame writes). ``values`` are deep-copied so iteration-local
    scalars do not pollute siblings. ``sections`` start empty so nested
    SECTION_SUMMARY / LLM text cannot bleed across keys."""
    child = RunContext(alert_payload=parent.alert_payload)
    child.datasets = dict(parent.datasets)  # shallow — share df references
    child.values = copy.deepcopy(parent.values)
    child.sections = {}
    child.executive_summary = ""
    child.report_path = ""
    child.run_id = parent.run_id  # same run, correlated logs
    return child


def handle_map(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    keys_key: str = cfg.get("keys_key", "")
    iter_ctx_key: str = cfg.get("iteration_ctx_key", "")
    dataset_prefix: str = cfg.get("dataset_prefix", "") or ""
    iter_dataset_alias: str = cfg.get("iteration_dataset_alias", "") or ""
    sub_workflow = cfg.get("sub_workflow") or {}
    collect_values: list[str] = list(cfg.get("collect_values") or [])
    collect_datasets: list[str] = list(cfg.get("collect_datasets") or [])
    output_name: str = cfg.get("output_name", "map_results") or "map_results"

    if not keys_key or not iter_ctx_key or not sub_workflow:
        raise ValueError("MAP requires keys_key, iteration_ctx_key, and sub_workflow")

    keys_dict = ctx.get(keys_key)
    if not isinstance(keys_dict, dict) or "values" not in keys_dict:
        raise ValueError(
            f"MAP keys_key='{keys_key}' must reference a {{'values': [...]}} object"
        )
    keys = list(keys_dict.get("values") or [])

    sub_nodes = sub_workflow.get("nodes") or []
    sub_edges = sub_workflow.get("edges") or []
    if not sub_nodes:
        raise ValueError("MAP sub_workflow has no nodes")

    # Lazy import to avoid circular dependency at module load time.
    from ..dag_runner import execute_nodes

    results: dict = {}
    for key in keys:
        child = _child_ctx(ctx)
        child.set(iter_ctx_key, key)

        # Alias the grouped dataset into a stable name so sub-workflow
        # nodes can reference it by iteration_dataset_alias rather than
        # knowing the prefix scheme.
        if dataset_prefix and iter_dataset_alias:
            src_name = f"{dataset_prefix}_{key}"
            if src_name in child.datasets:
                child.datasets[iter_dataset_alias] = child.datasets[src_name]

        execute_nodes(sub_nodes, sub_edges, child)

        per_key: dict = {}
        for vk in collect_values:
            if vk in child.values:
                per_key[vk] = child.values[vk]
        for dk in collect_datasets:
            if dk in child.datasets:
                df = child.datasets[dk]
                per_key[dk] = df
                ctx.datasets[f"{output_name}_{key}_{dk}"] = df

        # Always record that we ran this key, even with no collections.
        results[key] = per_key

    ctx.set(output_name, {"results": results})


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_map)
