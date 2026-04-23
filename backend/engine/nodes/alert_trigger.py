from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml

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


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_alert_trigger)
