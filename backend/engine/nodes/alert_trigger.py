from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType

STANDARD_FIELDS = ("trader_id", "book", "alert_date", "currency_pair", "alert_id", "entity", "desk")


def handle_alert_trigger(node: dict, ctx: RunContext) -> None:
    """Bind alert payload fields into run context."""
    cfg = node.get("config", {})
    declared_fields: dict = cfg.get("alert_fields", {})

    # Bind declared fields first
    for field_name in declared_fields:
        value = ctx.alert_payload.get(field_name)
        if value is not None:
            ctx.set(field_name, value)

    # Always bind standard fields if present in payload
    for key in STANDARD_FIELDS:
        if key not in declared_fields:
            val = ctx.alert_payload.get(key)
            if val is not None:
                ctx.set(key, val)


NODE_SPEC: NodeSpec = _spec(
    "ALERT_TRIGGER",
    handle_alert_trigger,
    "Entry point — binds alert payload to context",
    color="#7C3AED",
    icon="Siren",
    input_ports=(
        PortSpec(
            name="alert_payload",
            type=PortType.OBJECT,
            description="JSON object passed at workflow invocation time.",
        ),
    ),
    output_ports=(
        PortSpec(
            name="context_keys",
            type=PortType.OBJECT,
            description=(
                "One context key per declared alert_field, e.g. trader_id, book, "
                "alert_date, currency_pair, alert_id."
            ),
        ),
    ),
    params=(
        ParamSpec(
            name="alert_fields",
            type=ParamType.OBJECT,
            description=(
                "Map of field_name → type (string|date|number). Binds standard fields"
                " trader_id, book, alert_date, currency_pair, alert_id, entity, desk."
            ),
            default={},
            required=False,
        ),
    ),
    constraints=(
        "Must be the first node (id=n01).",
        "No dataset inputs or outputs.",
    ),
)
