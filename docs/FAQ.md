# dbSherpa FAQ

> Twenty practical questions a developer, architect, product owner, or reviewer
> is likely to ask when first reading this repo.

## 1. What is dbSherpa in one sentence?

dbSherpa is a workflow builder and runner for trade-surveillance investigations:
users describe an alert, Copilot proposes a workflow, deterministic validation
checks it, and the backend runs it to produce evidence and reports.

## 2. Why is this better than hard-coding each surveillance scenario?

Hard-coded scenarios are slow to change and duplicate a lot of plumbing. In
dbSherpa, scenarios are assembled from reusable nodes, data-source metadata,
skills, and workflow YAML. That means a new scenario often needs configuration
and workflow changes, not a new application.

## 3. What is the simplest mental model of the system?

Think of it as three layers:

- **Definitions:** NodeSpecs, data-source YAML, skills, workflows.
- **Control plane:** UI, Copilot, validator, auto-fixer.
- **Execution plane:** DAG runner, node handlers, report writer.

Definitions describe what is allowed. The control plane helps build valid
workflows. The execution plane runs only the validated DAG.

## 4. Where do node definitions live?

Node definitions live under `backend/engine/nodes/`.

Each normal node has:

```text
backend/engine/nodes/<node>.yaml  # inputs, outputs, params, UI metadata
backend/engine/nodes/<node>.py    # runtime handler
```

You do not add new nodes by editing frontend constants or `node_spec.py`.

## 5. What is a NodeSpec?

A NodeSpec is the contract for one node type. It says:

- what the node is called (`type_id`),
- what config fields it accepts (`params`),
- what data it expects (`input_ports`),
- what it produces (`output_ports`),
- how it appears in the UI (`ui`),
- what rules Copilot and humans should respect (`constraints`).

The Python handler must honor the YAML contract.

## 6. What is the difference between NodeSpec and `node_contracts.json`?

The NodeSpec YAML plus handler is the source of truth. `node_contracts.json` is
a generated artifact for compatibility, docs, and prompt material. If the
contract looks wrong, fix the YAML/handler and regenerate artifacts. Do not
hand-edit `node_contracts.json`.

## 7. How does the frontend know about new nodes?

The frontend asks the backend for `GET /node-manifest`. That endpoint is built
from the live NodeSpec registry. The generated frontend file
`frontend/src/nodes/generated.ts` is only a fallback for cold-start/offline
cases.

In Studio, click the node refresh icon after backend NodeSpec changes.

## 8. Where do data sources live?

Data-source schemas live under:

```text
backend/data_sources/metadata/*.yaml
```

These YAML files tell the system what source names, tables, columns, types, and
semantic tags exist. Copilot, validation, docs, and collector dropdowns should
read from these files instead of inventing schema by hand.

## 9. How do I onboard a new data source?

Start with metadata YAML. For example, a Redshift source with two tables would
be declared in `backend/data_sources/metadata/redshift.yaml`. If the source also
needs runtime access, add connector code such as:

```text
backend/data_sources/connectors/redshift.py
backend/engine/nodes/redshift_data_loader.yaml
backend/engine/nodes/redshift_data_loader.py
```

The YAML says what data exists. The connector says how to query it. The node
handler maps workflow config into a safe connector call.

## 10. Where do connection strings and secrets go?

Never put secrets in YAML or committed workflow files. Runtime credentials
belong in environment variables or Secret Manager. Committed examples in
`backend/.env.example` should stay commented out.

For Cloud Run, put secrets in Secret Manager and wire them into the backend
service.

## 11. What is a workflow now: YAML or JSON?

Humans should author and export workflows as YAML. Internally, the backend
converts YAML into the same JSON-compatible Python dict that the validator and
runner already understand.

So:

- YAML is the human-friendly file format.
- JSON-compatible dict is the runtime shape.
- Legacy `.json` workflows still load.

## 12. Why use YAML for workflows?

Workflow JSON gets hard to read because node configs can be nested and verbose.
YAML is easier for developers and product owners to review in pull requests,
especially when comparing node order, labels, configs, and edges.

The runtime does not become YAML-dependent; conversion happens at the boundary.

## 13. What validates a workflow?

`backend/engine/validator.py` validates the DAG before execution. It checks
things like:

- schema version,
- known node types,
- required params,
- enum values,
- edge shape,
- dangling edges,
- cycles,
- source/column references,
- hard surveillance rules.

Invalid workflows should fail before any node handler runs.

## 14. What runs a workflow?

`backend/engine/dag_runner.py` runs the workflow in topological order. It calls
the handler for each node type from the registry, passes a shared `RunContext`,
and checks declared runtime input/output contracts around handler execution.

## 15. What does Copilot actually use to generate workflows?

Copilot prompt context is built from:

- live NodeSpecs,
- data-source YAML,
- surveillance skill markdown files,
- active host capabilities,
- validator feedback from previous attempts.

It should not invent node types, params, ports, data sources, or columns outside
those definitions.

## 16. What are skills?

Skills are domain guidance files under `backend/skills/*.md`. They explain
surveillance patterns such as FX front-running, FI spoofing, layering, wash
trades, and communications review.

Adding skills improves Copilot's scenario understanding, but skills do not
override NodeSpecs or data-source schemas. The validator still enforces the hard
contract.

## 17. What looks complicated but is actually simple?

The code can look large because it separates concerns carefully:

- nodes define operations,
- workflows wire operations,
- data-source YAML defines available data,
- skills define domain reasoning,
- validator defines what is allowed,
- runner executes what already passed validation.

Most changes touch only one or two of those areas.

## 18. How do I decide whether to add a node or just configure an existing one?

Add a node only when there is a genuinely new reusable operation. If you are
only changing thresholds, field names, source names, report labels, grouping
keys, or filters, prefer workflow YAML or existing node params.

Good default: configure first, add code only when repetition or runtime behavior
proves a new abstraction is needed.

## 19. How do frontend and backend deploy separately?

Backend deploys as a FastAPI Cloud Run service from `backend/`. Frontend deploys
as an nginx/Vite Cloud Run service from `frontend/`.

The browser calls the frontend origin at `/api/*`. Frontend nginx forwards that
traffic to the backend Cloud Run URL from `BACKEND_URL`. This keeps the browser
same-origin and avoids CORS/SSE problems.

See `CLOUD_RUN_SPLIT_DEPLOYMENT.md`.

## 20. What should I run before opening a PR or pushing?

Run:

```bash
uv run pytest backend/tests -q
npm --prefix frontend run build
```

Also run artifact generation after NodeSpec changes:

```bash
uv run python backend/scripts/gen_artifacts.py
```

Do not commit real `.env` files, API keys, credentials, or transient draft
files unless there is a deliberate reason.

