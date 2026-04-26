"""
ALERT_TRIGGER — entry node of every workflow.

Job: copy the relevant fields out of the immutable alert_payload onto
ctx.values so downstream nodes can reference `{context.trader_id}`,
`{context.event_time}`, etc., via the refs grammar.

There are two kinds of fields:
  • declared in the YAML config under `alert_fields` — explicitly
    requested by the workflow author.
  • STANDARD_FIELDS — the conventional surveillance set we always
    expose if present in the payload, so collectors and prompt
    templates can rely on them without per-workflow boilerplate.

Topology rule (validator-enforced): there is exactly one
ALERT_TRIGGER per workflow, its id is `n01`, and it has no incoming
edges.
"""
from pathlib import Path

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _standard_fields_from_spec() -> tuple[str, ...]:
    from ..registry import get_spec  # local: avoid registry↔node import cycle at startup

    raw = (get_spec("ALERT_TRIGGER").contract or {}).get("standard_alert_fields")
    if not raw:
        raise RuntimeError("ALERT_TRIGGER YAML must define extras.standard_alert_fields")
    return tuple(str(x) for x in raw)


def handle_alert_trigger(node: dict, ctx: RunContext) -> None:
    """Bind alert payload fields into run context."""
    cfg = node.get("config", {})
    declared_fields: dict = cfg.get("alert_fields", {})

    # Bind declared fields first
    for field_name in declared_fields:
        value = ctx.alert_payload.get(field_name)
        if value is not None:
            ctx.set(field_name, value)

    # Always bind standard fields (from node YAML) if present in payload
    for key in _standard_fields_from_spec():
        if key not in declared_fields:
            val = ctx.alert_payload.get(key)
            if val is not None:
                ctx.set(key, val)

    # Materialise OBJECT output port `context_keys` for runner contract checks
    std = _standard_fields_from_spec()
    ctx.set(
        "context_keys",
        {k: ctx.get(k) for k in std if ctx.get(k) is not None},
    )


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_alert_trigger)
