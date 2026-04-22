# dbSherpa

**A modular, agent-driven trade-surveillance platform.** Investigators
describe an alert in natural language; the Gemini-powered Copilot
authors a deterministic workflow; the engine runs it and produces a
regulator-grade Excel report.

<img alt="dbSherpa" width="100%"
     src="https://img.shields.io/badge/python-3.11%2B-blue" />
<img alt="React" src="https://img.shields.io/badge/react-18-61dafb" />
<img alt="Tests" src="https://img.shields.io/badge/tests-66%20passing-brightgreen" />
<img alt="License" src="https://img.shields.io/badge/license-proprietary-lightgrey" />

---

## Why it exists

Surveillance teams juggle dozens of scenarios (FX front-running, wash
trades, spoofing, layering, insider trading, comms abuse…). Each one
has its own data extracts, thresholds, narrative sections, and
escalation rules. Historically this means either:

- a rigid "scenarios as code" platform that takes a quarter to change, or
- a thousand ad-hoc Excel macros that can't be audited.

dbSherpa is a third option: **every scenario is data** — a markdown
skill file, a YAML dataset declaration, a workflow JSON. The Copilot
assembles them on demand, the validator pins them to a deterministic
contract, and the engine runs them the same way every time.

---

## Architecture in 30 seconds

```
               ┌──────────────────────────────────────────────┐
               │              Frontend (React + ReactFlow)    │
               │   palette • canvas • config • Copilot • log  │
               └───────────┬───────────────┬──────────────────┘
                           │ REST + SSE    │
                           ▼               ▼
        ┌─────────────────────┐    ┌──────────────────────┐
        │   FastAPI routers   │    │  /copilot/generate   │
        │ /run, /validate, …  │    │        (SSE)         │
        └──────────┬──────────┘    └──────────┬───────────┘
                   │                          │
                   ▼                          ▼
     ┌──────────────────────┐  ┌────────────────────────────┐
     │  Deterministic engine │  │      Agent harness         │
     │  • auto-discovered    │  │  Planner → Validator →     │
     │    NODE_SPEC registry │  │  AutoFixer → Planner …     │
     │  • topological runner │  │  (temperature=0, JSON)     │
     │  • typed ports/params │  └──────────┬─────────────────┘
     │  • pure validator     │             │
     │  • hard-rule registry │             ▼
     └──────────┬───────────┘  ┌────────────────────────────┐
                │              │   llm.GeminiAdapter        │
                ▼              │   (single LLM seam)        │
     ┌──────────────────────┐  └────────────────────────────┘
     │   Excel report       │
     │   + disposition      │
     └──────────────────────┘
```

**Key design moves:**

- **One registry, auto-discovered.** Every node is one file under
  `backend/engine/nodes/`; adding a node type is never a merge conflict.
- **Pure validator.** `validate_dag()` + hard-rule registry = structured,
  machine-readable errors the UI, the agent, and the auto-fixer all
  consume.
- **Single LLM seam.** `llm.GeminiAdapter` is the only file that imports
  `google.genai`. Swap providers in one place.
- **Generated artifacts are checked in.** The frontend has no Python
  coupling at runtime.

---

## Quick start

```bash
# 1 — Clone + enter
git clone https://github.com/sunpratik1772/rebuilder.git dbsherpa
cd dbsherpa

# 2 — Drop in your Gemini key
cp backend/.env.example backend/.env
$EDITOR backend/.env          # paste GEMINI_API_KEY=AIza…

# 3 — One script starts everything
./start.sh
# → Backend:  http://localhost:8000
# → Frontend: http://localhost:5173
# → Docs:     http://localhost:8000/docs
```

Smoke-test the bundled FX Front-Running demo (no API key required for
this path — just CSV fixtures):

```bash
curl -X POST http://localhost:8000/run/demo \
     -H 'Content-Type: application/json' \
     -d '{}' --output demo_report.xlsx
open demo_report.xlsx
```

---

## Prerequisites

| Tool     | Version | Notes                                          |
|----------|---------|------------------------------------------------|
| Python   | 3.11+   | Backend + engine                               |
| Node.js  | 20+     | Frontend build / dev server                    |
| Gemini   | API key | Required for Copilot + narrative summaries     |

---

## Repository layout

```
dbsherpa/
├── backend/           # FastAPI + pure engine + agent harness
├── frontend/          # React + Vite + ReactFlow UI
├── docs/              # ★ Engineering docs ★
│   ├── ONBOARDING.md              # Worked example — ship a new scenario
│   ├── BACKEND_ARCHITECTURE.md    # Authoritative backend reference
│   └── FRONTEND_ARCHITECTURE.md   # High-level frontend overview
├── start.sh           # One-shot dev launcher
└── README.md          # You are here
```

---

## Read next

| I want to…                                 | Go to                                                          |
|--------------------------------------------|----------------------------------------------------------------|
| Onboard a new scenario / dataset / signal  | [`docs/ONBOARDING.md`](docs/ONBOARDING.md)                     |
| Understand the backend deeply              | [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md) |
| Understand the frontend                    | [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md) |
| Deploy to Cloud Run                        | `backend/deploy/` and `frontend/deploy/`                       |
| See every OpenAPI route                    | `http://localhost:8000/docs` while the backend is running      |

---

## Running the tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v                   # 66 unit + integration tests
```

Frontend typecheck:

```bash
cd frontend
./node_modules/.bin/tsc --noEmit
```

See `docs/BACKEND_ARCHITECTURE.md §6 — Testing guide` for patterns
(handler tests, hard-rule tests, LLM-seam tests, golden-path runs).

---

## Status

- **66 backend tests green**, frontend typecheck green.
- Full Cloud Run deployment artifacts (`backend/deploy/`,
  `frontend/deploy/`).
- Copilot chat + streaming generation with edit-mode (deictic
  references to the selected canvas node).
- Five built-in surveillance scenarios shipped:
  FX front-running, FI wash, FI layering, FI spoofing, comms.
- Semantic column resolver is the next scheduled milestone — see
  `docs/BACKEND_ARCHITECTURE.md §3.9`.

---

## License

Proprietary. All rights reserved.
