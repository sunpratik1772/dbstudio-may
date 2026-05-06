/**
 * Visual representation of a single node on the canvas.
 *
 * Pulls colour/icon from `nodeRegistryStore` (live node-manifest).
 * React.memo wraps the
 * component because React Flow re-renders on every drag frame; without
 * it a 30-node DAG drops below 60fps.
 *
 * Live run state (running / ok / error pulse) comes from
 * `useNodeRunStatus(id)`, which subscribes to SSE events the backend
 * pushes during /run/stream — so the graph animates as a workflow runs.
 */
import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { getNodeDisplayName, useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType, type NodeUIMeta } from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRunStatus } from '../../store/useNodeRunStatus'

interface NodeData {
  label: string
  nodeType: NodeType
  config: Record<string, unknown>
  disabled?: boolean
}

function formatMs(ms?: number): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`
}

const STATUS_COLOR: Record<string, string> = {
  idle: 'var(--border-strong)',
  running: 'var(--running)',
  ok: 'var(--success)',
  error: 'var(--danger)',
}

export const CustomNode = memo(({ id, data }: NodeProps<NodeData>) => {
  const meta: NodeUIMeta = useNodeRegistryStore((s) => s.nodeUI[data.nodeType] ?? UNKNOWN_NODE_UI)
  const IconComp = meta.Icon
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId)
  const selectNode = useWorkflowStore((s) => s.selectNode)
  const run = useNodeRunStatus(id)

  const isSelected = selectedNodeId === id
  const isRunning = run.status === 'running'
  const isOk = run.status === 'ok'
  const isError = run.status === 'error'
  const hasRun = isRunning || isOk || isError

  const ringColor = STATUS_COLOR[run.status]

  // Border: run state > selection > rest.
  // Run-state borders take precedence so the user always sees what is live.
  const borderColor = isRunning
    ? 'var(--running)'
    : isOk
    ? 'var(--success)'
    : isError
    ? 'var(--danger)'
    : isSelected
    ? meta.color
    : 'var(--border)'

  const shadow = isRunning
    ? `0 0 0 2px color-mix(in srgb, var(--running) 28%, transparent), 0 16px 36px -14px color-mix(in srgb, var(--running) 55%, transparent)`
    : isOk
    ? `0 10px 28px -14px color-mix(in srgb, var(--success) 40%, transparent)`
    : isError
    ? `0 10px 28px -14px color-mix(in srgb, var(--danger) 45%, transparent)`
    : isSelected
    ? `0 0 0 2px ${meta.color}2E, 0 18px 40px -16px rgba(0,0,0,0.35)`
    : '0 6px 18px -10px rgba(0,0,0,0.35)'

  const elapsed = isRunning ? run.live_ms : run.duration_ms

  const isDisabled = !!data.disabled

  return (
    <div
      onClick={() => {
        selectNode(id)
        useWorkflowStore.getState().setRightPanelMode('config')
      }}
      className={`relative cursor-pointer lift ${isRunning ? 'run-ring' : ''}`}
      style={{
        width: 252,
        borderRadius: 8,
        background: isRunning
          ? 'linear-gradient(180deg, color-mix(in srgb, var(--running) 7%, var(--bg-node-elev)) 0%, var(--bg-node) 100%)'
          : 'linear-gradient(180deg, var(--bg-node-elev) 0%, var(--bg-node) 100%)',
        border: `${isRunning ? 2 : 1}px solid ${borderColor}`,
        boxShadow: shadow,
        transition: 'border-color 180ms var(--ease-out), box-shadow 180ms var(--ease-out), background 180ms var(--ease-out), opacity 180ms var(--ease-out)',
        zIndex: isRunning ? 10 : 1,
        opacity: isDisabled ? 0.5 : 1,
        filter: isDisabled ? 'grayscale(0.6)' : undefined,
      }}
    >
      {/* Top accent strip — carries the node family color, with scan-sweep while running */}
      <div
        className={`relative overflow-hidden ${isRunning ? 'scan-sweep' : ''}`}
        style={{
          height: 2,
          background: isOk
            ? 'var(--success)'
            : isError
            ? 'var(--danger)'
            : meta.color,
          borderTopLeftRadius: 7,
          borderTopRightRadius: 7,
        }}
      />

      {/* Header row */}
      <div className="flex items-start gap-2.5 px-3 pt-2.5 pb-2">
        <div
          className="flex items-center justify-center rounded-md shrink-0"
          style={{
            width: 26, height: 26,
            background: `color-mix(in srgb, ${meta.color} 10%, transparent)`,
            border: `1px solid color-mix(in srgb, ${meta.color} 28%, transparent)`,
            color: meta.color,
          }}
        >
          <IconComp size={15} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div
            className="eyebrow truncate"
            style={{ color: 'var(--text-3)', letterSpacing: '0.08em', fontSize: 9.5 }}
          >
            {getNodeDisplayName(data.nodeType)}
          </div>
          <div
            className="truncate"
            style={{ color: 'var(--text-0)', fontSize: 12.5, fontWeight: 560, lineHeight: 1.3, marginTop: 2 }}
            title={data.label}
          >
            {data.label}
          </div>
        </div>
      </div>

      {/* Status row — always present so nodes don't jump in height */}
      <div
        className="flex items-center justify-between gap-2 px-3 py-1.5 border-t"
        style={{ borderColor: 'var(--border-soft)', minHeight: 28 }}
      >
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusDot status={run.status} />
          <span
            className="eyebrow"
            style={{ color: ringColor, fontSize: 9.5, letterSpacing: '0.08em' }}
          >
            {statusLabel(run.status)}
          </span>
          {isRunning && run.index != null && run.total != null && (
            <span className="num" style={{ color: 'var(--text-2)', fontSize: 10 }}>
              · {run.index}/{run.total}
            </span>
          )}
        </div>
        {hasRun && (
          <span
            className="num"
            style={{
              color: isError ? 'var(--danger)' : isRunning ? 'var(--running)' : 'var(--text-1)',
              fontSize: 10.5,
              fontWeight: 600,
            }}
          >
            {formatMs(elapsed)}
          </span>
        )}
      </div>

      {/* Config tags — declarative, driven by the node registry's
          `configTags` list so adding/removing a tag is a one-line change
          in backend/engine/registry.py. */}
      {meta.configTags.some((k) => data.config[k] != null) && (
        <div className="flex flex-wrap gap-1 px-3 pb-2.5 pt-0.5">
          {meta.configTags.map((k) => {
            const v = data.config[k]
            if (v == null) return null
            const tone = k === 'signal_type' ? 'danger' : k === 'output_name' ? 'muted' : 'default'
            const label = k === 'output_name' ? `→ ${String(v)}` : String(v)
            return <Tag key={k} label={label} tone={tone} />
          })}
        </div>
      )}

      {/* Node ID badge, bottom-right */}
      <div
        className="absolute num"
        style={{
          right: 8, bottom: 6,
          fontSize: 9,
          color: 'var(--text-3)',
          letterSpacing: 0,
        }}
      >
        {id}
      </div>

      {/* Handles */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: isRunning ? 'var(--running)' : meta.color,
          border: '2px solid var(--bg-0)',
          width: 9, height: 9,
          boxShadow: isRunning
            ? '0 0 0 3px color-mix(in srgb, var(--running) 30%, transparent)'
            : undefined,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: isOk ? 'var(--success)' : isRunning ? 'var(--running)' : meta.color,
          border: '2px solid var(--bg-0)',
          width: 9, height: 9,
          boxShadow: isRunning
            ? '0 0 0 3px color-mix(in srgb, var(--running) 30%, transparent)'
            : undefined,
        }}
      />
    </div>
  )
})

CustomNode.displayName = 'CustomNode'

function statusLabel(s: string): string {
  switch (s) {
    case 'running': return 'Running'
    case 'ok': return 'Complete'
    case 'error': return 'Error'
    default: return 'Idle'
  }
}

function StatusDot({ status }: { status: string }) {
  if (status === 'running') {
    return (
      <span className="relative inline-flex" style={{ width: 8, height: 8 }}>
        <span
          className="absolute inset-0 rounded-full"
          style={{ background: 'var(--running)' }}
        />
        <span
          className="absolute inset-0 rounded-full live-blink"
          style={{ background: 'var(--running)', filter: 'blur(4px)' }}
        />
      </span>
    )
  }
  const color =
    status === 'ok' ? 'var(--success)' :
    status === 'error' ? 'var(--danger)' :
    'var(--text-3)'
  return (
    <span
      className="inline-block rounded-full"
      style={{ width: 7, height: 7, background: color }}
    />
  )
}

function Tag({ label, tone = 'default' }: { label: string; tone?: 'default' | 'danger' | 'muted' }) {
  const styles = {
    default: { bg: 'rgba(124, 139, 255, 0.08)', fg: '#B7BEFF', br: 'rgba(124, 139, 255, 0.2)' },
    danger:  { bg: 'rgba(248, 113, 113, 0.10)', fg: '#FCA5A5', br: 'rgba(248, 113, 113, 0.25)' },
    muted:   { bg: 'rgba(111, 129, 154, 0.08)', fg: 'var(--text-2)', br: 'var(--border)' },
  }[tone]
  return (
    <span
      className="num"
      style={{
        fontSize: 10,
        padding: '2px 6px',
        borderRadius: 4,
        background: styles.bg,
        color: styles.fg,
        border: `1px solid ${styles.br}`,
      }}
    >
      {label}
    </span>
  )
}
