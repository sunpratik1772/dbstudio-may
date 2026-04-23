from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_decision_rule(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {})
    input_name: str = cfg.get("input_name", "signal_data")
    flag_count_expr: str = cfg.get("flag_count_expr", "flag_count > 0")
    escalate_threshold: int = cfg.get("escalate_threshold", 5)
    review_threshold: int = cfg.get("review_threshold", 1)
    output_branches: dict = cfg.get("output_branches", {})

    # Resolve flag_count from dataset or previously stored context value
    df = ctx.datasets.get(input_name)
    if df is not None and "_signal_flag" in df.columns:
        flag_count = int(df["_signal_flag"].sum())
    else:
        flag_count = int(ctx.get(f"{input_name}_flag_count", 0))

    # Safe eval of the expression (limited namespace)
    eval_ns = {"flag_count": flag_count, "__builtins__": {}}
    try:
        eval(flag_count_expr, eval_ns)  # noqa: S307 — expression is user-supplied config, not untrusted input
    except Exception:
        pass

    # Determine disposition
    if flag_count >= escalate_threshold:
        disposition = "ESCALATE"
    elif flag_count >= review_threshold:
        disposition = "REVIEW"
    else:
        disposition = "DISMISS"

    branch = output_branches.get(disposition, disposition)

    ctx.disposition = disposition
    ctx.output_branch = branch
    ctx.set("disposition", disposition)
    ctx.set("flag_count", flag_count)
    ctx.set("output_branch", branch)


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_decision_rule)
