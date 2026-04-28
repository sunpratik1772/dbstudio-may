# How To Build A Workflow From The Backend

> The rule: author workflows as YAML when humans will read or edit them.
> The backend converts YAML into the same JSON-compatible DAG dict before
> validation and execution. Treat validation errors as contract failures,
> not warnings to ignore.

## Workflow Shape

Use this top-level shape. YAML is preferred for authored workflow files:

```yaml
schema_version: "1.0"
workflow_id: my_workflow_001
name: My Workflow
version: "0.1.0"
description: What the workflow detects.
nodes: []
edges: []
```

Node shape:

```yaml
id: n01
type: ALERT_TRIGGER
label: Alert
config: {}
```

Edge shape:

```yaml
from: n01
to: n02
```

Do not use React Flow `source` / `target` in persisted workflows.

## Node Ordering

Conventions:

- `n01` should be `ALERT_TRIGGER`.
- Final node should usually be `REPORT_OUTPUT`.
- Use two-digit sequential ids: `n01`, `n02`, `n03`.
- Keep edges acyclic. In normal workflows, edges point from lower ids to higher ids.

## Start From Existing Workflows

Good references:

- `backend/workflows/fx_fro_v2_workflow.json`
- `backend/workflows/fisl_workflow.json`
- `backend/workflows/fi_wash_workflow.json`

Existing `.json` workflows still load. New hand-authored workflows should use
`.yaml` or `.yml`.

Templates used by Copilot live under:

```text
backend/templates/
```

Templates wrap a full workflow skeleton with `matches` and `parameters` metadata.

## Common Backend Workflow Pattern

Typical chassis:

```text
ALERT_TRIGGER
  -> TIME_WINDOW
  -> collectors
  -> transforms / grouping / MAP
  -> SIGNAL_CALCULATOR
  -> DATA_HIGHLIGHTER
  -> DECISION_RULE
  -> SECTION_SUMMARY / CONSOLIDATED_SUMMARY
  -> REPORT_OUTPUT
```

Use `EXECUTION_DATA_COLLECTOR` for Solr:

```yaml
id: n03
type: EXECUTION_DATA_COLLECTOR
label: Collect Orders
config:
  source: hs_client_order
  query_template: "trader_id:{context.trader_id}"
  output_name: orders
  window_key: window
```

For executions:

```yaml
id: n04
type: EXECUTION_DATA_COLLECTOR
label: Collect Executions
config:
  source: hs_execution
  query_template: "trader_id:{context.trader_id} AND trade_version:1"
  output_name: executions
  window_key: window
```

`hs_execution` queries must include `trade_version:1`; this is a hard rule.

## Validation

Validate from Python:

```bash
uv run python - <<'PY'
from engine.validator import validate_dag
from engine.workflow_format import workflow_from_yaml

with open("backend/workflows/my_workflow.yaml") as f:
    dag = workflow_from_yaml(f.read())

result = validate_dag(dag)
print(result.to_json())
raise SystemExit(0 if result.valid else 1)
PY
```

Validate through HTTP:

```bash
curl -X POST http://localhost:8000/validate \
  -H 'Content-Type: application/json' \
  -d @<(uv run python - <<'PY'
import json
from pathlib import Path
from engine.workflow_format import workflow_from_yaml

dag = workflow_from_yaml(Path("backend/workflows/my_workflow.yaml").read_text())
print(json.dumps({"dag": dag}))
PY
)
```

The endpoint always returns HTTP 200 with `{valid, errors, warnings, summary}`. `POST /run` returns HTTP 422 for invalid workflows.

## YAML / JSON Conversion

Use the shared converter when you need to cross the human/runtime boundary:

```python
from pathlib import Path

from engine.workflow_format import workflow_from_yaml, workflow_to_yaml

dag = workflow_from_yaml(Path("backend/workflows/my_workflow.yaml").read_text())
yaml_text = workflow_to_yaml(dag)
```

HTTP helpers exist for the UI and scripts:

```bash
curl -X POST http://localhost:8000/workflow-format/yaml-to-json \
  -H 'Content-Type: application/json' \
  -d '{"content":"schema_version: \"1.0\"\nworkflow_id: demo\nname: Demo\nversion: \"0.1.0\"\nnodes: []\nedges: []\n"}'
```

## Run

Run through HTTP:

```bash
curl -X POST http://localhost:8000/run \
  -H 'Content-Type: application/json' \
  -d @<(python3 - <<'PY'
import json
from pathlib import Path
from engine.workflow_format import workflow_from_yaml

dag = workflow_from_yaml(Path("backend/workflows/my_workflow.yaml").read_text())
print(json.dumps({
    "dag": dag,
    "alert_payload": {
        "trader_id": "T001",
        "book": "FX-SPOT",
        "currency_pair": "EUR/USD",
        "alert_date": "2024-01-15",
        "alert_id": "DEMO-0001",
        "event_time": "2024-01-15 09:00"
    }
}))
PY
)
```

Run the canned demo:

```bash
curl -X POST http://localhost:8000/run/demo \
  -H 'Content-Type: application/json' \
  -d '{}' \
  --output demo_report.xlsx
```

## Save And Draft APIs

Saved workflows:

- `GET /workflows`
- `GET /workflows/{filename}`
- `POST /workflows/{filename}`
- `DELETE /workflows/{filename}`

Draft workflows:

- `GET /drafts`
- `GET /drafts/{filename}`
- `POST /drafts/{filename}`
- `DELETE /drafts/{filename}`
- `POST /drafts/{filename}/promote`

Generated Copilot workflows auto-save as drafts.

Saved and draft APIs accept `.yaml`, `.yml`, and `.json` filenames. The
response body is always the runtime JSON-compatible workflow dict.

## Regenerate Docs And Fallbacks

If the workflow change follows a node/datasource change, run:

```bash
uv run python backend/scripts/gen_artifacts.py
```

If the workflow is just a YAML wiring change, no artifact generation is required.

## Tests

Add a golden test when the workflow is intended to be shipped:

```python
def test_my_workflow_validates() -> None:
    from pathlib import Path
    from engine.workflow_format import workflow_from_yaml

    dag = workflow_from_yaml(Path("backend/workflows/my_workflow.yaml").read_text())
    result = validate_dag(dag)
    assert result.valid, [e.message for e in result.errors]
```

For end-to-end coverage, call `run_workflow(...)` or the FastAPI route with `TestClient`.

## Checklist

- `schema_version` is `1.0`.
- Node ids are stable and sequential.
- Edges use `{from, to}` and are acyclic.
- Every `input_name` matches an upstream `output_name`.
- Solr execution/trade reads pin `trade_version:1` when required.
- `validate_dag` is clean.
- Golden test added for shipped workflows.
