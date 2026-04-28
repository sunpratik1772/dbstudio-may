# How To Build A Workflow From The UI

> The rule: Studio exports and imports workflows as YAML for humans, then
> converts them to the same JSON-compatible DAG the backend validates and runs.
> Node types, colors, sections, params, and contracts come from the backend
> NodeSpec manifest.

## Start The App

```bash
export GEMINI_API_KEY=...   # needed for Copilot and LLM summaries
./start.sh
```

Open:

```text
http://localhost:5173
```

Backend docs are at:

```text
http://localhost:8000/docs
```

## Refresh Node Specs

The left palette is backed by `GET /node-manifest`.

Use the small refresh icon in the `NODES` palette header when:

- You added/edited a backend NodeSpec.
- You changed a source dropdown derived from data-source YAML.
- You regenerated artifacts and want the UI to pull the live backend state.

The icon spins while syncing and flashes green when the manifest is loaded.

## Build Manually

1. Drag nodes from the left palette to the canvas.
2. Select a node to edit its config in the right panel.
3. Wire nodes by dragging from output handles to input handles.
4. Use `Validate` before `Run`.
5. Use `Run` to stream execution logs and produce output.
6. Use `Save` to promote the workflow to `backend/workflows`.

Double-clicking a palette node also adds it to the canvas.

## Validate

The shield icon in the topbar calls `POST /validate`.

States:

- Neutral: not validated or workflow changed since the last validation.
- Green: current workflow validated cleanly.
- Red badge: validation errors exist; badge count is the error count.

Validation checks:

- Schema version.
- Registered node types.
- Edge shape and dangling edges.
- DAG cycles.
- Required params and enum values.
- `input_name` to upstream `output_name` wiring.
- Field-binding columns against data-source YAML.
- Hard rules such as `trade_version:1` and disabled upload scripts.

## Run

The Run button streams `POST /run/stream`.

The right run log shows:

- Workflow start.
- Per-node start/complete/error.
- Durations.
- Output previews.
- Final disposition/report output.

Invalid workflows do not run; the backend returns structured validation errors first.

## Build With Copilot

Open Copilot in the right panel and use Plan mode.

Copilot generation lifecycle:

```text
Understanding
Retrieving skills & contracts
Drafting workflow
Validating & repairing pass 1
Validating & repairing pass 2/3 only if needed
Finalizing workflow
Workflow generated
```

Only pass 1 is shown initially. Pass 2 and pass 3 appear only if previous passes fail.

Copilot guardrails shown in the panel reflect live backend state:

- Live node count from NodeSpecs.
- Data-source catalog count.
- Skill files included in prompt context.
- Host capabilities such as `upload_script` being disabled.

Generated workflows replace the canvas only after backend validation succeeds.

## Create vs Edit Prompts

Prompt wording matters:

- `create`, `generate`, `build`, `make`, `new` starts greenfield and replaces the current canvas after validation.
- `fix`, `repair`, `edit`, `update`, `change`, `add`, `remove`, `this`, `current`, `existing`, `canvas` attaches the current canvas for targeted edits.

The context chip above the input tells you whether the next prompt will replace or edit the loaded workflow.

## Clear

The Clear button unloads the current workflow entirely:

- Canvas workflow.
- Saved/draft filename identity.
- Selection.
- Run logs/results.
- Validation issues.
- Pending run event queue.

It does not delete saved workflow files from disk.

## Save, Drafts, Import, Export

Copilot generations auto-save as drafts.

- `Templates` opens saved/draft workflows.
- `Save` writes the current workflow to the saved workflow store, using `.yaml` for new saves.
- `Export` downloads human-readable workflow YAML.
- `Import` accepts `.yaml`, `.yml`, and legacy `.json` workflow files.

Internally the canvas still holds the runtime JSON-compatible DAG object. YAML
conversion happens at import/export and when the backend reads or writes
workflow files.

## Troubleshooting

If a node is missing from the palette:

1. Confirm the backend started without import errors.
2. Confirm the node module exports `NODE_SPEC`.
3. Confirm the YAML has `ui.palette`.
4. Click the node refresh icon.
5. Run `uv run python backend/scripts/gen_artifacts.py` if the fallback needs updating.

If Copilot generates invalid workflows:

1. Check the guardrail card.
2. Look at validation error codes in the timeline.
3. Use a fix/edit prompt if you want Copilot to repair the current canvas.
4. Check that the scenario is represented by skills and data-source YAML.

If Run fails after validation:

1. Open Run Log.
2. Check per-node runtime output.
3. Confirm mock CSV paths exist under `backend/` or use synthetic data.
4. Confirm a node handler writes the outputs declared in its NodeSpec.

## Checklist

- Nodes palette was refreshed after backend spec changes.
- Workflow validates green before running.
- Copilot prompt says replace/edit as intended.
- Run produces output and report link.
- Workflow saved or exported if you need to keep it.
