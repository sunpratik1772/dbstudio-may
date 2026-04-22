/**
 * Keyboard + clipboard hook for the workflow canvas.
 *
 * Mirrors n8n / VSCode behaviour:
 *   Delete / Backspace  → remove selected nodes and edges
 *   Cmd/Ctrl + C        → copy selected nodes to an in-memory clipboard
 *   Cmd/Ctrl + V        → paste clipboard at current cursor position
 *   Cmd/Ctrl + D        → duplicate selected nodes with a 40px offset
 *   Cmd/Ctrl + A        → select all nodes
 *
 * Deliberately scoped to the canvas DIV only — the hook ignores keystrokes
 * coming from <input>, <textarea> or contentEditable so typing into the
 * config panel doesn't nuke your selection.
 */
import { useCallback, useEffect, useRef } from 'react'
import { useReactFlow } from 'reactflow'
import type { Node as RFNode, Edge as RFEdge } from 'reactflow'
import { useWorkflowStore } from '../../store/workflowStore'
import type { WorkflowNode } from '../../types'

const CLIPBOARD_KEY = 'dbsherpa:nodeClipboard:v1'

interface ClipboardPayload {
  nodes: WorkflowNode[]   // deep-copied
  minX: number            // origin, so paste can rebase relative to cursor
  minY: number
}

function isTypingInField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  return false
}

export function useCanvasKeyboard(containerRef: React.RefObject<HTMLDivElement>) {
  const { getNodes, setNodes, screenToFlowPosition } = useReactFlow()
  const workflow = useWorkflowStore((s) => s.workflow)
  const deleteNodes = useWorkflowStore((s) => s.deleteNodes)
  const duplicateNodes = useWorkflowStore((s) => s.duplicateNodes)

  // Track the latest cursor position over the canvas so paste can anchor.
  const cursorRef = useRef<{ x: number; y: number } | null>(null)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onMove = (e: MouseEvent) => {
      cursorRef.current = { x: e.clientX, y: e.clientY }
    }
    el.addEventListener('mousemove', onMove)
    return () => el.removeEventListener('mousemove', onMove)
  }, [containerRef])

  const copySelection = useCallback((): ClipboardPayload | null => {
    const selectedIds = getNodes().filter((n) => n.selected).map((n) => n.id)
    if (selectedIds.length === 0 || !workflow) return null
    const source = workflow.nodes.filter((n) => selectedIds.includes(n.id))
    if (source.length === 0) return null
    const copy: WorkflowNode[] = source.map((n) => JSON.parse(JSON.stringify(n)))
    const xs = copy.map((n) => n.position?.x ?? 0)
    const ys = copy.map((n) => n.position?.y ?? 0)
    const payload: ClipboardPayload = {
      nodes: copy,
      minX: Math.min(...xs),
      minY: Math.min(...ys),
    }
    try {
      window.localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(payload))
    } catch {
      /* silent */
    }
    return payload
  }, [getNodes, workflow])

  const pasteClipboard = useCallback(() => {
    let payload: ClipboardPayload | null = null
    try {
      const raw = window.localStorage.getItem(CLIPBOARD_KEY)
      if (raw) payload = JSON.parse(raw) as ClipboardPayload
    } catch {
      /* ignore */
    }
    if (!payload || payload.nodes.length === 0) return

    // Anchor at the cursor if we have one, else offset from the original.
    let dx = 40
    let dy = 40
    const cursor = cursorRef.current
    if (cursor) {
      const flow = screenToFlowPosition({ x: cursor.x, y: cursor.y })
      dx = flow.x - payload.minX
      dy = flow.y - payload.minY
    }

    // We re-use the store's duplicateNodes by first re-seeding temp nodes.
    // Simpler: add each node via the store, preserving config & type.
    const { addNode } = useWorkflowStore.getState()
    const newIds: string[] = []
    payload.nodes.forEach((n) => {
      const pos = n.position
        ? { x: n.position.x + dx, y: n.position.y + dy }
        : { x: 120, y: 120 }
      const newId = addNode(n.type, pos)
      newIds.push(newId)
    })

    // After the paste, rewrite the new nodes' config & label to match the
    // source (addNode only sets type + default label + empty config).
    useWorkflowStore.setState((s) => {
      if (!s.workflow) return {}
      const nodes = s.workflow.nodes.map((n) => {
        const idx = newIds.indexOf(n.id)
        if (idx === -1) return n
        const src = payload!.nodes[idx]
        return {
          ...n,
          label: `${src.label} (copy)`,
          config: JSON.parse(JSON.stringify(src.config ?? {})),
        }
      })
      return { workflow: { ...s.workflow, nodes } }
    })

    // Select the freshly pasted set so another paste repeats smoothly.
    setNodes((rf: RFNode[]) =>
      rf.map((n) => ({ ...n, selected: newIds.includes(n.id) })),
    )
  }, [screenToFlowPosition, setNodes])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isTypingInField(e.target)) return
      const mod = e.metaKey || e.ctrlKey

      // Delete / Backspace — remove selected nodes + edges.
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Don't hijack backspace during normal typing (handled above),
        // but inside the canvas we treat it as delete.
        const nodes = getNodes()
        const selectedNodeIds = nodes.filter((n) => n.selected).map((n) => n.id)
        if (selectedNodeIds.length > 0) {
          e.preventDefault()
          deleteNodes(selectedNodeIds)
        }
        return
      }

      if (!mod) return

      // Cmd/Ctrl + A — select all nodes.
      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault()
        setNodes((rf: RFNode[]) => rf.map((n) => ({ ...n, selected: true })))
        return
      }

      // Cmd/Ctrl + C — copy.
      if (e.key === 'c' || e.key === 'C') {
        if (copySelection()) e.preventDefault()
        return
      }

      // Cmd/Ctrl + V — paste.
      if (e.key === 'v' || e.key === 'V') {
        e.preventDefault()
        pasteClipboard()
        return
      }

      // Cmd/Ctrl + D — duplicate in place.
      if (e.key === 'd' || e.key === 'D') {
        const selectedIds = getNodes().filter((n) => n.selected).map((n) => n.id)
        if (selectedIds.length > 0) {
          e.preventDefault()
          const newIds = duplicateNodes(selectedIds)
          setNodes((rf: RFNode[]) =>
            rf.map((n) => ({ ...n, selected: newIds.includes(n.id) })),
          )
        }
        return
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [copySelection, pasteClipboard, deleteNodes, duplicateNodes, getNodes, setNodes])

  // Expose imperative API so the context menu can reuse the same logic.
  return {
    copySelection,
    pasteClipboard,
  }
}

// Keep the import happy when bundlers tree-shake; referenced only for types.
export type { RFEdge }
