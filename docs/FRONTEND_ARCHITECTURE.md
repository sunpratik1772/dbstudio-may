# Frontend Architecture (high-level)

> **Audience:** backend-focused engineers who occasionally touch the
> frontend, or new frontend engineers onboarding onto the project.
>
> **Scope:** the 5-minute mental model, not a component-by-component
> reference. For component-level docs, read the source — each top-level
> component has a comment block explaining its role.

---

## 0 — Junior engineer reading order (1 hour)

1. **`frontend/src/main.tsx`** + **`App.tsx`** — five-region layout.
   The diagram in App.tsx's docstring tells you which file owns which
   pixel.
2. **`frontend/src/store/workflowStore.ts`** — the only shared state.
   ~95% of cross-component data comes from here. Skim the section
   banners (PANE-SIZE, COPILOT, RUN STREAM, …) to learn the slices.
3. **`frontend/src/services/api.ts`** — every backend call lives here.
   One async fn per endpoint; streaming endpoints return async
   iterables of typed SSE events.
4. **`frontend/src/store/nodeRegistryStore.ts`** + **`nodes/index.ts`** —
   live node catalogue. The UI starts from generated fallback data, then
   refreshes from backend `GET /node-manifest` so new NodeSpecs and
   parameter changes appear without rebuilding the frontend.
5. **`frontend/src/components/WorkflowCanvas/index.tsx`** + **`CustomNode.tsx`**
   — React Flow wrapper + the visual node component. Run-status
   pulse, validation badges, drag-drop wiring all live here.
6. **`frontend/src/components/Topbar/index.tsx`** — the main action
   bar (run / save / validate / theme).
7. **`frontend/src/components/RightPanel/ConfigView.tsx`** — the active
   selected-node inspector. It renders docs and config fields from the
   live NodeSpec registry.
8. **`frontend/src/components/Copilot/index.tsx`** — the LLM author /
   editor. Read its docstring to understand how SSE events drive the
   progressive UI.

### Cheat sheet

| If you want to…                              | Open                                                  |
|----------------------------------------------|-------------------------------------------------------|
| Add a route call                             | `services/api.ts`                                     |
| Add a new piece of shared state              | A slice in `store/workflowStore.ts`                   |
| Add a node type to the palette               | Add backend NodeSpec YAML, then refresh `/node-manifest` |
| Style a node                                 | Update backend NodeSpec `ui`, then refresh Nodes      |
| Tweak a config form field                    | Backend YAML `params`, then refresh Nodes             |
| Tweak the canvas itself                      | `components/WorkflowCanvas/index.tsx`                 |
| Tweak run-time pulse / status                | `store/useNodeRunStatus.ts` + `CustomNode.tsx`        |

---

## 1 — Stack and conventions

- **Vite + React 18 + TypeScript** — strict mode on, no JS files.
- **Zustand** for state — one store, `useWorkflowStore`, in
  `src/store/workflowStore.ts`.
- **ReactFlow** for canvas (DAG rendering, drag/drop, connections).
- **Tailwind CSS** for styling. No CSS-in-JS.
- **lucide-react** for icons — the icon name strings you see in
  `NODE_SPEC.ui.icon` map directly.

No data fetching library (React Query, SWR, etc.) is used — calls are
orchestrated through `src/services/api.ts` and stored in Zustand.

Build:

```bash
cd frontend
npm install
npm run dev           # http://localhost:5173
npm run build         # typecheck + production bundle
./node_modules/.bin/tsc --noEmit   # typecheck only
```

---

## 2 — Directory layout

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── deploy/
│   ├── Dockerfile
│   └── nginx.conf              # SPA + SSE-safe reverse proxy
└── src/
    ├── main.tsx                # React entry
    ├── App.tsx                 # Shell layout (panes, topbar)
    ├── services/
    │   └── api.ts              # Single HTTP/SSE client; thin wrappers
    ├── store/
    │   ├── workflowStore.ts    # ★ workflow/canvas/run state ★
    │   └── nodeRegistryStore.ts # live NodeSpec manifest + generated fallback
    ├── types/                  # Shared TypeScript types
    ├── nodes/
    │   ├── generated.ts        # GENERATED fallback — palette + contracts
    │   ├── lucideIconMap.ts    # maps backend icon names to components
    │   └── index.ts            # facade over live registry helpers
    ├── styles/                 # Tailwind layers + global CSS
    └── components/
        ├── Topbar/             # Workflow title, save, run, validate
        ├── WorkflowDrawer/     # Left drawer: saved workflows + drafts
        ├── NodePanel/          # Left palette: draggable node types
        ├── WorkflowCanvas/     # ReactFlow canvas + custom nodes
        │   ├── CustomNode.tsx
        │   ├── NodeContextMenu.tsx
        │   └── useCanvasKeyboard.ts
        ├── ActivityRail.tsx    # toggles right-side modes
        ├── RightPanel/         # active config/run/output/copilot shell
        ├── Copilot/            # Right pane: chat + agent timeline
        └── ResizeHandle.tsx    # Drag-to-resize pane separator
```

---

## 3 — State model

There are two main Zustand stores:

- `useWorkflowStore` owns the current workflow, canvas selection, run
  stream, pane sizes, and right-panel state.
- `useNodeRegistryStore` owns the live NodeSpec catalogue loaded from
  `GET /node-manifest`, seeded by `nodes/generated.ts` as a fallback.

`useWorkflowStore` major slices:

| Slice                | Purpose                                                              |
|----------------------|----------------------------------------------------------------------|
| `workflow`           | Current `Workflow` — `nodes[]`, `edges[]`, metadata                  |
| `selectedNodeId`     | Drives the right-panel inspector and Copilot deictic references      |
| `validationIssues`   | Last result from `POST /validate`; drives red pills on canvas nodes  |
| `runLog`             | Live `RunLogEntry[]` appended by the SSE stream                      |
| `runResult`          | Final run result (disposition, report URL)                           |
| `rightPanelMode`     | Active right-side mode: config, copilot, runlog, output, or null      |
| `copilotDraft`       | One-shot text handoff into the Copilot input                          |
| Pane sizes           | `paletteWidth`, `copilotWidth`, persisted in localStorage                    |

Two conventions to know:

1. **Every node id follows `n01`, `n02`, … `nNN`.** The helper
   `_nextNodeId()` preserves this so the Copilot's references
   ("update n07") always resolve.
2. **Panes persist to `localStorage` under the key `dbsherpa:panes:v1`.**
   Each drag writes debounced. Sizes are clamped to the
   `PANE_LIMITS` object.
3. **Node metadata is not owned by the workflow.** A node stores its
   `type`; color, icon, parameters, docs, and palette section come from
   `useNodeRegistryStore`.

---

## 4 — Data flow

```
          ┌────────────────────────────────────────────┐
          │                  App.tsx                   │
          │   ┌───────────┐    ┌────────────────────┐  │
          │   │  Palette  │    │                    │  │
          │   │  Drawer   │    │  WorkflowCanvas    │  │
          │   │  Topbar   │    │  (ReactFlow)       │  │
          │   │  Actions  │    │                    │  │
          │   └───────────┘    └────────────────────┘  │
          │   ┌───────────────┐ ┌───────────────────┐ │
          │   │ ActivityRail  │ │ RightPanel        │ │
          │   │ mode toggles  │ │ config/run/output │ │
          │   └───────────────┘ └───────────────────┘ │
          └──────────────────┬─────────────────────────┘
                             │
            useWorkflowStore(selector) — reads & writes
                             │
                     services/api.ts
                 ┌───────────┼───────────┐
              fetch        EventSource   EventSource
              (JSON)       (/copilot)    (/run/stream)
                             │
                        backend (FastAPI)
```

1. **App boot** calls `useNodeRegistryStore.refreshFromBackend()`.
   Palette sections, node docs, colors, contracts, and typed params come
   from backend `GET /node-manifest`; `generated.ts` is only fallback.
2. **Palette drag** drops a new node by type. The new node's label and
   UI metadata are looked up from the live registry.
3. **Edit in canvas / right-panel config** mutates `workflow` in the store.
4. **Validate** (shield icon in `Topbar`) sends `workflow` to `POST
   /validate`, stores `validationIssues`, and turns green/red for the
   current workflow revision.
5. **Run** opens an SSE to `/run/stream`. Each frame is parsed in
   `services/api.ts` and pushed through `workflowStore.applyRunEvent`;
   Canvas, RunLogView, and OutputView all derive from that store state.
6. **Copilot generate** opens an SSE to `/copilot/generate/stream`.
   Frames are `understanding`, `planning`, `generating`,
   `auto_fixing`, `critiquing`, `finalizing`, `complete`, or `error`.
   The right pane renders the timeline. Greenfield prompts replace the
   canvas only after validation succeeds; explicit edit/fix prompts
   attach the current canvas for targeted repair.

---

## 5 — Node manifest — how the frontend knows about nodes

The frontend **does not** share Python types with the backend. The
runtime source of truth is:

```text
backend NodeSpec YAML + handlers
        ↓ engine.registry.studio_manifest()
GET /node-manifest
        ↓ useNodeRegistryStore.refreshFromBackend()
NodePanel, ConfigView, CustomNode, RunLogView, OutputView
```

`backend/scripts/gen_artifacts.py` still writes `nodes/generated.ts`,
but it is now a cold-start/offline fallback, not the normal runtime data
path:

```ts
// frontend/src/nodes/generated.ts  (GENERATED fallback, do not hand-edit)
export const NODE_UI = { ALERT_TRIGGER: { color: "...", Icon: Siren, ... } }
export const NODE_TYPED = {
  ALERT_TRIGGER: {
    inputPorts: [...],
    outputPorts: [...],
    params: [{ name: "alert_fields", type: "object", widget: "json", ... }],
  },
}
```

Components should import from `src/nodes/` or `useNodeRegistryStore`:

- `NodePanel` renders the palette from `nodeTypes`, `nodeUI`, and
  `paletteSections`.
- `ConfigView` renders the right editor widget for each param
  based on `widget` (`text`, `textarea`, `number`, `checkbox`,
  `select`, `chips`, `json`, `input_ref`, `code`).
- `CustomNode`, RunLog, and Output views pick color + icon from live
  `nodeUI`.

If backend adds a node or changes a parameter, restart/refresh the
backend registry and click **Nodes** in the topbar (or reload the app).
The frontend bundle does not need to be rebuilt for normal manifest
changes. Run `gen_artifacts.py` only when you want the checked-in
fallback artifact to match the backend.

---

## 6 — Copilot integration

The Copilot has three backend surfaces:

| Endpoint                      | Purpose                                      | Frontend consumer            |
|-------------------------------|----------------------------------------------|------------------------------|
| `POST /copilot/chat`          | Free-form chat turn                          | `services/api.ts:copilotChat` |
| `POST /copilot/generate`      | Blocking: prompt → workflow                  | rarely used directly          |
| `POST /copilot/generate/stream` | SSE: agent events + final workflow         | `actions.copilotStream()`     |

"Edit mode" is what the frontend sends when the user is refining an
existing workflow (rather than generating from scratch):

```
{
  "prompt": "Remove the spoofing signal from n07 and add a volume filter.",
  "history": [...],
  "mode": "edit",
  "context": {
    "workflow": <current JSON>,
    "selected_node_id": "n07",
    "recent_errors": ["…"]
  }
}
```

The Copilot prompt builder on the backend injects that context so
"this" and "here" in the user's prompt resolve to the selected node.
See `backend/copilot/workflow_generator.py`.

---

## 7 — Running the canvas against the backend

Local end-to-end:

```bash
./start.sh                 # starts backend on :8000 and frontend on :5173
open http://localhost:5173
```

CORS is open (`allow_origins=["*"]`) at dev time; the nginx config in
`frontend/deploy/nginx.conf` reverse-proxies `/api/*` to the backend in
production.

SSE gotchas:

- nginx's `proxy_buffering off` and `X-Accel-Buffering: no` are set.
  If you deploy behind a different reverse proxy, replicate those.
- The EventSource API does not send custom headers. Auth (when it
  lands) must live in cookies or query strings.

---

## 8 — Testing (frontend)

Today there is no unit-test suite on the frontend. We rely on:

1. `./node_modules/.bin/tsc --noEmit` — strict typecheck on every PR.
2. Manual smoke in the browser against the running backend.
3. Backend `test_copilot_edit_mode.py` — verifies that the data the
   frontend sends for edit-mode is correctly consumed.

Adding Vitest + React Testing Library is on the roadmap; when it
lands, tests live alongside components (`FooBar.test.tsx`).

---

## 9 — Conventions / house rules

1. **Store is the only mutable state.** No component-level module-scope
   mutable globals.
2. **One component per file**, named-default-exported.
3. **Tailwind first**, custom CSS only for things Tailwind can't do
   (resize handles, ReactFlow selection states).
4. **Icons come from lucide-react.** Don't install a second icon
   library.
5. **No direct `fetch` in components.** Route everything through
   `services/api.ts` so HTTP concerns (base URL, SSE, error handling)
   stay in one place.
6. **Deictic Copilot references** (`this`, `here`) require
   `selectedNodeId` — always include it when calling
   `copilotStream({ mode: 'edit', ... })`.
7. **Generated code is never edited by hand** — always regenerate from
   the backend.

---

## 10 — Deployment

See `frontend/deploy/`:

- `Dockerfile` — two stages: Node build, nginx runtime.
- `nginx.conf` — SPA fallback, long-lived SSE, gzip/brotli for static
  assets, cache headers.

Environment:

- `VITE_API_BASE_URL` — backend URL. In dev, falls back to
  `http://localhost:8000`. In production, typically an empty string
  (so `/api/*` hits the same host and nginx reverse-proxies).

---

For anything deeper — component responsibilities, the Copilot timeline
rendering, the ReactFlow custom edge style — read the source. The
component folders are small and each has a single well-named entry
file.
