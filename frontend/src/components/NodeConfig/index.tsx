/**
 * Bottom-edge config drawer — opens for the currently selected node.
 *
 * The form is generated entirely from the node's typed ParamSpec
 * (declared in YAML on the backend, surfaced via NODE_UI). When the
 * backend adds a new param, regenerate `src/nodes/generated.ts` and
 * the field shows up here automatically — no edits to this file.
 *
 * Validation issues for the selected node light up beside the
 * relevant input. The "Apply" button writes back through
 * workflowStore.updateNode; "Cancel" reverts to the last saved state.
 *
 * The companion `ConfigInspector.tsx` renders the read-only summary
 * shown in the right panel.
 */
import { useRef, useState } from 'react'
import ResizeHandle from '../ResizeHandle'
import type { LucideIcon } from 'lucide-react'
import {
  Check,
  X as XIcon,
  Download,
  ChevronDown,
  ChevronRight,
  ChevronsDown,
  ChevronsUp,
  Radar,
  Repeat2,
  Ghost,
  Layers3,
} from 'lucide-react'
import { useWorkflowStore, type RightPanelTab } from '../../store/workflowStore'
import { NODE_UI, type NodeType } from '../../nodes'
import type { RunLogEntry } from '../../types'
import ConfigInspector from './ConfigInspector'

/**
 * Rewrites a download URL so it goes through the Vite `/api` proxy in dev
 * (and is safe in prod). The backend currently emits paths like
 * `/report/<file>.xlsx` — those would otherwise hit Vite's SPA fallback and
 * return index.html, producing a corrupt "xlsx" file.
 */
function resolveDownloadHref(url: string): string {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/')) return url
  if (url.startsWith('/')) return `/api${url}`
  return `/api/${url}`
}

const TABS: readonly RightPanelTab[] = ['config', 'runlog', 'result', 'skills'] as const

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
      className="shrink-0 w-4 h-4 rounded-full flex items-center justify-center"
      style={{
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        border: `1px solid ${color}`,
        color,
      }}
    >
      {status === 'running' ? (
        <span className="w-1.5 h-1.5 rounded-full live-blink" style={{ background: color }} />
      ) : status === 'error' ? (
        <XIcon size={9} strokeWidth={3} />
      ) : (
        <Check size={9} strokeWidth={3} />
      )}
    </div>
  )
}

function DatasetPreview({ name, ds }: { name: string; ds: { rows: number; columns: string[]; sample: Record<string, unknown>[] } }) {
  const columns = ds.columns.slice(0, 6)
  return (
    <div
      className="rounded overflow-hidden"
      style={{ background: 'var(--bg-0)', border: '1px solid var(--border)' }}
    >
      <div
        className="flex items-center justify-between px-2 py-1"
        style={{ background: 'var(--bg-2)', fontSize: 11 }}
      >
        <span className="num" style={{ color: 'var(--info)' }}>{name}</span>
        <span className="num" style={{ color: 'var(--text-2)' }}>
          {ds.rows} rows · {ds.columns.length} cols
        </span>
      </div>
      {ds.sample.length > 0 && (
        <div className="overflow-x-auto">
          <table className="num" style={{ minWidth: '100%', fontSize: 10.5 }}>
            <thead>
              <tr style={{ background: 'var(--bg-1)' }}>
                {columns.map((c) => (
                  <th
                    key={c}
                    className="text-left px-2 py-1 whitespace-nowrap eyebrow"
                    style={{ color: 'var(--text-2)', fontSize: 9.5 }}
                  >
                    {c}
                  </th>
                ))}
                {ds.columns.length > columns.length && (
                  <th className="text-left px-2 py-1 eyebrow" style={{ color: 'var(--text-3)' }}>
                    +{ds.columns.length - columns.length}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {ds.sample.map((row, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border-soft)' }}>
                  {columns.map((c) => {
                    const v = row[c]
                    const text = v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)
                    return (
                      <td
                        key={c}
                        className="px-2 py-1 whitespace-nowrap overflow-hidden"
                        style={{ color: 'var(--text-1)', maxWidth: 180, textOverflow: 'ellipsis' }}
                        title={text}
                      >
                        {text}
                      </td>
                    )
                  })}
                  {ds.columns.length > columns.length && (
                    <td className="px-2 py-1" style={{ color: 'var(--text-3)' }}>…</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function NodeOutput({ entry }: { entry: RunLogEntry }) {
  const { output, error, trace } = entry
  if (error) {
    return (
      <div className="mt-2 space-y-1">
        <div style={{ fontSize: 11.5, color: 'var(--danger)', fontWeight: 500 }}>{error}</div>
        {trace && (
          <pre
            className="p-2 rounded overflow-x-auto num"
            style={{
              fontSize: 10.5,
              color: 'var(--text-2)',
              background: 'var(--bg-0)',
              border: '1px solid color-mix(in srgb, var(--danger) 40%, transparent)',
              maxHeight: 180,
            }}
          >
            {trace}
          </pre>
        )}
      </div>
    )
  }
  if (!output) return <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 8 }}>No output recorded</div>
  return (
    <div className="mt-2 space-y-2">
      {output.datasets && Object.keys(output.datasets).length > 0 && (
        <div className="space-y-1.5">
          {Object.entries(output.datasets).map(([name, ds]) => (
            <DatasetPreview key={name} name={name} ds={ds} />
          ))}
        </div>
      )}
      {output.disposition != null && (
        <div className="flex flex-wrap gap-x-3 gap-y-1" style={{ fontSize: 11 }}>
          <KV k="disposition" v={output.disposition || '—'} vColor="var(--accent)" bold />
          <KV k="flags" v={String(output.flag_count ?? 0)} vColor="var(--text-0)" bold />
          {output.output_branch && <KV k="branch" v={output.output_branch} vColor="var(--text-1)" mono />}
        </div>
      )}
      {output.section && (
        <div className="rounded p-2" style={{ background: 'var(--bg-0)', border: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2 mb-1" style={{ fontSize: 11 }}>
            <span style={{ color: 'var(--text-2)' }}>section:</span>
            <span className="num" style={{ color: '#EC4899' }}>{output.section.name}</span>
          </div>
          <div className="mb-1" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
            {Object.entries(output.section.stats).map(([k, v]) => (
              <span key={k} className="mr-3">
                {k}: <span style={{ color: 'var(--text-1)' }} className="num">{String(v)}</span>
              </span>
            ))}
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.55 }}>
            {output.section.narrative_preview}
          </p>
        </div>
      )}
      {output.executive_summary_preview && (
        <div className="rounded p-2" style={{ background: 'var(--bg-0)', border: '1px solid var(--border)' }}>
          <div className="mb-1" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
            executive summary ({output.executive_summary_chars} chars)
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
            {output.executive_summary_preview}
          </p>
        </div>
      )}
      {output.report_path && (
        <div className="flex items-center gap-2" style={{ fontSize: 11 }}>
          <span style={{ color: 'var(--text-2)' }}>report:</span>
          <span className="num break-all" style={{ color: 'var(--success)' }}>{output.report_path}</span>
        </div>
      )}
      {output.context && Object.keys(output.context).length > 0 && (
        <details>
          <summary
            className="cursor-pointer"
            style={{ fontSize: 11, color: 'var(--text-2)' }}
          >
            context changes ({Object.keys(output.context).length})
          </summary>
          <pre
            className="mt-1 p-2 rounded overflow-x-auto num"
            style={{
              fontSize: 10.5,
              color: 'var(--text-2)',
              background: 'var(--bg-0)',
              border: '1px solid var(--border)',
              maxHeight: 180,
            }}
          >
            {JSON.stringify(output.context, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}

function KV({ k, v, vColor, bold, mono }: { k: string; v: string; vColor?: string; bold?: boolean; mono?: boolean }) {
  return (
    <span>
      <span style={{ color: 'var(--text-2)' }}>{k}:</span>{' '}
      <span
        className={mono ? 'num' : ''}
        style={{
          color: vColor ?? 'var(--text-0)',
          fontWeight: bold ? 600 : 400,
        }}
      >
        {v}
      </span>
    </span>
  )
}

function RunLogTimeline() {
  const { runLog, runTotalMs, isRunning, runError } = useWorkflowStore()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  if (runLog.length === 0 && !isRunning) {
    return (
      <p className="text-center mt-8" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
        Run the workflow to see per-node execution
      </p>
    )
  }

  const doneCount = runLog.filter((e) => e.status !== 'running').length
  const totalSoFar = runLog.reduce((acc, e) => acc + (e.duration_ms ?? 0), 0)

  return (
    <div className="space-y-2">
      {/* Header */}
      <div
        className="flex items-center justify-between px-2.5 py-2 rounded-lg"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', fontSize: 11.5 }}
      >
        <span style={{ color: 'var(--text-1)' }} className="flex items-center gap-2">
          {isRunning ? (
            <>
              <span
                className="inline-block w-2 h-2 rounded-full live-blink"
                style={{ background: 'var(--running)' }}
              />
              <span className="eyebrow" style={{ color: 'var(--running)' }}>Running</span>
              <span className="num" style={{ color: 'var(--text-0)', fontWeight: 600 }}>
                {doneCount}/{runLog[0]?.total || runLog.length}
              </span>
            </>
          ) : runError ? (
            <span style={{ color: 'var(--danger)' }} className="flex items-center gap-1.5">
              <XIcon size={12} strokeWidth={2.5} /> <span className="eyebrow">Failed</span>
            </span>
          ) : (
            <>
              <Check size={12} strokeWidth={2.5} style={{ color: 'var(--success)' }} />
              <span className="eyebrow" style={{ color: 'var(--success)' }}>Completed</span>
              <span className="num" style={{ color: 'var(--text-0)', fontWeight: 600 }}>
                {runLog.length} nodes
              </span>
            </>
          )}
        </span>
        <span className="num" style={{ color: 'var(--text-1)', fontWeight: 600 }}>
          {runTotalMs != null ? formatDuration(runTotalMs) : `${formatDuration(totalSoFar)}${isRunning ? ' …' : ''}`}
        </span>
      </div>

      {runError && (
        <div
          className="rounded-lg p-2"
          style={{
            fontSize: 11,
            color: 'var(--danger)',
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--danger) 40%, transparent)',
          }}
        >
          {runError}
                      </div>
      )}

      {/* Timeline */}
      <div className="space-y-1">
        {runLog.map((entry) => {
          const meta = NODE_UI[entry.node_type as NodeType]
          const isOpen = expanded.has(entry.node_id)
          const IconComp = meta?.Icon
          return (
            <div
              key={entry.node_id + ':' + entry.index}
              className="rounded-lg lift"
              style={{
                background: 'var(--bg-2)',
                border: `1px solid ${meta ? `color-mix(in srgb, ${meta.color} 25%, var(--border))` : 'var(--border)'}`,
              }}
            >
              <button
                onClick={() => toggle(entry.node_id)}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-left"
              >
                <StatusDot status={entry.status} />
                <span className="shrink-0 num" style={{ color: 'var(--text-3)', width: 22, textAlign: 'right', fontSize: 10.5 }}>
                  {entry.index}.
                </span>
                {IconComp && (
                  <span
                    className="shrink-0 flex items-center justify-center rounded"
                    style={{
                      width: 18, height: 18,
                      background: `${meta!.color}14`,
                      color: meta!.color,
                    }}
                  >
                    <IconComp size={11} strokeWidth={2} />
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <div className="truncate" style={{ fontSize: 11.5, color: 'var(--text-0)', fontWeight: 500 }}>
                    {entry.label}
                    </div>
                  <div className="truncate" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
                    {entry.node_type} · <span className="num">{entry.node_id}</span>
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-1.5">
                  <span
                    className="num"
                    style={{
                      fontSize: 10.5,
                      color: entry.status === 'running' ? 'var(--running)' : entry.status === 'error' ? 'var(--danger)' : 'var(--text-1)',
                      fontWeight: 600,
                    }}
                  >
                    {entry.status === 'running' ? '…' : formatDuration(entry.duration_ms)}
                  </span>
                  {isOpen
                    ? <ChevronDown size={12} style={{ color: 'var(--text-3)' }} />
                    : <ChevronRight size={12} style={{ color: 'var(--text-3)' }} />}
                </div>
              </button>
              {isOpen && (
                <div className="px-2.5 pb-2.5">
                  <NodeOutput entry={entry} />
                </div>
              )}
            </div>
          )
        })}
                </div>
              </div>
  )
}

function DownloadButton({ href, size = 'lg' }: { href: string; size?: 'lg' | 'sm' }) {
  const resolved = resolveDownloadHref(href)
  // Prefer the real filename so the browser saves as "<alert>.xlsx"
  // rather than appending ".html" from the response mime/ext heuristic.
  const filename = decodeURIComponent(resolved.split('/').pop() || 'report.xlsx')
  return (
    <a
      href={resolved}
      download={filename}
      target="_blank"
      rel="noopener"
      className="flex items-center justify-center gap-2 w-full rounded-lg lift"
      style={{
        padding: size === 'lg' ? '10px 12px' : '8px 12px',
        fontSize: size === 'lg' ? 12.5 : 11.5,
        fontWeight: 600,
        background: 'linear-gradient(180deg, var(--success) 0%, var(--success-lo) 100%)',
        color: '#FFFFFF',
        border: '1px solid color-mix(in srgb, var(--success-lo) 60%, black)',
        boxShadow: '0 1px 0 rgba(255,255,255,0.25) inset, 0 10px 22px -10px color-mix(in srgb, var(--success) 60%, transparent)',
        letterSpacing: '0.02em',
      }}
    >
      <Download size={size === 'lg' ? 14 : 12} strokeWidth={2.2} />
      <span>{size === 'lg' ? 'Download Excel Report' : 'Download Report'}</span>
    </a>
  )
}

const SKILLS: { id: string; name: string; Icon: LucideIcon; color: string }[] = [
  { id: 'skills-fx-fro',      name: 'FX Front-Running', Icon: Radar,   color: '#7C3AED' },
  { id: 'skills-fx-wash',     name: 'FX Wash Trading',  Icon: Repeat2, color: '#2563EB' },
  { id: 'skills-fi-spoofing', name: 'FI Spoofing',      Icon: Ghost,   color: '#DC2626' },
  { id: 'skills-fi-layering', name: 'FI Layering',      Icon: Layers3, color: '#D97706' },
]

export default function NodeConfig() {
  const {
    workflow,
    selectedNodeId,
    runResult,
    runTotalMs,
    runLog,
    rightPanelTab,
    setRightPanelTab,
    nodeConfigCollapsed,
    toggleNodeConfig,
    setNodeConfigCollapsed,
    nodeConfigHeight,
    setNodeConfigHeight,
  } = useWorkflowStore()
  const node = workflow?.nodes.find((n) => n.id === selectedNodeId)
  const meta = node ? NODE_UI[node.type] : null
  const rootRef = useRef<HTMLDivElement>(null)

  // Freshest run log entry for the currently-selected node. We scan in reverse
  // so re-runs show the most recent pass rather than the first.
  const selectedRunEntry = node
    ? [...runLog].reverse().find((e) => e.node_id === node.id)
    : undefined

  // Dock sizing: collapsed = tabs strip only, expanded = tabs + content.
  const dockHeight = nodeConfigCollapsed ? 40 : nodeConfigHeight

  return (
    <div
      ref={rootRef}
      className="flex flex-col relative"
      style={{
        width: '100%',
        // `height` is the *preferred* size. flex-shrink:1 lets the dock give
        // up space on very short windows. flex-grow:0 keeps it from expanding
        // into the canvas when the user grows the viewport.
        height: dockHeight,
        minHeight: 40,
        flexShrink: 1,
        flexGrow: 0,
        background: 'var(--bg-1)',
        borderTop: '1px solid var(--border-strong)',
        // Only animate height during collapse/expand — not during a live drag.
        transition: nodeConfigCollapsed ? 'height 200ms var(--ease-out)' : undefined,
        boxShadow: '0 -4px 16px -12px rgba(0,0,0,.25)',
      }}
    >
      {/* Drag the top edge to resize the dock (hidden while collapsed). */}
      {!nodeConfigCollapsed && (
        <ResizeHandle
          edge="top"
          ariaLabel="Resize config dock"
          onResize={(clientY) => {
            const bottom = rootRef.current?.getBoundingClientRect().bottom ?? window.innerHeight
            setNodeConfigHeight(bottom - clientY)
          }}
        />
      )}
      {/* Tab bar + collapse toggle */}
      <div
        className="flex items-stretch shrink-0"
        style={{
          borderBottom: nodeConfigCollapsed ? 'none' : '1px solid var(--border)',
          height: 40,
        }}
      >
        {TABS.map((t) => {
          const active = rightPanelTab === t
          return (
            <button
              key={t}
              onClick={() => {
                setRightPanelTab(t)
                // Opening a tab auto-expands the dock so users don't click into a hidden panel.
                if (nodeConfigCollapsed) setNodeConfigCollapsed(false)
              }}
              className="capitalize transition-colors"
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                padding: '0 18px',
                background: active ? 'var(--bg-2)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--text-2)',
                borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
                borderRight: '1px solid var(--border-soft)',
              }}
            >
              {t === 'runlog' ? 'Run Log' : t}
            </button>
          )
        })}

        <div className="flex-1" />

        {/* Context hint: selected node or "no selection" */}
        {!nodeConfigCollapsed && node && meta && (
          <div className="flex items-center gap-2 pr-3" style={{ fontSize: 11 }}>
            <span
              className="flex items-center justify-center rounded shrink-0"
              style={{
                width: 20, height: 20,
                background: `${meta.color}14`,
                border: `1px solid ${meta.color}40`,
                color: meta.color,
              }}
            >
              <meta.Icon size={11} strokeWidth={2} />
            </span>
            <span className="eyebrow" style={{ color: meta.color }}>
              {node.type.replace(/_/g, ' ')}
            </span>
            <span className="num" style={{ color: 'var(--text-2)', fontSize: 10.5 }}>
              {node.id}
            </span>
          </div>
        )}

        <button
          onClick={toggleNodeConfig}
          aria-label={nodeConfigCollapsed ? 'Expand config panel' : 'Collapse config panel'}
          title={nodeConfigCollapsed ? 'Expand (⌥⌘)' : 'Collapse (⌥⌘)'}
          className="lift flex items-center justify-center"
          style={{
            width: 40, height: 40,
            background: 'transparent',
            color: 'var(--text-2)',
            borderLeft: '1px solid var(--border-soft)',
          }}
          onMouseEnter={(e) => {
            ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-0)'
            ;(e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-2)'
          }}
          onMouseLeave={(e) => {
            ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-2)'
            ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
          }}
        >
          {nodeConfigCollapsed ? (
            <ChevronsUp size={14} strokeWidth={2} />
          ) : (
            <ChevronsDown size={14} strokeWidth={2} />
          )}
        </button>
      </div>

      {/* Content area — hidden when collapsed */}
      {!nodeConfigCollapsed && (
      <div className="flex-1 overflow-y-auto p-4" style={{ maxWidth: 1400, width: '100%', margin: '0 auto' }}>
        {/* Config tab — full node inspector: header / wiring / editable
            config / last-run output. Driven by the central node registry
            and runLog so everything stays in sync. */}
        {rightPanelTab === 'config' && (
          <ConfigInspector
            runEntry={selectedRunEntry}
            renderRunOutput={(entry) => <NodeOutput entry={entry} />}
          />
        )}

        {/* Run Log tab */}
        {rightPanelTab === 'runlog' && <RunLogTimeline />}

        {/* Result tab */}
        {rightPanelTab === 'result' && (
          <div className="space-y-3">
            {!runResult ? (
              <p className="text-center mt-8" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
                Run the workflow to see results
              </p>
            ) : (
              <>
                <DispositionBanner
                  disposition={runResult.disposition}
                  flagCount={runResult.flag_count}
                  totalMs={runTotalMs}
                />

                {runResult.download_url && <DownloadButton href={runResult.download_url} size="lg" />}

                {runResult.executive_summary && (
                  <div>
                    <label className="eyebrow" style={{ color: 'var(--text-2)' }}>Executive Summary</label>
                    <div
                      className="mt-1 rounded-lg p-2.5 whitespace-pre-wrap"
                  style={{
                        fontSize: 11.5,
                        color: 'var(--text-1)',
                        lineHeight: 1.6,
                        background: 'var(--bg-2)',
                        border: '1px solid var(--border)',
                        maxHeight: 240,
                        overflowY: 'auto',
                      }}
                    >
                      {runResult.executive_summary}
                    </div>
                  </div>
                )}

                <div>
                  <label className="eyebrow" style={{ color: 'var(--text-2)' }}>Datasets</label>
                  <div className="mt-1 space-y-1">
                    {runResult.datasets.map((ds) => (
                      <div
                        key={ds}
                        className="flex items-center gap-2 px-2 py-1.5 rounded"
                        style={{ background: 'var(--bg-2)', border: '1px solid var(--border-soft)' }}
                      >
                        <span className="num" style={{ fontSize: 11, color: 'var(--info)' }}>{ds}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {Object.entries(runResult.sections).map(([name, sec]) => (
                  <div key={name}>
                    <label className="eyebrow" style={{ color: 'var(--text-2)' }}>
                      {name.replace(/_/g, ' ')}
                    </label>
                    <div
                      className="mt-1 rounded-lg p-2"
                      style={{
                        fontSize: 11.5,
                        color: 'var(--text-1)',
                        lineHeight: 1.55,
                        background: 'var(--bg-2)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div className="mb-1" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
                        {Object.entries(sec.stats).map(([k, v]) => (
                          <span key={k} className="mr-3">
                            {k}: <span className="num" style={{ color: 'var(--text-0)' }}>{String(v)}</span>
                          </span>
                        ))}
                      </div>
                      <p className="line-clamp-4">{sec.narrative}</p>
                    </div>
                  </div>
                ))}

                {runResult.report_path && !runResult.download_url && (
                  <div>
                    <label className="eyebrow" style={{ color: 'var(--text-2)' }}>Report</label>
                    <div
                      className="mt-1 num rounded px-2 py-1.5 break-all"
                      style={{
                        fontSize: 11,
                        color: 'var(--success)',
                        background: 'var(--bg-0)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      {runResult.report_path}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Skills tab */}
        {rightPanelTab === 'skills' && (
          <div className="space-y-2">
            <p className="mb-3" style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
              Skills are templates for common surveillance scenarios. Ask the Copilot to use them.
            </p>
            {SKILLS.map((skill) => (
              <div
                key={skill.id}
                className="rounded-lg p-3 cursor-pointer lift"
                style={{
                  background: 'var(--bg-2)',
                  border: `1px solid color-mix(in srgb, ${skill.color} 20%, var(--border))`,
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = `color-mix(in srgb, ${skill.color} 60%, transparent)` }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = `color-mix(in srgb, ${skill.color} 20%, var(--border))` }}
              >
                <div className="flex items-center gap-2.5">
                  <div
                    className="flex items-center justify-center rounded-md shrink-0"
                    style={{
                      width: 30, height: 30,
                      background: `${skill.color}14`,
                      border: `1px solid ${skill.color}40`,
                      color: skill.color,
                    }}
                  >
                    <skill.Icon size={15} strokeWidth={2} />
                  </div>
                  <div className="min-w-0">
                    <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-0)' }}>{skill.name}</div>
                    <div className="num" style={{ fontSize: 10.5, color: skill.color }}>
                      skills/{skill.id}.md
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  )
}

function DispositionBanner({
  disposition, flagCount, totalMs,
}: { disposition: string; flagCount: number; totalMs: number | null }) {
  const isEsc = disposition === 'ESCALATE'
  const isRev = disposition === 'REVIEW'
  const color = isEsc ? 'var(--danger)' : isRev ? 'var(--accent)' : 'var(--success)'
  return (
    <div
      className="rounded-lg text-center"
      style={{
        padding: '14px 12px',
        background: `color-mix(in srgb, ${color} 12%, var(--bg-2))`,
        border: `1px solid color-mix(in srgb, ${color} 50%, transparent)`,
      }}
    >
      <div
        className="display"
        style={{
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: '0.04em',
          color,
        }}
      >
        {disposition || 'COMPLETED'}
      </div>
      <div className="eyebrow mt-1" style={{ color: 'var(--text-2)' }}>
        <span className="num" style={{ color: 'var(--text-0)' }}>{flagCount}</span> signal flags
        {totalMs != null && <> · <span className="num" style={{ color: 'var(--text-0)' }}>{formatDuration(totalMs)}</span></>}
      </div>
    </div>
  )
}
