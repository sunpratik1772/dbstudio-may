/**
 * Read-only timeline for the last streamed workflow run.
 *
 * This component does not talk to the backend directly. `Topbar.handleRun`
 * opens `/run/stream`, `services/api.ts` parses SSE frames, and
 * `workflowStore.applyRunEvent` turns those frames into `runLog` rows. Keeping
 * that flow centralized makes Config, Canvas, Output, and Run Log agree.
 */
import { Activity, Check, X as XIcon } from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType } from '../../nodes'
import type { RunLogEntry } from '../../types'
import Shell, { Empty } from './Shell'

function formatDuration(ms?: number): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function StatusDot({ status }: { status: RunLogEntry['status'] }) {
  const color =
    status === 'running' ? 'var(--running)' :
    status === 'error' ? 'var(--danger)' :
    'var(--success)'
  return (
    <div
      className="shrink-0 flex items-center justify-center"
      style={{
        width: 18, height: 18, borderRadius: 999,
        background: `color-mix(in srgb, ${color} 18%, var(--bg-1))`,
        border: `1.5px solid ${color}`,
        color,
        zIndex: 1,
      }}
    >
      {status === 'running' ? (
        <span className="live-blink" style={{ width: 6, height: 6, borderRadius: 999, background: color }} />
      ) : status === 'error' ? (
        <XIcon size={10} strokeWidth={3} />
      ) : (
        <Check size={10} strokeWidth={3} />
      )}
    </div>
  )
}

function SummaryBar() {
  const { runLog, runTotalMs, isRunning, runError } = useWorkflowStore()
  const doneCount = runLog.filter((e) => e.status !== 'running').length
  const total = runLog[0]?.total || runLog.length
  const sumMs = runLog.reduce((acc, e) => acc + (e.duration_ms ?? 0), 0)

  let label: string
  let color: string
  if (isRunning) { label = 'RUNNING'; color = 'var(--running)' }
  else if (runError) { label = 'FAILED'; color = 'var(--danger)' }
  else if (runLog.length > 0) { label = 'COMPLETED'; color = 'var(--success)' }
  else return null

  return (
    <div
      className="flex items-center justify-between px-4 py-2.5"
      style={{
        background: `color-mix(in srgb, ${color} 8%, var(--bg-1))`,
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="font-mono"
          style={{
            fontSize: 9.5, letterSpacing: '0.18em', fontWeight: 600,
            color, padding: '2px 6px', borderRadius: 4,
            border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
            background: `color-mix(in srgb, ${color} 12%, transparent)`,
          }}
        >
          {label}
        </span>
        <span className="num" style={{ fontSize: 12, color: 'var(--text-1)', fontWeight: 600 }}>
          {doneCount}/{total || runLog.length} nodes
        </span>
      </div>
      <span className="num" style={{ fontSize: 12, color: 'var(--text-0)', fontWeight: 600 }}>
        {runTotalMs != null ? formatDuration(runTotalMs) : `${formatDuration(sumMs)}${isRunning ? ' …' : ''}`}
      </span>
    </div>
  )
}

function EntryRow({ entry, last }: { entry: RunLogEntry; last: boolean }) {
  const meta = useNodeRegistryStore((s) => s.nodeUI[entry.node_type as NodeType] ?? UNKNOWN_NODE_UI)
  const IconComp = meta.Icon
  const durColor =
    entry.status === 'running' ? 'var(--running)' :
    entry.status === 'error' ? 'var(--danger)' :
    'var(--text-1)'

  return (
    <div className="relative">
      {!last && (
        <span
          aria-hidden
          style={{
            position: 'absolute', left: 21, top: 24, bottom: -8, width: 1,
            background: 'var(--border-soft)',
          }}
        />
      )}
      <div
        className="w-full flex items-center gap-2.5 text-left px-3 py-2"
        style={{ borderRadius: 6 }}
      >
        <StatusDot status={entry.status} />
        <span className="num shrink-0" style={{ fontSize: 10, color: 'var(--text-3)', width: 18, textAlign: 'right' }}>
          {entry.index}
        </span>
        {IconComp && meta && (
          <span
            className="shrink-0 flex items-center justify-center rounded"
            style={{ width: 18, height: 18, background: `${meta.color}14`, color: meta.color }}
          >
            <IconComp size={11} strokeWidth={2} />
          </span>
        )}
        <div className="flex-1 min-w-0">
          <div className="truncate" style={{ fontSize: 12, color: 'var(--text-0)', fontWeight: 500 }}>
            {entry.label}
          </div>
          <div className="truncate font-mono" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.04em' }}>
            {entry.node_type.toLowerCase()}
          </div>
        </div>
        <span className="num shrink-0" style={{ fontSize: 11, color: durColor, fontWeight: 600 }}>
          {entry.status === 'running' ? '…' : formatDuration(entry.duration_ms)}
        </span>
      </div>
    </div>
  )
}

export default function RunLogView() {
  const runLog = useWorkflowStore((s) => s.runLog)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const runError = useWorkflowStore((s) => s.runError)

  return (
    <Shell
      icon={Activity}
      title="Run Log"
      eyebrow={isRunning ? 'STREAMING' : 'EXECUTION'}
      accent="var(--accent)"
      subtitle="Per-node execution trace from the latest run."
    >
      <SummaryBar />
      {runError && (
        <div
          className="mx-4 mt-3 p-2.5 rounded"
          style={{
            fontSize: 11, color: 'var(--danger)', lineHeight: 1.5,
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
          }}
        >
          {runError}
        </div>
      )}
      <div className="px-2 pt-2 pb-3 space-y-0.5">
        {runLog.length === 0 ? (
          <Empty>
            <Activity size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
            <div style={{ color: 'var(--text-1)', fontWeight: 500, marginBottom: 4 }}>No run yet</div>
            <div>Press <span className="num" style={{ color: 'var(--text-1)' }}>Run</span> to stream per-node execution here.</div>
          </Empty>
        ) : (
          runLog.map((e, i) => (
            <EntryRow key={`${e.node_id}:${e.index}`} entry={e} last={i === runLog.length - 1} />
          ))
        )}
      </div>
    </Shell>
  )
}
