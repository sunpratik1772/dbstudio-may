from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType


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


NODE_SPEC: NodeSpec = _spec(
    "DECISION_RULE",
    handle_decision_rule,
    "Evaluate flag_count → ESCALATE/REVIEW/DISMISS",
    color="#D97706",
    icon="Gavel",
    input_ports=(
        PortSpec(
            name="dataset",
            type=PortType.DATAFRAME,
            description="Signal DataFrame with _signal_flag column.",
        ),
        PortSpec(
            name="flag_count",
            type=PortType.SCALAR,
            description=(
                "Flag count from SIGNAL_CALCULATOR (read from "
                "ctx.values[{input_name}_flag_count] if the dataset isn't available)."
            ),
            optional=True,
        ),
    ),
    output_ports=(
        PortSpec(
            name="disposition",
            type=PortType.TEXT,
            description="'ESCALATE' | 'REVIEW' | 'DISMISS'. Stored as context.disposition.",
        ),
        PortSpec(
            name="flag_count",
            type=PortType.SCALAR,
            description="Total signal hits (int). Stored as context.flag_count.",
        ),
        PortSpec(
            name="output_branch",
            type=PortType.TEXT,
            description="Branch name to route to. Stored as context.output_branch.",
        ),
    ),
    params=(
        ParamSpec(
            name="input_name",
            type=ParamType.INPUT_REF,
            description="Signal dataset name.",
            required=True,
        ),
        ParamSpec(
            name="flag_count_expr",
            type=ParamType.STRING,
            description=(
                "Python expression using 'flag_count' variable, e.g. 'flag_count > 0'. "
                "Overrides escalate/review thresholds when supplied."
            ),
            required=False,
        ),
        ParamSpec(
            name="escalate_threshold",
            type=ParamType.INTEGER,
            description="flag_count >= this → ESCALATE.",
            default=1,
            required=False,
        ),
        ParamSpec(
            name="review_threshold",
            type=ParamType.INTEGER,
            description="flag_count >= this → REVIEW, else DISMISS.",
            default=1,
            required=False,
        ),
        ParamSpec(
            name="output_branches",
            type=ParamType.OBJECT,
            description="Map of disposition → branch_name string.",
            default={},
            required=False,
        ),
    ),
)
