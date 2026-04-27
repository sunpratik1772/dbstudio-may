/**
 * The single Zustand store that owns the workflow editor's runtime state.
 *
 * Anything that needs to be shared across panels (Topbar, Canvas,
 * Copilot, RightPanel) lives here. State is split into
 * cohesive slices — read the section banners (PANE-SIZE PERSISTENCE,
 * COPILOT, RUN STREAM, etc.) to find the right slice quickly.
 *
 * Architectural notes for newcomers:
 *
 *   • The store is mutated through *actions* declared on the same
 *     object — `setWorkflow`, `addNode`, `updateNode`, etc. Components
 *     never mutate state directly; that keeps undo/redo and selectors
 *     trivial.
 *   • Pane sizes persist to localStorage so a reload doesn't reset
 *     the user's layout. The clamping helpers stop bad values
 *     (NaN / negative) from sneaking in across versions.
 *   • Run state is kept here rather than in a separate hook because
 *     SSE events arrive from the backend out-of-band (no React event)
 *     — funnelling them through a Zustand action means every panel
 *     re-renders consistently.
 *   • Copilot state is also here so the right-panel chat survives
 *     navigation between workflows.
 *   • Right panel: `rightPanelMode` is the live shell state controlled
 *     by ActivityRail. Old bottom-drawer state was removed; if you are
 *     changing which right column is visible, use `rightPanelMode`.
 *
 * Tip: when you grep for "where does X come from?", search the store
 * first. ~95% of cross-component state is here.
 */
import { create } from 'zustand'
import type {
  Workflow,
  WorkflowNode,
  NodeType,
  RunResult,
  CopilotMessage,
  RunLogEntry,
  RunWorkflowStreamEvent,
  ValidationIssue,
} from '../types'
import { getNodeDisplayName } from '../nodes'

/** Auto-generate a new unique node id, honouring the "n01", "n02" scheme used by existing workflows. */
function _nextNodeId(existing: WorkflowNode[]): string {
  let n = 1
  const seen = new Set(existing.map((x) => x.id))
  while (seen.has(`n${String(n).padStart(2, '0')}`)) n++
  return `n${String(n).padStart(2, '0')}`
}

/** Human-friendly default label for a freshly-dropped node. */
function _defaultLabel(type: NodeType, existing: WorkflowNode[]): string {
  const base = getNodeDisplayName(type)
  const sameType = existing.filter((n) => n.type === type).length
  return sameType > 0 ? `${base} ${sameType + 1}` : base
}

/* ------------------------------------------------------------------ */
/* Pane-size persistence                                              */
/*                                                                    */
/* VSCode / Cursor-style: we keep the last width/height the user      */
/* dragged to in localStorage so reloading the page doesn't reset the */
/* workspace layout. Clamped to sensible ranges.                      */
/* ------------------------------------------------------------------ */
export const PANE_LIMITS = {
  paletteWidth:     { min: 180, max: 420, def: 224 },
  copilotWidth:     { min: 280, max: 640, def: 360 },
} as const

const _PANE_KEY = 'dbsherpa:panes:v1'
type PaneSizes = { paletteWidth: number; copilotWidth: number }

function _clamp(v: number, min: number, max: number): number {
  if (Number.isNaN(v)) return min
  return Math.min(max, Math.max(min, Math.round(v)))
}

function _readPaneSizes(): PaneSizes {
  const defaults = {
    paletteWidth: PANE_LIMITS.paletteWidth.def,
    copilotWidth: PANE_LIMITS.copilotWidth.def,
  }
  if (typeof window === 'undefined') return defaults
  try {
    const raw = window.localStorage.getItem(_PANE_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw) as Partial<PaneSizes>
    return {
      paletteWidth: _clamp(parsed.paletteWidth ?? defaults.paletteWidth, PANE_LIMITS.paletteWidth.min, PANE_LIMITS.paletteWidth.max),
      copilotWidth: _clamp(parsed.copilotWidth ?? defaults.copilotWidth, PANE_LIMITS.copilotWidth.min, PANE_LIMITS.copilotWidth.max),
    }
  } catch {
    return defaults
  }
}

function _writePaneSizes(sizes: PaneSizes): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(_PANE_KEY, JSON.stringify(sizes))
  } catch {
    /* swallow quota / safari-private errors */
  }
}

export type RightPanelMode = 'config' | 'runlog' | 'output' | 'copilot' | null

/**
 * Minimum time a node must visibly be in 'running' state before the UI is
 * allowed to transition it to 'ok' / 'error'. Without this, fast nodes
 * (mock data, pandas on a few hundred rows) flip start→complete inside a
 * single React batch and the run-ring never paints.
 */
const MIN_NODE_DWELL_MS = 450

/**
 * Where the on-disk version of the current workflow lives:
 *
 *   'saved' → user has explicitly named and promoted this workflow;
 *             changes auto-save to /workflows/{filename}.
 *   'draft' → Copilot generated it OR user is still building; changes
 *             auto-save to /drafts/{filename}. Promote to 'saved' via
 *             the Save-As button.
 *   null    → ephemeral in-memory workflow (hasn't been persisted yet).
 */
export type WorkflowSource = 'saved' | 'draft' | null

interface WorkflowStore {
  workflow: Workflow | null
  /**
   * Filename backing the current workflow on disk. `null` when the workflow
   * is ephemeral (just created, not yet auto-saved).
   */
  sourceFilename: string | null
  /** Which store the `sourceFilename` lives in — saved or draft. */
  sourceKind: WorkflowSource
  setWorkflow: (w: Workflow) => void
  /** Load a workflow that came from an on-disk file; flips the UI into Edit mode. */
  loadWorkflowFromFile: (filename: string, w: Workflow) => void
  /** Load a draft from disk (drawer click on a draft). */
  loadDraftFromFile: (filename: string, w: Workflow) => void
  /** Called by the autosave hook once a workflow has a backing draft file. */
  setDraftFilename: (filename: string) => void
  /** Called by Save-As when a draft is promoted to a saved workflow. */
  markSaved: (filename: string) => void
  /** Clear the canvas and unload any saved/draft workflow identity. */
  newBlankWorkflow: () => void
  clearWorkflow: () => void
  /** Add a new node (e.g. from a palette drop). Creates a stub workflow if none is loaded. Returns the new node id. */
  addNode: (type: NodeType, position: { x: number; y: number }) => string
  /** Persist the current canvas position of a node onto the workflow. */
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void
  /** Patch a node's config (shallow merge). Use `null` to remove a key. */
  updateNodeConfig: (nodeId: string, patch: Record<string, unknown>) => void
  /** Replace a node's display label. */
  renameNode: (nodeId: string, label: string) => void

  /* --- n8n-style canvas ops -------------------------------------------- */
  /** Remove one or more nodes AND any edges referencing them. */
  deleteNodes: (nodeIds: string[]) => void
  /** Remove a single edge between two nodes. */
  deleteEdge: (fromId: string, toId: string) => void
  /** Clone nodes (deep copy of config) with new ids and a positional offset. Returns the new ids. */
  duplicateNodes: (nodeIds: string[], offset?: { x: number; y: number }) => string[]
  /** Toggle the `disabled` flag on a node — used to grey it out and skip at runtime. */
  toggleNodeDisabled: (nodeId: string) => void

  workflowDrawerOpen: boolean
  setWorkflowDrawerOpen: (v: boolean) => void

  /* --- Pane sizing (VSCode-style draggable splitters) ------------------ */
  paletteWidth: number        // left palette width (px)
  copilotWidth: number        // unified right panel width (px)
  setPaletteWidth: (px: number) => void
  setCopilotWidth: (px: number) => void

  isRunning: boolean
  runResult: RunResult | null
  runError: string | null
  /** Structured per-node issues emitted by the pre-flight validator.
   *  Populated by `workflow_error` SSE frames and by catching
   *  ValidationError on the blocking run path. Null when the last run
   *  failed for a non-validation reason. */
  validationIssues: ValidationIssue[] | null
  /** Non-blocking warnings that accompanied a successful run. */
  runWarnings: ValidationIssue[] | null
  runLog: RunLogEntry[]
  runTotalMs: number | null
  setRunning: (v: boolean) => void
  setRunResult: (r: RunResult | null) => void
  setRunError: (e: string | null) => void
  setValidationIssues: (issues: ValidationIssue[] | null) => void
  resetRun: () => void
  applyRunEvent: (ev: RunWorkflowStreamEvent) => void

  selectedNodeId: string | null
  selectNode: (id: string | null) => void

  copilotMessages: CopilotMessage[]
  addCopilotMessage: (msg: CopilotMessage) => void
  clearCopilotMessages: () => void

  /**
   * Which view (if any) the unified right-side panel is showing.
   * `null` collapses the panel down to just the activity rail.
   * Driven by the ActivityRail buttons — clicking the active mode
   * toggles back to `null`.
   */
  rightPanelMode: RightPanelMode
  setRightPanelMode: (m: RightPanelMode) => void
  toggleRightPanelMode: (m: RightPanelMode) => void

  /**
   * Pending text that the Copilot input should pick up on next mount /
   * re-render. Used by "Fix with Copilot" CTAs in the topbar so they
   * can cross-component hand off a prefilled prompt without direct
   * DOM access. The Copilot consumes it into local state and calls
   * `setCopilotDraft(null)` to clear.
   */
  copilotDraft: string | null
  setCopilotDraft: (v: string | null) => void
}

/* ------------------------------------------------------------------ */
/* Streaming-event queue                                              */
/*                                                                    */
/* Events are applied to the store serially so a deferred             */
/* node_complete can't be visually overtaken by the next node_start.  */
/* ------------------------------------------------------------------ */
const _queue: RunWorkflowStreamEvent[] = []
let _draining = false
// Tracks the wall-clock time (frontend) at which node_start was APPLIED to
// the UI, keyed by node_id. Backend's `started_at` can be 100s of ms old by
// the time events traverse the SSE pipe, so we can't use it for dwell math.
const _uiStartedAt = new Map<string, number>()

function _sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function _drain(): Promise<void> {
  if (_draining) return
  _draining = true
  try {
    while (_queue.length > 0) {
      const ev = _queue[0]

      // Hold node_complete / node_error until the running state has been
      // visible (applied to the UI) for at least MIN_NODE_DWELL_MS.
      if (ev.type === 'node_complete' || ev.type === 'node_error') {
        const uiStart = ev.node_id ? _uiStartedAt.get(ev.node_id) : undefined
        if (uiStart != null) {
          const elapsed = Date.now() - uiStart
          const remaining = MIN_NODE_DWELL_MS - elapsed
          if (remaining > 0) await _sleep(remaining)
        }
      }

      _queue.shift()
      _applyNow(ev)
    }
  } finally {
    _draining = false
  }
}

function _applyNow(ev: RunWorkflowStreamEvent): void {
  useWorkflowStore.setState((s) => {
    switch (ev.type) {
      case 'workflow_start':
        _uiStartedAt.clear()
        return {
          runLog: [],
          runResult: null,
          runError: null,
          runTotalMs: null,
          validationIssues: null,
          runWarnings: null,
        }
      case 'node_start': {
        if (!ev.node_id) return {}
        // Anchor dwell + live counter on frontend clock so the running
        // state is visible even when the backend finishes in <1ms.
        const nowIso = new Date().toISOString()
        _uiStartedAt.set(ev.node_id, Date.now())
        const entry: RunLogEntry = {
          node_id: ev.node_id,
          node_type: ev.node_type || '',
          label: ev.label || ev.node_id,
          index: ev.index ?? s.runLog.length + 1,
          total: ev.total ?? 0,
          status: 'running',
          started_at: nowIso,
        }
        return { runLog: [...s.runLog, entry] }
      }
      case 'node_complete':
      case 'node_error': {
        if (!ev.node_id) return {}
        _uiStartedAt.delete(ev.node_id)
        const idx = s.runLog.findIndex(
          (e) => e.node_id === ev.node_id && e.status === 'running',
        )
        if (idx < 0) return {}
        const log = [...s.runLog]
        log[idx] = {
          ...log[idx],
          status: ev.type === 'node_complete' ? 'ok' : 'error',
          duration_ms: ev.duration_ms,
          output: ev.output,
          error: ev.error,
          trace: ev.trace,
        }
        return { runLog: log }
      }
      case 'workflow_complete':
        return {
          runResult: ev.result ?? null,
          runTotalMs: ev.total_duration_ms ?? null,
          runWarnings: ev.warnings ?? ev.result?.warnings ?? null,
        }
      case 'workflow_error': {
        // Surface structured validation failures alongside the flat
        // error string so the UI can render per-node issues.
        const validation = ev.validation
        const message = validation
          ? `${validation.errors.length} validation error(s): ${validation.errors.map((e) => e.code).join(', ')}`
          : ev.error ?? 'Workflow error'
        return {
          runError: message,
          validationIssues: validation?.errors ?? null,
          runWarnings: validation?.warnings ?? null,
        }
      }
      default:
        return {}
    }
  })
}

function _enqueue(ev: RunWorkflowStreamEvent): void {
  // On a fresh run, flush any leftover events from a prior run that were
  // still waiting in the dwell queue.
  if (ev.type === 'workflow_start') _queue.length = 0
  _queue.push(ev)
  void _drain()
}

/* ------------------------------------------------------------------ */

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  workflow: null,
  sourceFilename: null,
  sourceKind: null,
  // Keep setWorkflow "honest": if you hand us a workflow without a filename
  // context, we treat it as a fresh create. The autosave hook will pick it
  // up and persist it as a draft on the next tick.
  setWorkflow: (w) => set({ workflow: w, sourceFilename: null, sourceKind: null }),
  loadWorkflowFromFile: (filename, w) =>
    set({ workflow: w, sourceFilename: filename, sourceKind: 'saved' }),
  loadDraftFromFile: (filename, w) =>
    set({ workflow: w, sourceFilename: filename, sourceKind: 'draft' }),
  setDraftFilename: (filename) =>
    set({ sourceFilename: filename, sourceKind: 'draft' }),
  markSaved: (filename) =>
    set({ sourceFilename: filename, sourceKind: 'saved' }),
  newBlankWorkflow: () =>
    set({
      workflow: null,
      sourceFilename: null,
      sourceKind: null,
      runResult: null,
      runError: null,
      runLog: [],
      runTotalMs: null,
      selectedNodeId: null,
    }),
  clearWorkflow: () => {
    _queue.length = 0
    _uiStartedAt.clear()
    set({
      workflow: null,
      sourceFilename: null,
      sourceKind: null,
      selectedNodeId: null,
      runResult: null,
      runError: null,
      runLog: [],
      runTotalMs: null,
      validationIssues: null,
      runWarnings: null,
      isRunning: false,
    })
  },

  workflowDrawerOpen: false,
  setWorkflowDrawerOpen: (v) => set({ workflowDrawerOpen: v }),

  /* Pane sizes — hydrated from localStorage so the user's layout sticks. */
  ...(() => {
    const s = _readPaneSizes()
    return {
      paletteWidth: s.paletteWidth,
      copilotWidth: s.copilotWidth,
    }
  })(),
  setPaletteWidth: (px) =>
    set((s) => {
      const next = _clamp(px, PANE_LIMITS.paletteWidth.min, PANE_LIMITS.paletteWidth.max)
      _writePaneSizes({
        paletteWidth: next,
        copilotWidth: s.copilotWidth,
      })
      return { paletteWidth: next }
    }),
  setCopilotWidth: (px) =>
    set((s) => {
      const next = _clamp(px, PANE_LIMITS.copilotWidth.min, PANE_LIMITS.copilotWidth.max)
      _writePaneSizes({
        paletteWidth: s.paletteWidth,
        copilotWidth: next,
      })
      return { copilotWidth: next }
    }),

  addNode: (type, position) => {
    let newId = ''
    set((s) => {
      const existingNodes = s.workflow?.nodes ?? []
      newId = _nextNodeId(existingNodes)
      const newNode: WorkflowNode = {
        id: newId,
        type,
        label: _defaultLabel(type, existingNodes),
        config: {},
        position,
      }
      const base: Workflow = s.workflow ?? {
        workflow_id: 'untitled',
        name: 'Untitled workflow',
        version: '0.1.0',
        description: '',
        nodes: [],
        edges: [],
      }
      return { workflow: { ...base, nodes: [...base.nodes, newNode] } }
    })
    return newId
  },

  updateNodePosition: (nodeId, position) =>
    set((s) => {
      if (!s.workflow) return {}
      const nodes = s.workflow.nodes.map((n) => (n.id === nodeId ? { ...n, position } : n))
      return { workflow: { ...s.workflow, nodes } }
    }),

  updateNodeConfig: (nodeId, patch) =>
    set((s) => {
      if (!s.workflow) return {}
      const nodes = s.workflow.nodes.map((n) => {
        if (n.id !== nodeId) return n
        // Merge, dropping any keys explicitly set to null so users can clear.
        const merged: Record<string, unknown> = { ...(n.config ?? {}), ...patch }
        for (const [k, v] of Object.entries(patch)) {
          if (v === null || v === undefined) delete merged[k]
        }
        return { ...n, config: merged }
      })
      return { workflow: { ...s.workflow, nodes } }
    }),

  renameNode: (nodeId, label) =>
    set((s) => {
      if (!s.workflow) return {}
      const nodes = s.workflow.nodes.map((n) => (n.id === nodeId ? { ...n, label } : n))
      return { workflow: { ...s.workflow, nodes } }
    }),

  deleteNodes: (nodeIds) =>
    set((s) => {
      if (!s.workflow || nodeIds.length === 0) return {}
      const drop = new Set(nodeIds)
      const nodes = s.workflow.nodes.filter((n) => !drop.has(n.id))
      const edges = s.workflow.edges.filter((e) => !drop.has(e.from) && !drop.has(e.to))
      const selectedNodeId = s.selectedNodeId && drop.has(s.selectedNodeId) ? null : s.selectedNodeId
      return { workflow: { ...s.workflow, nodes, edges }, selectedNodeId }
    }),

  deleteEdge: (fromId, toId) =>
    set((s) => {
      if (!s.workflow) return {}
      const edges = s.workflow.edges.filter((e) => !(e.from === fromId && e.to === toId))
      return { workflow: { ...s.workflow, edges } }
    }),

  duplicateNodes: (nodeIds, offset = { x: 40, y: 40 }) => {
    const newIds: string[] = []
    set((s) => {
      if (!s.workflow || nodeIds.length === 0) return {}
      const keep = new Set(nodeIds)
      const sourceNodes = s.workflow.nodes.filter((n) => keep.has(n.id))
      if (sourceNodes.length === 0) return {}

      // Build id mapping first so intra-selection edges can be cloned too.
      const working: WorkflowNode[] = [...s.workflow.nodes]
      const idMap = new Map<string, string>()
      for (const src of sourceNodes) {
        const newId = _nextNodeId(working)
        idMap.set(src.id, newId)
        const clone: WorkflowNode = {
          ...src,
          id: newId,
          label: `${src.label} (copy)`,
          config: JSON.parse(JSON.stringify(src.config ?? {})),
          position: src.position
            ? { x: src.position.x + offset.x, y: src.position.y + offset.y }
            : undefined,
        }
        working.push(clone)
        newIds.push(newId)
      }

      // Clone edges where BOTH endpoints are in the duplicated set.
      const clonedEdges = s.workflow.edges
        .filter((e) => idMap.has(e.from) && idMap.has(e.to))
        .map((e) => ({ from: idMap.get(e.from)!, to: idMap.get(e.to)! }))

      return {
        workflow: {
          ...s.workflow,
          nodes: working,
          edges: [...s.workflow.edges, ...clonedEdges],
        },
      }
    })
    return newIds
  },

  toggleNodeDisabled: (nodeId) =>
    set((s) => {
      if (!s.workflow) return {}
      const nodes = s.workflow.nodes.map((n) =>
        n.id === nodeId ? { ...n, disabled: !n.disabled } : n,
      )
      return { workflow: { ...s.workflow, nodes } }
    }),

  isRunning: false,
  runResult: null,
  runError: null,
  validationIssues: null,
  runWarnings: null,
  runLog: [],
  runTotalMs: null,
  setRunning: (v) => set({ isRunning: v }),
  setRunResult: (r) => set({ runResult: r }),
  setRunError: (e) => set({ runError: e }),
  setValidationIssues: (issues) => set({ validationIssues: issues }),
  resetRun: () => {
    _queue.length = 0
    _uiStartedAt.clear()
    set({
      runResult: null,
      runError: null,
      runLog: [],
      runTotalMs: null,
      validationIssues: null,
      runWarnings: null,
    })
  },

  applyRunEvent: (ev) => _enqueue(ev),

  selectedNodeId: null,
  selectNode: (id) => set({ selectedNodeId: id }),

  copilotMessages: [],
  addCopilotMessage: (msg) => set((s) => ({ copilotMessages: [...s.copilotMessages, msg] })),
  clearCopilotMessages: () => set({ copilotMessages: [] }),

  rightPanelMode: 'copilot',
  setRightPanelMode: (m) => set({ rightPanelMode: m }),
  toggleRightPanelMode: (m) =>
    set((s) => {
      const next = s.rightPanelMode === m ? null : m
      return { rightPanelMode: next }
    }),

  copilotDraft: null,
  setCopilotDraft: (v) => set({ copilotDraft: v }),
}))
