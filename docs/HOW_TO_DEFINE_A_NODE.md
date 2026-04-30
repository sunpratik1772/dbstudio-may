# How To Define A Node

> The rule: a node is normally defined by one YAML NodeSpec plus one Python handler.
> The UI, Copilot contracts, validator, generated artifacts, and node docs all
> read from that NodeSpec. Do not add frontend constants by hand.

## Mental Model

A node has two halves:

- `backend/engine/nodes/<node_name>.yaml` describes the public contract: type id, description, UI metadata, ports, params, constraints, and semantics.
- `backend/engine/nodes/<node_name>.py` implements the handler and exports `NODE_SPEC = _spec_from_yaml(...)`.

`backend/engine/registry.py` auto-discovers every module under `backend/engine/nodes/` that exports `NODE_SPEC`, or a grouped `NODE_SPECS` tuple for tightly coupled internal node families. There is no central node list to edit.

## Which Contract Are We Talking About?

This repo uses the word "contract" in two related ways. Keep this distinction clear:

| Name | Where it lives | Who uses it | Purpose |
| --- | --- | --- | --- |
| **Canonical node contract** | The YAML NodeSpec (`input_ports`, `output_ports`, `params`, `constraints`, `semantics`) plus the Python handler | Validator, runner, UI manifest, Copilot prompt builder, generated docs | The real source of truth. Edit this when node behavior changes. |
| **Derived contract dict** | `NodeSpec.contract`, live `/contracts`, and generated `backend/contracts/node_contracts.json` | Copilot prompt text, older API consumers, generated fallback docs | A serialisable view built from the canonical NodeSpec. Do not edit this by hand. |

So when someone says "node contract used for creation and validation", they mean:

- **Creation/UI/Copilot:** `GET /node-manifest` and `contracts_document()` are built from the live `NODE_SPEC`.
- **Validation:** `engine.validator.validate_dag()` reads the live `NodeSpec.params`, ports, hard rules, and data-source metadata.
- **Runtime validation:** `engine.dag_runner` checks declared input/output ports before and after handlers run.

The generated file `backend/contracts/node_contracts.json` is not the canonical source. It is a checked-in artifact for compatibility and offline/fallback use.

## Minimal Files

Create:

```text
backend/engine/nodes/my_node.yaml
backend/engine/nodes/my_node.py
backend/tests/test_my_node.py
```

Use lowercase snake case for filenames and uppercase snake case for `type_id`.

## Grouped Node Specs

Prefer one YAML-backed `NODE_SPEC` per node. Use a grouped `NODE_SPECS` tuple only when all of these are true:

- The nodes are a cohesive internal family with shared helpers and shared params.
- Splitting them would create more duplicated boilerplate than clarity.
- Each generated `NodeSpec` still declares complete params, ports, UI metadata, and constraints.
- Tests cover every exported type id and handler behavior.

Current example: `backend/engine/nodes/agent_layer.py` groups the LLM/helper primitives because they share prompt rendering, state access, and fallback execution utilities. Ordinary data, transform, report, and collector nodes should stay YAML-backed.

## NodeSpec YAML

Use this shape:

```yaml
type_id: MY_NODE
description: "Short action-oriented description."

ui:
  color: "#2563EB"
  icon: Box
  config_tags: [input_name, output_name]
  display_name: My Node
  palette:
    section:
      id: transform
      label: Transform
      order: 20
      color: "#A78BFA"
    node_order: 50

input_ports:
  - name: dataset
    type: dataframe
    description: "Input rows."
    required_columns: [trader_id]
    source_config_key: input_name

output_ports:
  - name: rows
    type: dataframe
    store_at: "ctx.datasets[{output_name}]"
    description: "Transformed rows."

params:
  - name: input_name
    type: input_ref
    description: "Upstream dataset name."
    required: true
  - name: output_name
    type: string
    description: "Dataset name written to ctx.datasets."
    default: my_rows
    required: true

semantics:
  requires: [trader]

constraints:
  - "Does not mutate the input DataFrame in place."
```

Important fields:

- `ui.palette.section` controls the left palette grouping. The frontend reads this from `/node-manifest`.
- `params` drives the config inspector widgets. Use `enum`, `input_ref`, `string_list`, `object`, `array`, `code`, etc.
- `input_ports.required_columns` is enforced at runtime before the handler runs.
- `output_ports.store_at` lets the runner verify the handler produced the declared output.
- `constraints` are prompt/contract material for Copilot and humans.

## Handler Python

Use this pattern:

```python
from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def handle_my_node(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config") or {}
    input_name = cfg["input_name"]
    output_name = cfg.get("output_name", "my_rows")

    df = ctx.datasets[input_name]
    out = df.copy()
    out["_example"] = True

    ctx.datasets[output_name] = out
    ctx.set(f"{output_name}_count", len(out))


NODE_SPEC: NodeSpec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_my_node)
```

Handler rules:

- Read config from `node["config"]`.
- Read data from `ctx.datasets`, values from `ctx.values` / `ctx.get(...)`.
- Write declared dataframe outputs to `ctx.datasets[output_name]`.
- Write scalar helper values to `ctx.set(...)`.
- Prefer `df.copy()` before modifying frames.
- Keep source-specific reusable helpers small and local.

## Data Source Backed Nodes

If the node is a generic collector whose schema changes by source, use the Solr collector pattern in `execution_data_collector.py`:

- Declare source metadata in `backend/data_sources/metadata/<id>.yaml`.
- Load `get_registry().get("<id>")` in the node module.
- Replace the `source` param enum from `DataSource.sources`.
- Populate `contract["output_columns_by_source"]` from `source_schemas`.

That keeps the UI dropdown, validator column knowledge, Copilot prompt, and runtime output checks aligned with YAML.

## Generated Artifacts

After adding or renaming a node, run:

```bash
uv run python backend/scripts/gen_artifacts.py
```

This updates:

- `backend/engine/node_type_ids.py`
- `backend/contracts/node_contracts.json`
- `frontend/src/nodes/generated.ts`
- `node_detail.md`

The frontend normally refreshes live from `GET /node-manifest`; `generated.ts` is the cold-start fallback.

## Tests

At minimum add:

- A handler test that calls the handler with a `RunContext`.
- A validator test if the node adds hard rules, required columns, or config semantics.
- A golden workflow test if the node is part of a shipped scenario.

Run:

```bash
uv run pytest backend/tests -q
npm --prefix frontend run build
```

## Checklist

- YAML has `type_id`, `description`, `ui.palette`, ports, params, constraints.
- Python exports `NODE_SPEC`, or narrowly scoped `NODE_SPECS` for a cohesive internal family.
- Handler writes exactly the outputs the YAML declares.
- No frontend files were hand-edited except generated artifacts.
- `node_detail.md` includes the new node after artifact generation.
- Backend tests and frontend build pass.
