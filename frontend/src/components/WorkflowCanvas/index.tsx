/**
 * The DAG editing canvas — wraps React Flow.
 *
 * Responsibilities:
 *   • Render every workflow node with `<CustomNode />` (sibling file).
 *   • Translate React Flow events (drag, drop, connect, delete, select)
 *     back into workflowStore actions.
 *   • Accept palette drops via HTML5 DnD — when a NodePanel item is
 *     dropped onto the canvas, we compute the world coordinates and
 *     call `addNode(type, position)`.
 *   • Show validation errors as red badges on the offending node,
 *     pulling from `useWorkflowStore.getState().validationIssues`.
 *
 * Nothing here knows the schema of a specific node type — palette
 * metadata comes from `nodeRegistryStore` (backend node-manifest).
 */
import { useCallback, useMemo, useRef, useState, type DragEvent } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
  type NodeDragHandler,
  type OnSelectionChangeParams,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
} from 'reactflow'
import 'reactflow/dist/style.css'

// (icons used in empty state are inline below)
import { CustomNode } from './CustomNode'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, type NodeType } from '../../nodes'
import type { RunLogEntry } from '../../types'
import { useCanvasKeyboard } from './useCanvasKeyboard'
import NodeContextMenu, { type ContextMenuState } from './NodeContextMenu'

const nodeTypes = { custom: CustomNode }
/** MIME the palette uses for drag payloads; also duplicated as text/plain for Safari. */
export const PALETTE_DND_MIME = 'application/x-dbsherpa-node'

// Column / row spacing in flow-space pixels. Tuned so a ~280px-wide
// node card + ~150px-tall stack reads as "columns of stages" rather
// than a dense grid.
const COL_WIDTH = 300
const ROW_HEIGHT = 160
const CANVAS_PAD_X = 60
const CANVAS_PAD_Y = 60

type WorkflowShape = NonNullable<ReturnType<typeof useWorkflowStore.getState>['workflow']>

/**
 * Layered (Sugiyama-style) layout for the DAG.
 *
 * Column = longest-path depth from any root (node with no incoming
 *   edges). This matches how an analyst thinks about execution order:
 *   "stage 1 collects, stage 2 enriches, stage 3 signals, …" — and
 *   mirrors how n8n / Temporal / Airflow render their pipelines.
 *
 * Row    = within a column, order nodes by the average row of their
 *   parents in the previous column (the classic "barycenter"
 *   heuristic). That pulls each node close to whatever fed it and
 *   massively reduces edge crossings vs. insertion order.
 *
 * Tie-breakers preserve original `workflow.nodes` ordering so the
 * layout is stable across reloads — otherwise the canvas jumps
 * around every time Copilot regenerates a workflow.
 */
function layoutByTopology(workflow: WorkflowShape): Map<string, { x: number; y: number }> {
  const nodeIds = workflow.nodes.map((n) => n.id)
  const orderIndex = new Map(nodeIds.map((id, i) => [id, i]))
  const parents = new Map<string, string[]>(nodeIds.map((id) => [id, []]))
  const children = new Map<string, string[]>(nodeIds.map((id) => [id, []]))
  for (const e of workflow.edges) {
    if (!parents.has(e.to) || !children.has(e.from)) continue
    parents.get(e.to)!.push(e.from)
    children.get(e.from)!.push(e.to)
  }

  // Kahn's algorithm with depth accumulation. Longest-path depth
  // (not shortest) keeps fan-in nodes from being pulled left of
  // their siblings — e.g. REPORT_OUTPUT stays at the rightmost
  // column even though ALERT_TRIGGER has a direct edge to it.
  const indegree = new Map<string, number>(nodeIds.map((id) => [id, parents.get(id)!.length]))
  const depth = new Map<string, number>(nodeIds.map((id) => [id, 0]))
  const queue: string[] = nodeIds.filter((id) => indegree.get(id) === 0)
  while (queue.length) {
    const u = queue.shift()!
    const du = depth.get(u)!
    for (const v of children.get(u)!) {
      if ((depth.get(v) ?? 0) < du + 1) depth.set(v, du + 1)
      indegree.set(v, indegree.get(v)! - 1)
      if (indegree.get(v) === 0) queue.push(v)
    }
  }
  // Any nodes still with depth 0 but with parents are in a cycle;
  // fall back to their max(parent.depth)+1 by a second pass so the
  // UI degrades gracefully instead of stacking every cycle member
  // at column 0.
  for (let pass = 0; pass < nodeIds.length; pass++) {
    let changed = false
    for (const id of nodeIds) {
      const ps = parents.get(id)!
      if (!ps.length) continue
      const maxParent = Math.max(...ps.map((p) => depth.get(p) ?? 0))
      if (depth.get(id)! < maxParent + 1) {
        depth.set(id, maxParent + 1)
        changed = true
      }
    }
    if (!changed) break
  }

  // Bucket by column.
  const columns = new Map<number, string[]>()
  for (const id of nodeIds) {
    const d = depth.get(id)!
    if (!columns.has(d)) columns.set(d, [])
    columns.get(d)!.push(id)
  }

  // Row assignment: barycenter ordering within each column, left to
  // right. Root column keeps original workflow order; each later
  // column sorts by the mean row of its parents to minimise crossings.
  const row = new Map<string, number>()
  const sortedCols = [...columns.keys()].sort((a, b) => a - b)
  for (const col of sortedCols) {
    const ids = columns.get(col)!
    const scored = ids.map((id) => {
      const ps = parents.get(id)!
      const parentRows = ps.map((p) => row.get(p)).filter((r): r is number => r !== undefined)
      const bary = parentRows.length
        ? parentRows.reduce((a, b) => a + b, 0) / parentRows.length
        : orderIndex.get(id)!
      return { id, bary, tie: orderIndex.get(id)! }
    })
    scored.sort((a, b) => a.bary - b.bary || a.tie - b.tie)
    scored.forEach((s, i) => row.set(s.id, i))
  }

  const positions = new Map<string, { x: number; y: number }>()
  for (const id of nodeIds) {
    positions.set(id, {
      x: CANVAS_PAD_X + depth.get(id)! * COL_WIDTH,
      y: CANVAS_PAD_Y + row.get(id)! * ROW_HEIGHT,
    })
  }
  return positions
}

function workflowToFlow(workflow: ReturnType<typeof useWorkflowStore.getState>['workflow']) {
  if (!workflow) return { nodes: [], edges: [] }

  // Auto-layout is only consulted for nodes that don't have a
  // persisted position. Once a user drags a node its coordinates
  // live in workflow.nodes[i].position and win every time.
  const autoPositions = layoutByTopology(workflow)

  const nodes: Node[] = workflow.nodes.map((n) => ({
    id: n.id,
    type: 'custom',
    position: n.position ?? autoPositions.get(n.id) ?? { x: CANVAS_PAD_X, y: CANVAS_PAD_Y },
    data: { label: n.label, nodeType: n.type, config: n.config, disabled: !!n.disabled },
  }))

  const edges: Edge[] = workflow.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.from,
    target: e.to,
    type: 'smoothstep',
    animated: false,
    style: { stroke: 'var(--border-strong)', strokeWidth: 1.5, opacity: 0.8 },
  }))

  return { nodes, edges }
}

function styleEdgesByRun(edges: Edge[], log: RunLogEntry[]): Edge[] {
  const byNode = new Map(log.map((e) => [e.node_id, e]))
  return edges.map((e) => {
    const target = byNode.get(e.target as string)
    const source = byNode.get(e.source as string)
    if (target?.status === 'running') {
      return { ...e, className: 'edge--running', animated: false, style: { strokeWidth: 2 } }
    }
    if (target?.status === 'ok') {
      return { ...e, className: 'edge--done', animated: false, style: { strokeWidth: 1.75, opacity: 0.95 } }
    }
    if (target?.status === 'error') {
      return { ...e, className: 'edge--error', animated: false, style: { strokeWidth: 2 } }
    }
    // Source completed but target not yet started — subtle lead-in
    if (source?.status === 'ok') {
      return {
        ...e,
        className: '',
        animated: true,
        style: { stroke: 'var(--success)', strokeWidth: 1.5, opacity: 0.55 },
      }
    }
    return { ...e, className: '', animated: false, style: { stroke: 'var(--border-strong)', strokeWidth: 1.5, opacity: 0.65 } }
  })
}

function EmptyCanvas({ onDragOver, onDrop }: { onDragOver: (e: DragEvent<HTMLDivElement>) => void; onDrop: (e: DragEvent<HTMLDivElement>) => void }) {
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const setRightPanelMode = useWorkflowStore((s) => s.setRightPanelMode)
  return (
    <div
      className="flex-1 relative flex items-center justify-center"
      style={{ background: 'transparent' }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="text-center relative z-10 max-w-md px-6" style={{ display: 'grid', gap: 18, justifyItems: 'center' }}>
        <h2 style={{ color: 'var(--text-0)', fontSize: 30, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.1 }}>
          Compose a workflow
        </h2>
        <p style={{ color: 'var(--text-2)', fontSize: 13.5, lineHeight: 1.55, maxWidth: 440 }}>
          Drag nodes from the left palette, chain typed ports, or ask the{' '}
          <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>Copilot</span> to generate an entire surveillance workflow.
        </p>
        <div className="flex items-center gap-3 mt-1">
          <button
            onClick={() => setDrawerOpen(true)}
            style={{
              height: 40, padding: '0 18px', borderRadius: 8,
              background: 'linear-gradient(135deg, var(--accent-hi) 0%, var(--accent-lo) 100%)',
              color: '#fff',
              border: '1px solid color-mix(in srgb, var(--accent-lo) 45%, transparent)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
              boxShadow: '0 4px 14px color-mix(in srgb, var(--accent) 28%, transparent)',
            }}
          >
            Load a template
          </button>
          <button
            onClick={() => setRightPanelMode('copilot')}
            style={{
              height: 40, padding: '0 18px', borderRadius: 8,
              background: 'transparent', color: 'var(--text-0)',
              border: '1px solid var(--border-strong)',
              fontSize: 13, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Ask copilot
          </button>
        </div>
      </div>
    </div>
  )
}

export default function WorkflowCanvas() {
  // ReactFlowProvider is required so the inner shell can use `useReactFlow()`
  // for screen→flow coord conversion when handling palette drops.
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner />
    </ReactFlowProvider>
  )
}

function WorkflowCanvasInner() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const addNode = useWorkflowStore((s) => s.addNode)
  const updateNodePosition = useWorkflowStore((s) => s.updateNodePosition)
  const deleteNodes = useWorkflowStore((s) => s.deleteNodes)
  const deleteEdge = useWorkflowStore((s) => s.deleteEdge)
  const { screenToFlowPosition } = useReactFlow()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const { copySelection } = useCanvasKeyboard(wrapperRef)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => workflowToFlow(workflow),
    [workflow]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Re-sync React Flow's internal state when the workflow object changes
  // outside canvas gestures (template load, import, copilot edit, clear).
  // This useMemo intentionally performs state writes; a useEffect would be
  // more idiomatic, but introduces an extra frame where the canvas can show
  // stale nodes. Touch carefully if you refactor the flow/store boundary.
  useMemo(() => {
    const { nodes: n, edges: e } = workflowToFlow(workflow)
    setNodes(n)
    setEdges(e)
  }, [workflow]) // eslint-disable-line

  // Derive edge styling from run state without mutating layout
  const displayEdges = useMemo(() => styleEdgesByRun(edges, runLog), [edges, runLog])

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge({ ...params, type: 'smoothstep', style: { stroke: 'var(--accent)', strokeWidth: 1.75 } }, eds)
      ),
    [setEdges]
  )

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      const raw =
        e.dataTransfer.getData(PALETTE_DND_MIME) ||
        e.dataTransfer.getData('text/plain')
      if (!raw) return
      if (!useNodeRegistryStore.getState().nodeUI[raw]) return
      const type = raw as NodeType
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addNode(type, position)
    },
    [addNode, screenToFlowPosition]
  )

  // Persist manual drags back to the workflow so position survives re-sync.
  const onNodeDragStop: NodeDragHandler = useCallback(
    (_ev, node) => updateNodePosition(node.id, node.position),
    [updateNodePosition]
  )

  // ReactFlow fires these when the user presses Delete on the canvas with
  // its built-in shortcut set. We forward to the store so edges referencing
  // removed nodes are cleaned up too.
  const onNodesDelete = useCallback(
    (deleted: Node[]) => deleteNodes(deleted.map((n) => n.id)),
    [deleteNodes],
  )
  const onEdgesDelete = useCallback(
    (deleted: Edge[]) =>
      deleted.forEach((e) => deleteEdge(e.source as string, e.target as string)),
    [deleteEdge],
  )

  // Right-click on a node → open context menu anchored at the cursor.
  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault()
      setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id })
    },
    [],
  )

  // Right-click on empty canvas / node deselection → dismiss any open menu.
  const onPaneClick = useCallback(() => setContextMenu(null), [])
  const onPaneContextMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    // Prevent browser menu on the canvas backdrop. We'll add a pane-level
    // menu later if needed (paste clipboard here, etc.).
    e.preventDefault()
    setContextMenu(null)
  }, [])

  // When the selection changes, also close the menu so it doesn't drift.
  const onSelectionChange = useCallback((_p: OnSelectionChangeParams) => {
    setContextMenu(null)
  }, [])

  if (!workflow) {
    return (
      <EmptyCanvas onDragOver={onDragOver} onDrop={onDrop} />
    )
  }

  return (
    <div
      ref={wrapperRef}
      className="flex-1 relative"
      style={{ background: 'transparent' }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {/* atmospheric overlays — pointer-events:none, sit under the flow UI */}
      <div className="canvas-atmo" />
      <div className="canvas-grain" />

      <ReactFlow
        nodes={nodes}
        edges={displayEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={onPaneClick}
        onPaneContextMenu={onPaneContextMenu}
        onSelectionChange={onSelectionChange}
        nodeTypes={nodeTypes}
        // Let our own hook drive deletes so we can batch store updates.
        // React Flow's built-in keys would otherwise also consume the event,
        // but keeping them enabled as a fallback is harmless.
        deleteKeyCode={['Delete', 'Backspace']}
        multiSelectionKeyCode={['Meta', 'Shift', 'Control']}
        selectionKeyCode={['Shift']}
        fitView={!workflow.nodes.some((n) => n.position)}
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={26}
          size={1.6}
          color="var(--dots-color)"
        />
        <Controls
          className="panel-glass !bg-[var(--panel-glass-bg)]"
          style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
          showInteractive={false}
        />
        <MiniMap
          className="panel-glass !bg-[var(--panel-glass-bg)]"
          style={{
            border: '1px solid var(--border)',
            borderRadius: 6,
          }}
          nodeColor={(n) => {
            const nodeType = (n.data as { nodeType: string })?.nodeType
            return useNodeRegistryStore.getState().nodeUI[nodeType]?.color ?? 'var(--text-3)'
          }}
          maskColor="var(--minimap-mask)"
          pannable
          zoomable
        />
      </ReactFlow>

      {contextMenu && (
        <NodeContextMenu
          menu={contextMenu}
          onClose={() => setContextMenu(null)}
          onCopy={() => copySelection()}
        />
      )}
    </div>
  )
}
