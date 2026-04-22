# Frontend Architecture (high-level)

> **Audience:** backend-focused engineers who occasionally touch the
> frontend, or new frontend engineers onboarding onto the project.
>
> **Scope:** the 5-minute mental model, not a component-by-component
> reference. For component-level docs, read the source — each top-level
> component has a comment block explaining its role.

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
    │   └── workflowStore.ts    # ★ Zustand store — all app state ★
    ├── types/                  # Shared TypeScript types
    ├── nodes/
    │   ├── generated.ts        # GENERATED — palette + contracts
    │   └── index.ts
    ├── styles/                 # Tailwind layers + global CSS
    └── components/
        ├── Topbar/             # Workflow title, save, run, validate
        ├── WorkflowDrawer/     # Left drawer: saved workflows + drafts
        ├── NodePanel/          # Left palette: draggable node types
        ├── WorkflowCanvas/     # ReactFlow canvas + custom nodes
        │   ├── CustomNode.tsx
        │   ├── NodeContextMenu.tsx
        │   └── useCanvasKeyboard.ts
        ├── NodeConfig/         # Bottom drawer: selected-node editor
        │   └── ConfigInspector.tsx
        ├── WorkflowActions/    # Validate / Run / Save / Promote
        ├── Copilot/            # Right pane: chat + agent timeline
        ├── RunConsole/         # SSE log viewer (n8n-style)
        └── ResizeHandle.tsx    # Drag-to-resize pane separator
```

---

## 3 — State model

There is one store, accessed via `useWorkflowStore(selector)`. Its
major slices:

| Slice                | Purpose                                                              |
|----------------------|----------------------------------------------------------------------|
| `workflow`           | Current `Workflow` — `nodes[]`, `edges[]`, metadata                  |
| `selectedNodeId`     | Drives the `NodeConfig` drawer and Copilot deictic references        |
| `validationIssues`   | Last result from `POST /validate`; drives red pills on canvas nodes  |
| `runLog`             | Live `RunLogEntry[]` appended by the SSE stream                      |
| `runResult`          | Final run result (disposition, report URL)                           |
| `copilotOpen`        | Right pane visibility                                                 |
| `copilotDraft`       | Live-streaming Copilot reply before commit                           |
| `copilotHistory`     | Persisted chat turns (sent to `/copilot/chat`)                       |
| Pane sizes           | `paletteWidth`, `copilotWidth`, `nodeConfigHeight`, persisted in localStorage |

Two conventions to know:

1. **Every node id follows `n01`, `n02`, … `nNN`.** The helper
   `_nextNodeId()` preserves this so the Copilot's references
   ("update n07") always resolve.
2. **Panes persist to `localStorage` under the key `dbsherpa:panes:v1`.**
   Each drag writes debounced. Sizes are clamped to the
   `PANE_LIMITS` object.

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
          │   ┌────────────────────────┐  ┌─────────┐  │
          │   │   NodeConfig drawer    │  │ Copilot │  │
          │   │   (bottom, dockable)   │  │  pane   │  │
          │   └────────────────────────┘  └─────────┘  │
          │              RunConsole (SSE)              │
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

1. **Palette drag** drops a new node with a `NODE_SPEC`-derived default
   config. The source of truth is `src/nodes/generated.ts`, produced by
   `python backend/scripts/gen_artifacts.py`.
2. **Edit in canvas / config drawer** mutates `workflow` in the store.
3. **Validate** (`actions.validate()`) sends `workflow` to `POST
   /validate`, stores `validationIssues`. Red pills light up on the
   canvas.
4. **Run** (`actions.runStream()`) opens an SSE to `/run/stream`. Each
   frame is pushed into `runLog`; the `RunConsole` renders them as an
   n8n-style live log with the currently-running node highlighted.
5. **Copilot generate** (`actions.copilotStream(prompt)`) opens an SSE
   to `/copilot/generate/stream`. Frames are `understanding`,
   `planning`, `validation`, `auto_fixing`, `success`, `failed`. The
   right pane renders the timeline; the final workflow payload is
   merged into the canvas in "edit mode" if the user is refining an
   existing workflow.

---

## 5 — The generated artifact — how the frontend knows about nodes

The frontend **does not** share Python types with the backend. Instead,
`backend/scripts/gen_artifacts.py` writes:

```ts
// frontend/src/nodes/generated.ts  (GENERATED, do not hand-edit)
export const NODE_DEFINITIONS = [
  {
    type_id: "ALERT_TRIGGER",
    description: "Entry point — binds alert payload to context",
    color: "#7C3AED",
    icon: "Siren",
    config_tags: [],
    input_ports:  [ { name: "alert_payload", type: "object", ... } ],
    output_ports: [ { name: "context_keys", type: "object", ... } ],
    params:       [ { name: "alert_fields", type: "object", widget: "json", ... } ],
  },
  // …
] as const;
```

Components import from `src/nodes/`:

- `NodePanel` renders the palette from `NODE_DEFINITIONS`.
- `ConfigInspector` renders the right editor widget for each param
  based on `widget` (`text`, `textarea`, `number`, `checkbox`,
  `select`, `chips`, `json`, `input_ref`, `code`).
- `CustomNode` in the canvas picks its color + icon from this file.

**This is why `scripts/gen_artifacts.py` must run after every
backend `NODE_SPEC` change.**

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
