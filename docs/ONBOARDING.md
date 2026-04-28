# dbSherpa Onboarding

> Start here when you are new to the repo. This file is intentionally short:
> the detailed, current instructions live in the four bible docs below.

## What This System Is

dbSherpa is a workflow builder and runner for trade-surveillance scenarios.

The current architecture has four important truths:

- Backend node definitions are the source of truth. A node is a YAML NodeSpec plus a Python handler under `backend/engine/nodes/`.
- Data-source schemas are YAML under `backend/data_sources/metadata/`.
- The Studio UI refreshes node metadata from backend `GET /node-manifest`; `frontend/src/nodes/generated.ts` is only a cold-start fallback.
- Copilot generation is constrained by live NodeSpecs, data-source YAML, skills, and deterministic backend validation.

## Local Setup

Prereqs:

- Python 3.11+
- Node.js 20+
- Gemini API key for Copilot and LLM summaries

Run:

```bash
export GEMINI_API_KEY=...
./start.sh
```

Open:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API docs: http://localhost:8000/docs
```

`start.sh` does not auto-source `backend/.env`. Keep secrets local and untracked; export env vars in the shell or explicitly opt into local dotenv loading.

## Read These First

| Task | Canonical doc |
| --- | --- |
| Answer common dev/architect/PO questions | [`FAQ.md`](FAQ.md) |
| Add or change a node | [`HOW_TO_DEFINE_A_NODE.md`](HOW_TO_DEFINE_A_NODE.md) |
| Add or change a dataset/source schema | [`HOW_TO_ONBOARD_A_DATASOURCE.md`](HOW_TO_ONBOARD_A_DATASOURCE.md) |
| Build or test a workflow YAML from backend | [`HOW_TO_BUILD_A_WORKFLOW_FROM_BACKEND.md`](HOW_TO_BUILD_A_WORKFLOW_FROM_BACKEND.md) |
| Build, validate, run, or generate a workflow in Studio | [`HOW_TO_BUILD_A_WORKFLOW_FROM_UI.md`](HOW_TO_BUILD_A_WORKFLOW_FROM_UI.md) |
| Deploy frontend/backend separately to Cloud Run | [`CLOUD_RUN_SPLIT_DEPLOYMENT.md`](CLOUD_RUN_SPLIT_DEPLOYMENT.md) |
| Understand backend architecture | [`BACKEND_ARCHITECTURE.md`](BACKEND_ARCHITECTURE.md) |
| Understand frontend architecture | [`FRONTEND_ARCHITECTURE.md`](FRONTEND_ARCHITECTURE.md) |

## One Place Per Concern

| Concern | Source of truth |
| --- | --- |
| Node behavior and UI metadata | `backend/engine/nodes/<node>.yaml` + `<node>.py` |
| Data-source columns and semantic tags | `backend/data_sources/metadata/<source>.yaml` |
| Copilot domain knowledge | `backend/skills/*.md` |
| Saved runnable workflows | `backend/workflows/*.yaml` preferred; legacy `.json` still loads |
| Copilot templates | `backend/templates/*.json` |
| Generated fallback artifacts | `backend/scripts/gen_artifacts.py` output |

There is no frontend palette registry to hand-edit. Refresh the UI from the backend after NodeSpec changes.

## Test Commands

Backend:

```bash
uv run pytest backend/tests -q
```

Frontend:

```bash
npm --prefix frontend run build
```

Regenerate artifacts after NodeSpec changes:

```bash
uv run python backend/scripts/gen_artifacts.py
```

Generated artifacts include:

- `backend/engine/node_type_ids.py`
- `backend/contracts/node_contracts.json`
- `frontend/src/nodes/generated.ts`
- `node_detail.md`

## Current Chassis

Common workflow building blocks:

- `ALERT_TRIGGER`
- `TIME_WINDOW`
- `EXECUTION_DATA_COLLECTOR` / Solr Data Collector
- `MARKET_DATA_COLLECTOR`
- `COMMS_COLLECTOR`
- `ORACLE_DATA_COLLECTOR`
- `GROUP_BY`
- `MAP`
- `FEATURE_ENGINE`
- `SIGNAL_CALCULATOR`
- `DATA_HIGHLIGHTER`
- `DECISION_RULE`
- `SECTION_SUMMARY`
- `CONSOLIDATED_SUMMARY`
- `REPORT_OUTPUT`

Solr orders, executions, trades, combined order/execution rows, and quotes are all handled by `EXECUTION_DATA_COLLECTOR` via its `source` dropdown. The dropdown comes from `backend/data_sources/metadata/trades.yaml`.

## Before You Commit

Run:

```bash
uv run pytest backend/tests -q
npm --prefix frontend run build
```

Check:

- No real `.env` or API keys are staged.
- Generated artifacts are updated if NodeSpecs changed.
- `node_detail.md` reflects the node catalog.
- Workflows validate if you touched workflow YAML/JSON.
