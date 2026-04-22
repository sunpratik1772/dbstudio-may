import { useEffect, useState } from 'react'
import { useWorkflowStore } from './workflowStore'

export type NodeRunStatus = 'idle' | 'running' | 'ok' | 'error'

export interface NodeRunInfo {
  status: NodeRunStatus
  /** Completed duration in ms (after node_complete/error). */
  duration_ms?: number
  /** Live elapsed ms while status === 'running'. */
  live_ms?: number
  /** Position within the run, e.g. "3 / 12". */
  index?: number
  total?: number
  error?: string
}

/**
 * Resolves the run status and live-updating elapsed time for a single node.
 * Re-renders at ~60ms cadence only while the node is actively running, so
 * the rest of the canvas stays still.
 */
export function useNodeRunStatus(nodeId: string): NodeRunInfo {
  const entry = useWorkflowStore((s) => s.runLog.find((e) => e.node_id === nodeId))
  const [tick, setTick] = useState(0)

  const isRunning = entry?.status === 'running'

  useEffect(() => {
    if (!isRunning) return
    const id = window.setInterval(() => setTick((t) => t + 1), 60)
    return () => window.clearInterval(id)
  }, [isRunning])

  if (!entry) return { status: 'idle' }

  let live_ms: number | undefined
  if (entry.status === 'running' && entry.started_at) {
    const startedMs = Date.parse(entry.started_at)
    if (!Number.isNaN(startedMs)) live_ms = Math.max(0, Date.now() - startedMs)
  }

  // Touch tick so linter knows we depend on it (re-render driver while running).
  void tick

  return {
    status: entry.status,
    duration_ms: entry.duration_ms,
    live_ms,
    index: entry.index,
    total: entry.total,
    error: entry.error,
  }
}

/** Quick edge helper: status of the target node of an edge. */
export function useEdgeStatus(targetNodeId: string): NodeRunStatus {
  return useWorkflowStore((s) => {
    const entry = s.runLog.find((e) => e.node_id === targetNodeId)
    return (entry?.status ?? 'idle') as NodeRunStatus
  })
}
