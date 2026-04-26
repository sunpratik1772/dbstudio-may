# Onboarding a New Surveillance Scenario

> **Audience:** a backend engineer who has never opened this repo before and needs to
> ship a new dataset + signal + highlighter + runnable workflow in under a day.
>
> **Promise:** follow this doc top-to-bottom, you will finish with a working
> `POST /run` that produces an Excel report for your scenario — without ever
> touching the frontend or editing a central registry.

---

## 1 — What you're going to build

We'll walk through shipping a new scenario called **Insider Trading on FI Bonds**.
By the end you will have:

- A new **dataset** (`positions`) declared in one YAML file.
- A new **collector** node (`POSITIONS_COLLECTOR`) declared in one Python file.
- A new built-in **signal** type (`POSITION_SPIKE`) added to the existing
  `SIGNAL_CALCULATOR`.
- A new **highlighter rule** re-using the existing `DATA_HIGHLIGHTER`.
- A new **skill file** so the Copilot can author workflows for this scenario.
- A new **workflow JSON** wiring it all up.
- A unit test + an integration smoke test.

Last line you'll run:

```bash
curl -X POST http://localhost:8000/run \
  -H 'Content-Type: application/json' \
  -d @backend/workflows/fi_insider_workflow.json \
  --output insider_report.xlsx
```

…and the report opens in Excel.

---

## 2 — Prereqs

| Tool      | Version | Check                                      |
|-----------|---------|--------------------------------------------|
| Python    | 3.11+   | `python3 --version`                        |
| Node.js   | 20+     | `node --version`                           |
| Gemini key| any     | get a key from `https://ai.google.dev`     |

Copy the env template and paste your key:

```bash
cp backend/.env.example backend/.env
# then edit backend/.env and paste: GEMINI_API_KEY=AIza...
```

Start the stack once to confirm it runs:

```bash
./start.sh
# → Backend: http://localhost:8000
# → Frontend: http://localhost:5173
```

---

## 3 — The "one place per concern" principle

dbSherpa was built so that each new scenario touches exactly one file per
concern. Memorise this table — it is the whole mental model:

| I want to…                              | Edit only this file                                              |
|-----------------------------------------|------------------------------------------------------------------|
| Declare a dataset's schema              | `backend/data_sources/metadata/<id>.yaml`                        |
| Add a node type                         | `backend/engine/nodes/<name>.py` (handler + `NODE_SPEC`)         |
| Add a built-in signal                   | `backend/engine/nodes/signal_calculator.py` (new branch)         |
| Add a highlighter rule                  | Use existing `DATA_HIGHLIGHTER` config — no Python edit needed   |
| Teach the Copilot a new scenario        | `backend/skills/skills-<scenario>.md`                            |
| Ship a ready-to-run workflow            | `backend/workflows/<name>.json`                                  |
| Test your node                          | `backend/tests/test_<node>.py`                                   |
| Rebuild contracts for frontend + copilot| `python backend/scripts/gen_artifacts.py`                        |

There is **no central list** you need to append to. The registry
auto-discovers every `NODE_SPEC` under `engine/nodes/`.

---

## 4 — Worked example: FI Insider Trading, end-to-end

### 4.1 Declare the dataset

Create `backend/data_sources/metadata/positions.yaml`:

```yaml
id: positions
description: Daily position snapshots from the position-keeping system.
sources:
  - position_keeper
columns:
  - name: position_id
    type: string
    description: Unique row identifier.
  - name: trader_id
    type: string
    semantic: trader
    description: Trader holding the position.
  - name: as_of_date
    type: datetime
    semantic: time
  - name: instrument
    type: string
    description: Bond CUSIP / ISIN.
  - name: notional
    type: number
    semantic: size
  - name: side
    type: string
    description: LONG or SHORT.
  - name: pnl_unrealized
    type: number
    description: Mark-to-market P&L.
```

That's it — the `DataSourceRegistry` picks this file up on next import.
See [BACKEND_ARCHITECTURE.md §3.9](BACKEND_ARCHITECTURE.md#39-data-source-registry)
for the full loader.

**Semantic tags matter.** Any column with a `semantic` tag (`trader`,
`size`, `price`, `time`, `notional`) is automatically:

- injected into the Copilot's system prompt so the LLM writes the
  correct physical column name instead of an alias, and
- checked by the `_validate_field_bindings()` validator, which emits
  an `UNKNOWN_COLUMN` warning when a generated workflow references a
  column that doesn't exist in the registry.

Tag generously — it directly improves the quality of Copilot-generated
workflows for your new dataset.

If your collector should participate in the field-binding check, add it to
`COLLECTOR_TYPE_TO_SOURCE_ID` in `engine/collector_source.py` and record
runtime provenance with `collector_source_ref(...)`:
```python
"POSITIONS_COLLECTOR": "positions",   # node type -> data source id
```

### 4.2 Create the collector node

Create `backend/engine/nodes/positions_collector.py`:

```python
"""
POSITIONS_COLLECTOR — reads daily position rows for a trader / date window.

Kept in the same shape as the other collectors:
  * synthetic path for dev (when no CSV is available)
  * csv path for reproducible demos (mock_csv_path config)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType, Widget


def _mock_positions(ctx: RunContext) -> pd.DataFrame:
    trader = ctx.get("trader_id", "trader_demo")
    day = ctx.get("alert_date", "2024-01-01")
    rows = [
        {
            "position_id": f"P{i:03d}",
            "trader_id": trader,
            "as_of_date": f"{day}T16:00:00Z",
            "instrument": "US912828Z948",
            "notional": 1_000_000 * (i + 1),
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "pnl_unrealized": (i - 2) * 12_500,
        }
        for i in range(6)
    ]
    return pd.DataFrame(rows)


def handle_positions_collector(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config", {}) or {}
    output_name: str = cfg.get("output_name", "positions")
    mock_csv_path: str | None = cfg.get("mock_csv_path")

    if mock_csv_path and Path(mock_csv_path).exists():
        df = pd.read_csv(mock_csv_path)
    else:
        df = _mock_positions(ctx)

    ctx.datasets[output_name] = df
    ctx.set(f"{output_name}_row_count", len(df))


NODE_SPEC: NodeSpec = _spec(
    "POSITIONS_COLLECTOR",
    handle_positions_collector,
    "Collect daily position snapshots for a trader and date range.",
    color="#0EA5E9",
    icon="PieChart",
    input_ports=(),
    output_ports=(
        PortSpec(
            name="positions",
            type=PortType.DATAFRAME,
            description="Position rows for the alert window.",
        ),
    ),
    params=(
        ParamSpec(
            "output_name",
            ParamType.STRING,
            default="positions",
            description="Key the DataFrame is stored under in ctx.datasets.",
        ),
        ParamSpec(
            "mock_csv_path",
            ParamType.STRING,
            required=False,
            description="Optional CSV fixture used by demo / reproducible runs.",
        ),
    ),
    config_tags=("output_name",),
)
```

**What you got for free:**

- The palette (frontend) will show the new node automatically after step 4.8.
- The Copilot will see it in the contracts JSON after step 4.8.
- The validator will check that `output_name` is a non-empty string and that
  any downstream `input_name` referencing `"positions"` is wired correctly —
  no rule edits needed.

### 4.3 Add the built-in signal

Open `backend/engine/nodes/signal_calculator.py` and add a new function next
to `_front_running`, `_wash_trade`, etc:

```python
def _position_spike(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Flag trader-days where aggregate notional > threshold."""
    threshold = params.get("notional_threshold", 5_000_000)

    df = df.copy()
    if "notional" in df.columns and "trader_id" in df.columns:
        total = df.groupby("trader_id")["notional"].transform("sum")
        df["_signal_flag"] = total > threshold
        df["_signal_score"] = (total / threshold).clip(0, 10).round(2)
        df["_signal_reason"] = df.apply(
            lambda r: f"Trader aggregate notional {total[r.name]:,.0f} exceeds {threshold:,}"
            if r["_signal_flag"] else "",
            axis=1,
        )
    else:
        df["_signal_flag"] = False
        df["_signal_score"] = 0.0
        df["_signal_reason"] = ""

    df["_signal_type"] = "POSITION_SPIKE"
    df["_signal_window"] = "daily"
    return df
```

Wire it into the dispatcher (same file, search for `BUILT_IN_SIGNALS`):

```python
BUILT_IN_SIGNALS = {
    "FRONT_RUNNING": _front_running,
    "WASH_TRADE": _wash_trade,
    "SPOOFING": _spoofing,
    "LAYERING": _layering,
    "POSITION_SPIKE": _position_spike,   # ← new
}
```

Done. `SIGNAL_CALCULATOR` nodes can now set `signal_type: "POSITION_SPIKE"`
and it picks up the new function.

### 4.4 Declare the highlighter rule

No Python edit. The `DATA_HIGHLIGHTER` node already supports arbitrary
pandas-eval expressions in its `rules` config. In your workflow JSON you'll
write:

```json
{
  "id": "n06",
  "type": "DATA_HIGHLIGHTER",
  "label": "Highlight position spikes",
  "config": {
    "input_name": "position_signals",
    "output_name": "position_signals_highlighted",
    "rules": [
      { "condition": "_signal_flag == True", "colour": "#FF4444", "label": "SPIKE" },
      { "condition": "pnl_unrealized < 0",   "colour": "#F59E0B", "label": "DRAWDOWN" }
    ]
  }
}
```

### 4.5 Write the scenario skill

Create `backend/skills/skills-fi-insider.md`. Use the existing
[`skills-fx-fro.md`](../backend/skills/skills-fx-fro.md) as a template.
The Copilot reads these files to decide which scenario applies to a user
prompt and to learn the column vocabulary + thresholds it should use.

Minimum sections to include:

- `# Skill: <Scenario Name>` heading.
- `## Overview` — one paragraph in plain English.
- `## Regulatory Reference` — citations (MAR, Dodd-Frank, FINRA rule, etc.).
- `## Alert Trigger Fields` — table with `| Field | Type | Description |`.
- `## Required Data Extracts` — one block per collector, listing the
  dataset id and the key fields.
- `## Signals to Create` — one block per signal, with a JSON snippet the
  Copilot can copy-paste into a node's config.
- `## Highlight Rules` — table of `| Condition | Colour | Label |`.
- `## Decision Thresholds` — ESCALATE / REVIEW / DISMISS criteria.
- `## Report Sections` — the narrative sections the report should contain.
- `## Copilot Instruction Example` — a sample user prompt for smoke-testing.

### 4.6 Author the workflow JSON

Create `backend/workflows/fi_insider_workflow.json`. Every workflow has
the same shape:

```json
{
  "schema_version": "1.0",
  "workflow_id": "fi_insider_001",
  "name": "FI Insider Trading",
  "version": "1.0",
  "description": "Detects abnormal position build-ups tied to non-public info.",
  "nodes": [
    {
      "id": "n01",
      "type": "ALERT_TRIGGER",
      "label": "Alert Trigger",
      "config": {
        "alert_fields": {
          "trader_id": "string",
          "alert_date": "date",
          "instrument": "string"
        }
      }
    },
    {
      "id": "n02",
      "type": "POSITIONS_COLLECTOR",
      "label": "Collect Positions",
      "config": { "output_name": "positions" }
    },
    {
      "id": "n03",
      "type": "SIGNAL_CALCULATOR",
      "label": "Detect Position Spikes",
      "config": {
        "mode": "configure",
        "signal_type": "POSITION_SPIKE",
        "input_name": "positions",
        "output_name": "position_signals",
        "params": { "notional_threshold": 5000000 }
      }
    },
    {
      "id": "n04",
      "type": "DATA_HIGHLIGHTER",
      "label": "Highlight",
      "config": {
        "input_name": "position_signals",
        "output_name": "position_signals_highlighted",
        "rules": [
          { "condition": "_signal_flag == True", "colour": "#FF4444", "label": "SPIKE" }
        ]
      }
    },
    {
      "id": "n05",
      "type": "DECISION_RULE",
      "label": "Disposition",
      "config": {
        "input_name": "position_signals",
        "escalate_threshold": 5,
        "review_threshold": 1,
        "output_branches": { "ESCALATE": "senior", "REVIEW": "analyst", "DISMISS": "close" }
      }
    },
    {
      "id": "n06",
      "type": "REPORT_OUTPUT",
      "label": "Report",
      "config": {
        "output_path": "output/fi_insider_{alert_id}.xlsx",
        "tabs": [
          { "name": "Positions", "dataset": "position_signals_highlighted", "include_highlights": true }
        ]
      }
    }
  ],
  "edges": [
    { "from": "n01", "to": "n02" },
    { "from": "n02", "to": "n03" },
    { "from": "n03", "to": "n04" },
    { "from": "n04", "to": "n05" },
    { "from": "n05", "to": "n06" }
  ]
}
```

### 4.7 Add tests

Create `backend/tests/test_positions_collector.py`:

```python
from engine.context import RunContext
from engine.nodes.positions_collector import handle_positions_collector


def test_collector_produces_named_dataset():
    ctx = RunContext(alert_payload={"trader_id": "t1", "alert_date": "2024-06-01"})
    ctx.set("trader_id", "t1")
    ctx.set("alert_date", "2024-06-01")

    node = {"id": "n02", "type": "POSITIONS_COLLECTOR",
            "config": {"output_name": "positions"}}
    handle_positions_collector(node, ctx)

    df = ctx.datasets["positions"]
    assert {"trader_id", "notional", "side"}.issubset(df.columns)
    assert ctx.get("positions_row_count") == len(df)


def test_signal_spike_flags_large_notional():
    import pandas as pd
    from engine.nodes.signal_calculator import _position_spike

    df = pd.DataFrame([
        {"trader_id": "t1", "notional": 10_000_000, "pnl_unrealized": 5_000},
        {"trader_id": "t1", "notional": 10_000_000, "pnl_unrealized": 2_000},
    ])
    out = _position_spike(df, {"notional_threshold": 5_000_000})
    assert out["_signal_flag"].all()
    assert (out["_signal_type"] == "POSITION_SPIKE").all()
```

Run:

```bash
cd backend && .venv/bin/pytest tests/test_positions_collector.py -v
```

Add an integration assertion to `backend/tests/test_run_demo.py` or
create `backend/tests/test_fi_insider_run.py` that POSTs the workflow to
the `/run` endpoint via FastAPI's `TestClient` and asserts on the
response headers (`X-Flag-Count`, `X-Disposition`). The pattern is
documented in
[BACKEND_ARCHITECTURE.md §Testing](BACKEND_ARCHITECTURE.md#testing-guide).

### 4.8 Regenerate contracts + frontend types

Run this every time you touch `NODE_SPEC`, add a node, or change a
ParamSpec:

```bash
cd backend && python scripts/gen_artifacts.py
```

That script writes two files:

- `backend/contracts/node_contracts.json` — the Copilot's view of every
  node (types, params, inputs/outputs).
- `frontend/src/nodes/generated.ts` — the frontend's view (palette
  entries, icon names, colors, form schemas).

Both files are **generated, checked-in artifacts**. Never hand-edit them.
Both are detected by Git as changes — commit them with your feature PR so
reviewers can see exactly what shifted.

### 4.9 Run it

```bash
./start.sh
# In another terminal:
curl -X POST http://localhost:8000/run \
  -H 'Content-Type: application/json' \
  -d @backend/workflows/fi_insider_workflow.json \
  --output insider_report.xlsx
open insider_report.xlsx     # macOS
```

You can also drive it from the UI at <http://localhost:5173> — open the
workflow via the left drawer, or ask the Copilot to build one from a
prompt (the new skill file makes it aware of the scenario).

---

## 5 — Pre-merge checklist

Before opening a PR:

- [ ] New handler is pure — no `import fastapi`, no `requests.*`.
- [ ] `NODE_SPEC` declared at the bottom of the handler file.
- [ ] `python backend/scripts/gen_artifacts.py` ran cleanly and generated
      files (``node_type_ids.py``, ``node_contracts.json``, ``generated.ts``) are committed.
- [ ] `backend/.venv/bin/pytest tests/ -v` — all green.
- [ ] `cd frontend && ./node_modules/.bin/tsc --noEmit` — no errors.
- [ ] `POST /validate` on the new workflow returns `{"valid": true, ...}`.
- [ ] If you added a scenario, there's a skills markdown file.
- [ ] If you added a dataset, there's a metadata YAML file with `semantic`
      tags on columns where applicable, and the collector records provenance
      through `engine/collector_source.py`.
- [ ] If you added a signal, there's at least one unit test for the
      signal function itself (decoupled from the node handler).

---

## 6 — FAQ

**Q. Do I ever edit `registry.py`?**
No. It auto-discovers every `NODE_SPEC` under `engine/nodes/`. Adding your
module file is the registration step.

**Q. Do I need to touch the frontend?**
No, unless you want custom UI for your node. The palette, the config
drawer, the validation surface, and the SSE run log all pick up the new
node from `generated.ts` after you regenerate artifacts.

**Q. Where does the Copilot learn about my new node?**
Three places: the `contracts/node_contracts.json` file (what types and
params exist), your scenario skill markdown (when to use it), and the
workflow JSON files checked into `backend/workflows/` (worked examples).

**Q. My dataset has different column names than the existing scenarios —
do I need to rewrite all the signal handlers?**
No. Add `semantic` tags to your columns in the YAML (`semantic: price`,
`semantic: size`, etc.). The Copilot's system prompt is automatically
rebuilt from the registry at startup, so the LLM will use your physical
column names when generating workflows for your dataset. Existing signal
handlers that reference trades or market data are unaffected — they
operate on their own collector outputs, not yours. If you need a handler
to work across multiple datasets by role, use `DataSource.semantic_map()`
to look up the physical column at runtime.

**Q. My node needs to call an external service / LLM. How?**
Import `from llm import get_default_adapter` and call `chat_turn(...)` or
`single_shot(...)`. Don't open your own Gemini client. See
[BACKEND_ARCHITECTURE.md §LLM seam](BACKEND_ARCHITECTURE.md#llm-seam-geminiadapter).

**Q. How do I propagate errors from my handler?**
Raise a standard Python exception. The DAG runner catches it, converts
it to a structured `node_error` SSE frame with the first 3 frames of
traceback, and fails the run. Don't print to stderr; don't swallow.

---

## 7 — Next steps

Once your scenario is live:

1. Ask a senior to review the generated `contracts/node_contracts.json`
   diff — that's the surface area the Copilot sees.
2. Author 2–3 Copilot test prompts for your scenario and add them as
   golden-path pytests.
3. If your scenario needs custom narrative sections, add a
   `SECTION_SUMMARY` node to the workflow with field bindings; the
   narrative prompt template is in the same node's config.

When in doubt: lean on the worked example above. Every shipped scenario
(`FX_FRO`, `FI_WASH`, `FI_LAYERING`, `FI_SPOOFING`) was built with the
exact same recipe.
