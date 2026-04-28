# Backend Architecture

> **Audience:** backend engineers who will maintain and extend dbSherpa.
>
> **Purpose:** the single reference for "where does X live and why?".
> Read this once end-to-end, then keep it open as a lookup. This
> document supersedes the old root-level `ARCHITECTURE.md`.

---

## 0 — Junior engineer reading order (½ day to productive)

If you have 2–3 years of experience and have never opened this repo, read
files in this order. Each opens with a docstring that explains *why* it
exists and how it fits in — that's where most of the architecture is
encoded, not in this document.

1. **`backend/engine/context.py`** (30 lines) — the one shared object
   every node mutates. Until you understand what's on it, nothing else
   makes sense.
2. **`backend/engine/dag_runner.py`** — start at `run_workflow` (bottom
   of file) and follow the loop into `execute_nodes`. ~30 minutes.
3. **`backend/engine/registry.py` + `node_spec.py`** — how nodes plug
   in. After this you can add a new node without editing a central
   list.
4. **`backend/engine/nodes/order_collector.py`** — the simplest
   non-trivial handler. Use it as the template for your own.
5. **`backend/engine/nodes/feature_engine.py`** + `signal_calculator.py`
   — the DRY chassis. One node, many configs. Read the module
   docstrings to internalise the "add a config, not a node" mindset.
6. **`backend/engine/refs.py` + `prompt_context.py`** — the cross-dataset
   reference grammar (`{dataset.col.agg}`, `{context.key}`). Used by
   DECISION_RULE, DATA_HIGHLIGHTER, SECTION_SUMMARY, REPORT_OUTPUT.
7. **`backend/engine/validator.py` + `hard_rules.py`** — pure validation.
   Read the top-of-file docstrings; you'll know which file to edit when
   you need to add a rule.
8. **`backend/workflows/fx_fro_v2_workflow.json` + `fisl_workflow.json`**
   — the two reference scenarios. Same chassis, different config.
9. **`backend/tests/test_fro_v2_golden_path.py` + `test_fisl_golden_path.py`**
   — golden-path integration tests. Best mental model for what a run
   produces end-to-end.
10. **`backend/app/main.py`** — the FastAPI router map. Each router has
    its own docstring; read just the one whose URL you're touching.

After this you should be able to ship a new scenario in a day. The
**ONBOARDING.md** sibling doc walks through it as a worked example.

### Cheat sheet

| If you want to…                              | Open                                                          |
|----------------------------------------------|---------------------------------------------------------------|
| Add a new node type                          | `backend/engine/nodes/<name>.py` + `<name>.yaml`              |
| Add an op to FEATURE_ENGINE                  | `backend/engine/nodes/feature_engine.py` (one new function)   |
| Add a built-in signal family                 | `backend/engine/nodes/signal_calculator.py` (BUILT_IN dict)   |
| Add a validation rule                        | `backend/engine/hard_rules.py` (one decorated function)       |
| Add an auto-fix                              | `backend/engine/auto_fixer.py`                                |
| Add a scenario template                      | `backend/templates/<name>.json`                               |
| Add a dataset                                | `backend/data_sources/metadata/<name>.yaml`                   |
| Change the Excel layout                      | `backend/engine/nodes/report_output.py`                       |
| Hook a new endpoint                          | `backend/app/routers/<router>.py`                             |
| Regenerate frontend node specs after a change| `python scripts/gen_artifacts.py`                             |

---

## 1 — Mental model

dbSherpa is a **deterministic, registry-driven workflow engine** wrapped
by an **LLM-driven agent** that plans, validates, and self-repairs
workflows. Every new scenario (FX front-running, FI wash trade,
insider trading…) is a **data file**, not a new program:

```
alert_payload  ─▶  RunContext  ─▶  DAG of typed nodes  ─▶  Excel report
                       ▲
                       │ validated + auto-fixed before run
                       │
              Planner  ─▶  Validator  ─▶  AutoFixer  ─▶  Planner (repair)
                       (Gemini)      (pure)       (pure)
```

Invariants you can build on:

1. **One registry, auto-discovered.** Every node declares a
   `NODE_SPEC` in its own file. `engine.registry` walks `engine/nodes/`
   at import time and collects them. There is no central list to edit.
2. **Stateless handlers.** A node handler receives `(node_dict,
   RunContext)` and mutates only the context. No globals, no hidden
   state. This means nodes are trivially testable and runs are
   reproducible.
3. **Pure validation.** `engine.validator` and `engine.hard_rules` have
   zero runtime dependencies — no FastAPI, no pandas computations, no
   I/O. You can validate a workflow without being able to run it.
4. **Single LLM seam.** All Gemini calls go through
   `llm.GeminiAdapter`. Swap it in tests, swap it for a different
   provider, do it in one place.
5. **Generated artifacts are checked in.** `contracts/node_contracts.json`,
   `frontend/src/nodes/generated.ts`, `engine/node_type_ids.py`, and
   root `node_detail.md` are regenerated by one script and committed.
   Runtime Studio data comes from `/node-manifest`; generated frontend
   metadata is a cold-start/offline fallback.

---

## 2 — Repository layout

```
backend/
├── api.py                         # uvicorn entrypoint → app.main
├── app/                           # HTTP layer (FastAPI)
│   ├── main.py                    # router composition, CORS, DI
│   ├── deps.py                    # DI helpers (copilot singleton, paths)
│   ├── schemas.py                 # pydantic request/response models
│   └── routers/
│       ├── workflows.py           # /workflows + /drafts CRUD
│       ├── run.py                 # /run, /run/stream (SSE), /run/demo
│       ├── validate.py            # /validate — pure validation
│       ├── reports.py             # /report/<id> — xlsx download
│       ├── copilot.py             # /copilot/chat, /copilot/generate, /contracts
│       └── agent.py               # /agent/metrics
│
├── engine/                        # Pure workflow engine (no FastAPI)
│   ├── __init__.py                # re-exports RunContext, run_workflow
│   ├── context.py                 # RunContext dataclass
│   ├── ports.py                   # PortSpec, ParamSpec, enums
│   ├── node_spec.py               # NodeSpec + _spec() factory
│   ├── node_type_ids.py           # GENERATED — TYPE_ID constants from NODE_SPECS
│   ├── registry.py                # auto-discovery of NODE_SPEC
│   ├── dag_runner.py              # topological exec + port type checks
│   ├── jobs.py                    # JobRunner seam (tests inject fakes)
│   ├── validator.py               # validate_dag() → ValidationIssue[]
│   ├── validation_codes.py        # ValidationErrorCode enum
│   ├── hard_rules.py              # @register_hard_rule declarative rules
│   ├── schema_version.py          # workflow schema migrations
│   ├── typed_config.py            # ParamSpec → coercion helpers
│   └── nodes/                     # ★ one file per node type ★
│       ├── alert_trigger.py
│       ├── execution_data_collector.py
│       ├── comms_collector.py
│       ├── market_data_collector.py
│       ├── feature_engine.py
│       ├── signal_calculator.py
│       ├── data_highlighter.py
│       ├── decision_rule.py
│       ├── section_summary.py
│       ├── consolidated_summary.py
│       └── report_output.py
│
├── agent/                         # LLM agent harness
│   ├── planner.py                 # Planner — calls GeminiAdapter, returns PlanResult
│   ├── prompt_builder.py          # system prompt + few-shot assembly
│   ├── validator_adapter.py       # agent-friendly wrapper over validate_dag()
│   ├── repair/
│   │   ├── auto_fixer.py          # deterministic fix rules (no LLM)
│   │   └── feedback_builder.py    # turn issues → structured repair brief
│   └── harness/
│       ├── runner.py              # AgentRunner — plan → validate → fix → repeat
│       ├── state.py               # AgentEvent, AgentPhase, AgentState
│       └── metrics.py             # in-process counters
│
├── copilot/
│   └── workflow_generator.py      # /copilot/chat + /copilot/generate glue
│
├── llm/                           # ★ only place Gemini is called ★
│   ├── __init__.py                # exports GeminiAdapter, get_default_adapter
│   └── gemini_adapter.py
│
├── data_sources/                  # Declarative dataset catalog
│   ├── registry.py                # DataSourceRegistry + ColumnSpec
│   └── metadata/
│       ├── trades.yaml
│       ├── market.yaml
│       ├── comms.yaml
│       └── signals.yaml
│
├── skills/                        # Markdown files teaching Copilot each scenario
│   ├── skills-fx-fro.md
│   ├── skills-fi-wash.md
│   └── …
│
├── workflows/                     # Ready-to-run workflows (.yaml preferred, .json supported)
├── drafts/                        # Copilot scratch workspace
├── demo_data/                     # CSV fixtures used by demo endpoint
├── contracts/
│   └── node_contracts.json        # GENERATED — commit with PR
├── scripts/
│   └── gen_artifacts.py           # run after any NODE_SPEC change
├── deploy/                        # Dockerfile + Cloud Run configs
└── tests/                         # pytest suite
    ├── conftest.py
    ├── test_validator.py
    ├── test_auto_fixer.py
    ├── test_hard_rules.py
    ├── test_validation_codes.py
    ├── test_gemini_adapter.py
    ├── test_copilot_edit_mode.py
    ├── test_data_sources.py
    ├── test_golden_path.py
    └── test_run_demo.py
```

---

## 3 — Core concepts

### 3.1 `NodeSpec` — the source of truth

Every node type exports one `NODE_SPEC` at module load. New nodes should use
the YAML form:

```python
NODE_SPEC = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_my_node)
```

That YAML plus the handler is the **canonical node contract** used by:

- workflow creation in Copilot (`PromptBuilder` reads live NodeSpecs),
- Studio UI forms and palette (`GET /node-manifest`),
- pre-run validation (`validate_dag` reads typed params/ports),
- runtime checks (`dag_runner` checks declared input/output ports).

There is also a derived `NodeSpec.contract` dict. That dict feeds
`/contracts`, `backend/contracts/node_contracts.json`, and prompt/docs
compatibility. It is not the source of truth. If the derived contract looks
wrong, fix the YAML/handler and regenerate artifacts.

The lower-level Python factory is still available and builds the same
`NodeSpec` object:

```
_spec(
    type_id: str,           # "ALERT_TRIGGER" — UPPER_SNAKE, enforced unique
    handler: Handler,       # fn(node_dict, RunContext) -> None
    description: str,       # one-liner shown in palette tooltip
    *,
    color: str,             # "#7C3AED" — icon stripe on the canvas
    icon: str,              # lucide-react icon name (e.g. "Siren")
    config_tags: tuple[str, ...] = (),   # params promoted to the minimap
    input_ports:  tuple[PortSpec, ...] | None = None,
    output_ports: tuple[PortSpec, ...] | None = None,
    params:       tuple[ParamSpec, ...] | None = None,
    constraints:  tuple[str, ...] = (),  # copilot-readable prose rules
    extras: dict | None = None,
) -> NodeSpec
```

- `PortSpec(name, type: PortType, description, optional)` — typed I/O.
  `PortType` is a closed enum: `DATAFRAME | SCALAR | OBJECT | TEXT`.
- `ParamSpec(name, type: ParamType, default, required, enum, widget,
  description)` — typed config field with UI hint. `ParamType` covers
  `STRING | INTEGER | NUMBER | BOOLEAN | ENUM | STRING_LIST | OBJECT |
  ARRAY | INPUT_REF | CODE`. `Widget` tells the frontend which editor to
  render.

`registry.py` walks `engine/nodes/` with `pkgutil.iter_modules` and
collects every `NODE_SPEC`. Duplicate `type_id`s raise at import time,
not at runtime.

**Example — the bundled `ALERT_TRIGGER` node** — showing the full
recipe you'll copy for new nodes:

```python
from ..context import RunContext
from ..node_spec import NodeSpec, _spec
from ..ports import ParamSpec, ParamType, PortSpec, PortType

STANDARD_FIELDS = ("trader_id", "book", "alert_date", "currency_pair",
                   "alert_id", "entity", "desk")


def handle_alert_trigger(node: dict, ctx: RunContext) -> None:
    """Bind alert payload fields into run context."""
    cfg = node.get("config", {})
    declared_fields: dict = cfg.get("alert_fields", {})

    for field_name in declared_fields:
        value = ctx.alert_payload.get(field_name)
        if value is not None:
            ctx.set(field_name, value)

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
            description="One context key per declared alert_field.",
        ),
    ),
    params=(
        ParamSpec(
            name="alert_fields",
            type=ParamType.OBJECT,
            description="Map of field_name → type (string|date|number).",
            default={},
            required=False,
        ),
    ),
    constraints=(
        "Must be the first node (id=n01).",
        "No dataset inputs or outputs.",
    ),
)
```

### 3.2 `RunContext` — the shared mutable state

```python
@dataclass
class RunContext:
    alert_payload: dict               # original payload from /run request
    values: dict[str, Any]            # scalar context — set()/get()/inject_template()
    datasets: dict[str, pd.DataFrame] # named DataFrames between nodes
    sections: dict[str, dict]         # narrative payloads for the report
    executive_summary: str
    disposition: str                  # "ESCALATE" | "REVIEW" | "DISMISS"
    output_branch: str
    report_path: str
    run_id: str                       # uuid4 hex, stamped onto every SSE frame
```

Rules:

1. Handlers **only** mutate `ctx`. They never return a DataFrame — they
   publish via `ctx.datasets[name]` so downstream nodes can read by
   name.
2. Scalars: use `ctx.set(key, value)` and `ctx.get(key)`.
3. `ctx.inject_template(s)` substitutes `{context.trader_id}` and
   similar in query templates.

### 3.3 DAG runner

`engine.dag_runner.run_workflow(workflow_dict, alert_payload)` does:

1. `topological_sort` — deterministic ordering using Kahn's algorithm.
2. For each node:
   - Locate the handler in `NODE_HANDLERS[type_id]`.
   - Dispatch `handler(node, ctx)`.
   - Enforce each declared output port actually exists and has the
     declared `PortType` (`_resolve_output_value` + `_assert_port_type`).
3. Return the mutated `RunContext`.

The runner also powers `run_workflow_stream(...)`, the authoritative
source for run-log SSE event names. It yields:

- `workflow_start` — one frame before the first node, includes run id,
  workflow name, total node count, and execution order.
- `node_start` — one frame immediately before a handler runs.
- `node_complete` — one frame after a handler succeeds, including a
  compact output snapshot for the UI.
- `node_error` — one frame when a handler or output contract check fails.
- `workflow_complete` — terminal success frame; result shape matches
  the blocking `/run` response.
- `workflow_error` — terminal failure frame.

### 3.4 Validator

`engine.validator.validate_dag(workflow_dict) → ValidationResult`
performs **every** structural check you'd want before letting a run
touch real data:

| Check family           | Examples                                                         |
|------------------------|------------------------------------------------------------------|
| Schema version         | `schema_version` is parseable; migration available if out-of-date |
| Shape                  | `nodes` and `edges` are lists; each node has `id` + `type`       |
| Acyclicity             | Kahn's algorithm; report cycle members                           |
| Referential integrity  | Every edge endpoint resolves to a node id                        |
| Node type known        | `type_id` present in `NODE_SPECS`                                |
| Param presence         | Every required `ParamSpec` is set                                |
| Param typing           | Declared type matches `ParamType`                                |
| Param values           | `ParamType.ENUM` values are in the allowed set                   |
| Port wiring            | Upstream output names referenced downstream via `input_name`     |
| Field bindings         | `SECTION_SUMMARY.field_bindings[].field` names exist in the resolved `DataSource` |
| Hard rules             | Node-specific invariants registered via `@register_hard_rule`    |

Every issue is a frozen `ValidationIssue(code, message, severity,
node_id, field)`. `code` is a `ValidationErrorCode` — see
`engine/validation_codes.py` for the canonical 30-entry inventory. The
enum is `str`-based so JSON serialises cleanly and equality `issue.code
== "UNKNOWN_TYPE"` works for old call sites.

**Field-binding column validation** — `_validate_field_bindings()` traces
`SECTION_SUMMARY.input_name` back to the producing collector and selected
source, e.g. `trades:hs_execution` or `oracle:oracle_orders`, then checks
each `field_bindings[].field` against that exact source schema plus known
transformer outputs from `FEATURE_ENGINE` and `SIGNAL_CALCULATOR`. Unknown
columns are validation errors. If lineage cannot be traced, the check is
skipped to avoid false positives.

### 3.5 Hard rules — the Open/Closed extension point

Per-node invariants that can't be expressed as "param X is required"
live in `engine/hard_rules.py`:

```python
@register_hard_rule(
    name="trade_version_pin",
    code=ValidationErrorCode.MISSING_TRADE_VERSION,
    node_type="EXECUTION_DATA_COLLECTOR",
    description="hs_execution queries must pin trade_version:1.",
)
def _rule_trade_version_pin(node: dict, dag: dict, result: _ResultSink) -> None:
    cfg = node.get("config", {}) or {}
    if cfg.get("source") != "hs_execution":
        return
    template = cfg.get("query_template", "") or ""
    if "trade_version:1" not in template:
        result.add(ValidationIssue(
            code=ValidationErrorCode.MISSING_TRADE_VERSION,
            message="hs_execution queries must pin `trade_version:1`.",
            severity="error",
            node_id=node.get("id"),
            field="config.query_template",
        ))
```

Adding a new rule is just dropping a new decorated function into
`engine/hard_rules.py` (or importing one from a feature module). The
validator's `run_hard_rules()` filters by `node_type`, catches rule
crashes so one bad rule can't abort the run, and forwards issues into
the same result list.

### 3.6 AutoFixer — deterministic repair

Before re-invoking the LLM, the agent tries to resolve issues without
another round-trip. `agent/repair/auto_fixer.py` dispatches on
`ValidationErrorCode`:

```python
_RULES: dict[ValidationErrorCode, Callable[[dict, dict, AutoFixReport], bool]] = {
    ValidationErrorCode.MISSING_TRADE_VERSION:  _fix_missing_trade_version,
    ValidationErrorCode.MISSING_LABEL:          _fix_missing_label,
    ValidationErrorCode.WRONG_ENTRY_ID:         _fix_wrong_entry_id,
    ValidationErrorCode.BAD_PARAM_TYPE:         _fix_bad_param_type_empty_array,
    ValidationErrorCode.MISSING_REQUIRED_PARAM: _fix_missing_required_param_known,
}
```

The AutoFixer also normalises edges (`source/target` → `from/to`) and
fills obvious defaults. It is **idempotent**: running it on an already-
clean workflow is a no-op.

### 3.7 Agent harness

`agent/harness/runner.py`'s `AgentRunner.run(...)` is the control loop:

```
understanding → planning → (Planner.generate)
                         ↓
                   validate_dag()
                         │
            ┌────────────┼────────────┐
        valid            invalid      invalid after AutoFixer
            │              │                 │
         success    AutoFixer clears it   feedback brief
                     → emit auto_fixing   → Planner.generate(repair)
                     → success            → loop (up to max_attempts)
```

It yields `AgentEvent`s which the `/copilot/generate/stream` endpoint
translates to SSE frames. The blocking `/copilot/generate` endpoint
drains the iterator and returns the final state.

### 3.8 LLM seam — `GeminiAdapter`

All Gemini calls go through `llm.gemini_adapter.GeminiAdapter`, which
exposes exactly two methods:

```python
adapter.chat_turn(
    system_prompt: str,
    history: list[dict],          # [{"role": "user"|"assistant", "content": ...}]
    user_turn: str,
    model: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = True,
) -> str

adapter.single_shot(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int | None = None,
    system_prompt: str | None = None,
) -> str
```

Who calls what:

| Module                                  | Method        | temperature |
|-----------------------------------------|---------------|-------------|
| `agent.planner.Planner`                 | `chat_turn`   | 0.0         |
| `copilot.workflow_generator.WorkflowCopilot.chat` | `chat_turn` | 0.3 |
| `engine.nodes.section_summary`          | `single_shot` | 0.2         |
| `engine.nodes.consolidated_summary`     | `single_shot` | 0.2         |

`get_default_adapter()` is an `lru_cache`-memoised factory. In tests,
pass a hand-rolled `GeminiAdapter` instance (or monkeypatch
`llm.get_default_adapter`) — handlers and the planner accept one as an
optional constructor arg.

### 3.9 Data source registry

`data_sources/registry.py` loads every YAML under
`data_sources/metadata/*.yaml` into a read-only catalog:

```python
@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str                # "string" | "number" | "integer" | "boolean" | "datetime" | "object"
    description: str = ""
    semantic: str | None = None    # "trader" | "size" | "price" | "time" | …
    optional: bool = False

@dataclass(frozen=True)
class DataSource:
    id: str
    description: str
    sources: tuple[str, ...]   # "hs_client_order", "hs_execution", …
    columns: tuple[ColumnSpec, ...]
```

Lookup via `from data_sources.registry import get_registry`.

**Semantic resolver (live).** `ColumnSpec.semantic` drives two runtime behaviours:

1. **LLM system prompt injection.** `DataSourceRegistry.schema_hints_for_prompt()` serialises every source into a compact block that `PromptBuilder.system_prompt()` injects under `## Data Source Column Schemas`. The LLM sees exact column names and their semantic tags, so it writes `field: "quantity"` rather than the alias `"size"`.

   ```python
   ds.semantic_map("hs_client_order")  # {"size": ["quantity"], "price": ["limit_price"], ...}
   ds.schema_hint()           # per-source markdown block for the prompt
   registry.schema_hints_for_prompt()   # all sources in one block
   ```

2. **Field-binding validator.** `_validate_field_bindings()` in `validator.py` checks every `SECTION_SUMMARY.field_bindings[].field` against the traced source schema and known transformer extras. For example, `SIGNAL_CALCULATOR` validates as upstream columns plus `_signal_*` columns, so pass-through fields like `exec_id` remain valid.

### 3.10 HTTP layer

Every router is single-concern, lives in `app/routers/*.py`, and is
included by `app/main.py`. Requests flow:

```
client ──POST /run──▶ run.py
                       │
                       ├─ validate_dag(workflow)      # fast-fail 422
                       ├─ get_default_runner()        # JobRunner seam
                       ├─ runner.execute(workflow, payload)
                       │                              # returns RunContext
                       ├─ stream → SSE frames   OR
                       ├─ demo   → xlsx FileResponse
                       └─ direct → {"run_id": …, "disposition": …}
```

`get_default_runner()` returns a `JobRunner` protocol implementation.
The default is an in-process synchronous runner. Tests inject a fake.
This is where a future "queue + worker" architecture will plug in
without changing the route handlers.

---

## 4 — End-to-end flows

### 4.1 "Run a saved workflow"

1. `POST /run {"workflow_id": "fx_fro_001", "alert_payload": {...}}`.
2. `run.py` loads JSON from `workflows/fx_fro_001.json`.
3. `validate_dag(workflow)` — 422 if any issues.
4. `get_default_runner().execute(workflow, alert_payload)`.
5. Handlers mutate `ctx` in topological order.
6. `REPORT_OUTPUT` node writes `output/fx_fro_<alert_id>.xlsx` and sets
   `ctx.report_path`.
7. The route returns `{"run_id", "disposition", "report_url", ...}`.
   The client fetches `/report/<run_id>` to download the xlsx.

### 4.2 "Copilot generate"

1. `POST /copilot/generate/stream {"prompt": "Build FX FRO for trader
   T001", "history": [...]}`.
2. Route instantiates an `AgentRunner` (via `deps.get_copilot`).
3. `AgentRunner.run()` yields `AgentEvent`s:
   - `understanding` — acknowledges the prompt.
   - `planning` — about to call the LLM.
   - Planner calls `GeminiAdapter.chat_turn(temperature=0,
     json_mode=True)`.
   - The reply is parsed into `PlanResult(raw, workflow)`.
   - `validate_dag(workflow)` — issues collected.
   - If clean → emit `success`.
   - If fixable → `AutoFixer.fix(workflow, issues)` + emit
     `auto_fixing` + recheck.
   - Otherwise → `feedback_builder` assembles a repair brief; back to
     the Planner with the previous message history extended.
4. Final `success` / `failed` event carries the workflow (or
   diagnostics). The frontend renders a live timeline.

### 4.3 "Save edits from the canvas"

1. User drags/wires/edits in the frontend.
2. The store tracks a dirty flag and sends
   `PUT /drafts/{id}` with the full JSON on debounce.
3. `workflows.py:save_draft` calls `validate_dag(...)` — failures are
   returned as warnings (the draft is saved regardless so the user
   doesn't lose work).
4. User clicks **Promote**: `POST /drafts/{id}/promote` — a full
   `validate_dag` runs again, and if clean, the draft is moved to
   `workflows/{id}.json` and removed from `drafts/`.

---

## 5 — Adding things (summary — see ONBOARDING.md for the worked example)

### 5.1 Add a node type

1. Create `engine/nodes/<name>.py`.
2. Implement `handle_<name>(node: dict, ctx: RunContext) -> None`.
3. At the bottom, `NODE_SPEC = _spec(...)` with `input_ports`,
   `output_ports`, `params`.
4. Add a unit test in `tests/test_<name>.py`.
5. Run `python scripts/gen_artifacts.py`.
6. Done. No registry edit.

### 5.2 Add a dataset

1. Create `data_sources/metadata/<id>.yaml` with `id`, `description`,
   `sources`, and either `columns` or per-dropdown `source_schemas`. Add `semantic` tags (`trader`, `size`,
   `price`, `time`, `notional`) to every column where applicable — these
   tags are injected into the LLM system prompt and checked by the
   field-binding validator at validation time.
2. Add/extend a collector node that emits that dataset and records provenance
   through `collector_source_ref(...)`, e.g. `trades:hs_execution`.
3. Done. `get_registry()` picks it up on next import.

### 5.3 Add a validation rule

1. In any module imported on startup (usually `engine/hard_rules.py`,
   or a new `engine/rules/<feature>.py` that `hard_rules` imports):

    ```python
    @register_hard_rule(
        name="my_rule",
        code=ValidationErrorCode.YOUR_CODE,  # add to validation_codes.py first
        node_type="MY_NODE",
    )
    def _my_rule(node, dag, result): ...
    ```

2. Add a unit test in `tests/test_hard_rules.py`.

### 5.4 Add an auto-fix

1. Write `_fix_<thing>(wf, err, report) -> bool` in
   `agent/repair/auto_fixer.py`.
2. Add it to `_RULES` keyed by `ValidationErrorCode.<CODE>`.
3. Add a unit test in `tests/test_auto_fixer.py` covering both "fix
   applied" and "idempotent second run" paths.

### 5.5 Add a scenario for the Copilot

1. Create `skills/skills-<scenario>.md` following the structure of
   `skills-fx-fro.md`.
2. Reload the backend (the `WorkflowCopilot` reads the skills directory
   at startup).

---

## 6 — Testing guide

### 6.1 What to test and where

| Layer            | Location                           | What we assert                                      |
|------------------|------------------------------------|-----------------------------------------------------|
| Node handler     | `tests/test_<node>.py`             | Given a RunContext, does it publish the right shape?|
| Validator check  | `tests/test_validator.py`          | A malformed workflow surfaces the right ErrorCode   |
| Hard rule        | `tests/test_hard_rules.py`         | Rule fires for its `node_type`, not others          |
| Auto-fix rule    | `tests/test_auto_fixer.py`         | Fix applies; second run is a no-op                  |
| LLM seam         | `tests/test_gemini_adapter.py`     | Determinism pins, role translation, caching         |
| Validation codes | `tests/test_validation_codes.py`   | Wire-compat; every emitted code is a known member   |
| Copilot edit mode| `tests/test_copilot_edit_mode.py`  | Selected-node context is piped into the prompt      |
| Data sources     | `tests/test_data_sources.py`       | Semantic map, schema hint, prompt injection coverage|
| Golden path      | `tests/test_golden_path.py`        | Full DAG run produces expected disposition          |
| Demo run         | `tests/test_run_demo.py`           | `/run/demo` returns a valid xlsx                    |

### 6.2 Patterns

- **Node tests** use `RunContext(alert_payload=...)` directly and call
  the handler function. No FastAPI, no HTTP.
- **Integration tests** use `fastapi.testclient.TestClient(app)` and
  assert on response JSON / response headers.
- **LLM in tests** — monkeypatch `Planner.generate` or inject a stubbed
  `GeminiAdapter`. Never hit the real API in CI.

### 6.3 Running tests

```bash
uv run pytest backend/tests -q                    # full suite
uv run pytest backend/tests/test_validator.py -q   # targeted
uv run pytest backend/tests -k "hard_rule" -q      # pattern match
```

### 6.4 Example unit test (handler)

```python
# tests/test_alert_trigger.py
from engine.context import RunContext
from engine.nodes.alert_trigger import handle_alert_trigger


def test_binds_standard_fields_even_if_not_declared():
    ctx = RunContext(alert_payload={"trader_id": "T001", "book": "FX-SPOT"})
    node = {"id": "n01", "type": "ALERT_TRIGGER", "config": {}}

    handle_alert_trigger(node, ctx)

    assert ctx.get("trader_id") == "T001"
    assert ctx.get("book") == "FX-SPOT"


def test_declared_fields_win_even_if_null_in_payload():
    ctx = RunContext(alert_payload={"trader_id": "T001"})
    node = {
        "id": "n01",
        "type": "ALERT_TRIGGER",
        "config": {"alert_fields": {"trader_id": "string", "foo": "string"}},
    }

    handle_alert_trigger(node, ctx)

    assert ctx.get("trader_id") == "T001"
    assert ctx.get("foo") is None   # declared but absent → not set
```

### 6.5 Example integration test (HTTP)

```python
# tests/test_run_demo.py (excerpt)
from fastapi.testclient import TestClient

from app.main import app


def test_demo_run_returns_xlsx():
    client = TestClient(app)
    resp = client.post("/run/demo", json={})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert resp.headers.get("X-Disposition") in {"ESCALATE", "REVIEW", "DISMISS"}
```

---

## 7 — Golden rules

The rules below are enforced by code review. If your PR breaks one,
reviewers will ask you to refactor.

1. **No `import fastapi` inside `engine/`.** The engine is pure; if it
   needs an HTTP concern, the concern belongs in `app/`.
2. **No direct `from google import genai` outside `llm/`.** Use
   `GeminiAdapter`. New LLM providers are a swap of one file.
3. **No module-level global state beyond the registries.** Add
   dependencies via constructor injection so they're testable.
4. **No side effects on import.** The only imports that do work are the
   `engine/nodes/*` modules declaring their `NODE_SPEC` and the
   YAML-loading registries. Both are deterministic, cheap, and pure.
5. **Every new `ValidationErrorCode` gets a docstring and a test.**
6. **Generated artifacts** (`contracts/node_contracts.json`,
   `frontend/src/nodes/generated.ts`, `engine/node_type_ids.py`,
   `../node_detail.md`) are never hand-edited. Run
   `scripts/gen_artifacts.py`.
7. **Determinism pins** (`temperature=0`, `json_mode=True`) on the
   Planner are non-negotiable. Narrative nodes run at `temperature=0.2`;
   nothing higher without a good reason.

---

## 8 — Deployment

`backend/deploy/` contains the Cloud Run artifacts:

- `Dockerfile` — multi-stage; final image runs `uvicorn api:app`.
- `cloudbuild.yaml` — builds + pushes to Artifact Registry + deploys.
- `service.yaml` — Cloud Run service spec with
  `DBSHERPA_OUTPUT_DIR=/tmp/dbsherpa` so writes land on a writable
  volume.

The frontend has its own `frontend/deploy/` (nginx + SPA + SSE-safe
reverse proxy). Both are deployed independently.

Env vars the backend reads:

| Name                | Purpose                                       | Required |
|---------------------|-----------------------------------------------|----------|
| `GEMINI_API_KEY`    | Passed through to `GeminiAdapter`             | for LLM  |
| `DBSHERPA_OUTPUT_DIR` | Base path for generated xlsx reports        | no       |

Secrets are never committed. See `backend/.env.example` for the
template and `.gitignore` for what stays out of the repo.

---

## 8.5 — Chassis primitives

The chassis is the small set of generic node types every scenario
composes from. None of them know what an "FRO" or "FISL" is — they
just slice, fan-out, summarise, and emit. Adding a 51st scenario is a
new JSON workflow, not new node code.

| Primitive            | Role                                                                                         |
|----------------------|----------------------------------------------------------------------------------------------|
| `TIME_WINDOW`        | Publishes `{start_time, end_time, buffer_minutes}` from the alert's event time.              |
| `EXECUTION_DATA_COLLECTOR(source=hs_client_order)` | Pulls order-lifecycle rows from Solr. Honours `window_key` so all collectors share one window. |
| `EXECUTION_DATA_COLLECTOR(source=hs_execution / hs_trades / hs_quotes)` / `MARKET_DATA_COLLECTOR` / `COMMS_COLLECTOR` | Same `window_key` + filter contract; `COMMS_COLLECTOR` adds `keyword_categories` and an optional `emit_hits_only` aux dataset (`<output>_hits`). |
| `EXTRACT_SCALAR` / `EXTRACT_LIST` | Reduce a column to a scalar / sorted list. Powers cascade and ladder patterns. |
| `GROUP_BY`           | Partitions a dataset by column → publishes `{prefix}_{key}` per group + `{values:[...]}` keys list. |
| `MAP`                | Control-flow primitive. Forks a child `RunContext` per key, runs an inline `sub_workflow`, harvests `collect_values` / `collect_datasets` back to the parent. Composes recursively — see `fisl_workflow.json` for nested MAP. |
| `FEATURE_ENGINE`     | One node, an op registry (`window_bucket`, `time_slice`, `groupby_agg`, `pivot`, `rolling`, `derive`, `apply_expr`). Each op publishes the working DataFrame; `as: <name>` also stashes intermediate results. Replaces the urge to add a per-scenario transform node. |
| `SIGNAL_CALCULATOR`  | Same node, swap `signal_type` (`FRONT_RUNNING`, `WASH_TRADE`, `SPOOFING`, `LAYERING`) or `mode: upload_script`. Always emits the 5-column contract `_signal_flag/_signal_score/_signal_reason/_signal_type/_signal_window`. |
| `DATA_HIGHLIGHTER`   | Per-row `pandas.eval` rules with `{ref}` substitution before eval — rules can pull thresholds from any upstream dataset/context (`notional > {context.peak_threshold}`). Emits `_highlight_colour/_highlight_label`; REPORT_OUTPUT auto-uses the `_highlighted` sibling when `include_highlights: true`. |
| `DECISION_RULE`      | Threshold mode (default) **or** rules mode: ordered `[{name, when, severity, disposition}]` where `when` accepts `{ref}` (truthy) or `{ref} OP literal`. Emits `disposition / severity / score / matched_rule / output_branch`. |
| `SECTION_SUMMARY`    | Three modes: `templated`, `fact_pack_llm` (verify-and-retry), `event_narrative`. Optional `prompt_context` block injects cross-dataset slots into the prompt. |
| `CONSOLIDATED_SUMMARY` | LLM exec summary fed by `ctx.sections + ctx.disposition + ctx.severity`. Same `prompt_context` extensibility. |
| `REPORT_OUTPUT`      | `tabs` for static datasets + `expand_from` for *any* iterable (context list, MAP results dict, dataset column). Each tab gets a templated `name` and `dataset` resolved against the bound `as` slot. |

### Cross-cutting grammars

- **Refs** (`engine/refs.py`) — single grammar used by every templating
  node. `{dataset}`, `{dataset.col}`, `{dataset.col.agg}` (`agg ∈
  sum|mean|max|min|count|nunique|first|last|any|all`), `{dataset.@row_count}`,
  `{context.key.attr…}`. Resolvers raise `ResolveError` so callers can
  decide silent-fallback vs. validation surface.
- **`prompt_context` block** (shared by SECTION_SUMMARY +
  CONSOLIDATED_SUMMARY): `{mode: template|dataset|mixed, vars: {name:
  ref_expr, …}, dataset: {ref, format, max_rows, columns}}`. `vars`
  resolve refs into named slots; the serialised dataset is exposed as
  `{dataset}`. See `engine/prompt_context.py`.

### Reference workflows

Two workflows exercise the full chassis end-to-end. Same node set,
different config — that's the proof.

- `workflows/fx_fro_v2_workflow.json` — TIME_WINDOW → 4 windowed
  collectors → GROUP_BY orders by book → MAP per-book → FEATURE_ENGINE
  (`window_bucket` + `derive`) → SIGNAL_CALCULATOR (`FRONT_RUNNING`)
  → DATA_HIGHLIGHTER → DECISION_RULE (rules mode) → three
  SECTION_SUMMARYs (one per mode) → CONSOLIDATED_SUMMARY → REPORT_OUTPUT
  with static tabs + `expand_from` per book.
  Test: `tests/test_fro_v2_golden_path.py`.
- `workflows/fisl_workflow.json` — same chassis, **zero new node
  code**. Nested MAP (outer venue, inner book) for the structural
  proof; FEATURE_ENGINE composes `window_bucket → groupby_agg →
  pivot` to build an order-book ladder; SIGNAL_CALCULATOR runs with
  `signal_type: SPOOFING`. Test: `tests/test_fisl_golden_path.py`.

The validator recurses into every `MAP.sub_workflow` (re-scoping
issues under the parent MAP node). It skips the topology pass inside
sub-workflows — they have no `ALERT_TRIGGER` / `REPORT_OUTPUT` — and
skips the `input_name → output_name` wiring check inside, because MAP
aliases parent datasets via `iteration_dataset_alias`.

## 8.6 — Workflow templates

Templates are vetted scenario skeletons the planner uses as a
starting point instead of generating a workflow from scratch. They
live in `backend/templates/<name>.json`:

```
{
  "name": "fx_front_running",
  "description": "...",
  "matches": {
    "scenarios": ["front-running", "fro", ...],
    "datasets": ["orders", "executions", "comms", "market"]
  },
  "parameters": [{"name": "trader_id", "type": "string", "required": true}, ...],
  "skeleton": { ...full nodes + edges... }
}
```

- `agent/templates.py` exposes `TemplateRegistry.from_directory()` and
  `select(intent)`. The selector scores `+10` per scenario keyword
  overlap, `+1` per dataset overlap, returns the highest-scoring
  template (or `None` if no signal matches).
- Every bundled template's skeleton must validate clean against
  `validate_dag` — see `tests/test_templates.py`. That guarantees a
  planner that drops the skeleton straight onto the runtime never
  produces a structurally invalid workflow.
- Adding a new scenario template: copy an existing JSON, adjust
  `matches`, `parameters`, and `skeleton`, drop it in
  `backend/templates/`. The registry auto-discovers it on next load.

---

## 9 — Extending further

Want to understand a subsystem more deeply? These are the best
"sources of truth":

- **Planner**: `backend/agent/planner.py` + `prompt_builder.py`
- **Templates**: `backend/agent/templates.py` + `backend/templates/*.json`
- **Chassis primitives**: `backend/engine/nodes/{time_window,group_by,map_node,extract_scalar,extract_list}.py`
- **Validator**: `backend/engine/validator.py` + `validation_codes.py` +
  `hard_rules.py` (+ the docstring at the top of each)
- **Node execution semantics**: `backend/engine/dag_runner.py`
- **LLM integration**: `backend/llm/gemini_adapter.py`
- **Data catalog**: `backend/data_sources/registry.py` + the YAMLs
  beside it

Every one of those files opens with a docstring explaining the design
decisions. If the docstring disagrees with this document, the
docstring wins — it lives with the code.
