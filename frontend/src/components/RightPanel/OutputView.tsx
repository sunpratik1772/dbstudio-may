/**
 * Post-run output view.
 *
 * This complements `RunLogView`: the run log is a timeline, while this view
 * surfaces workflow-level result facets, report downloads, and per-node output
 * payload previews from `workflowStore.runLog` / `runResult`.
 *
 * `resolveDownloadHref` intentionally prefixes backend-relative report URLs
 * with `/api` in dev so Vite proxies to FastAPI instead of serving SPA HTML.
 */
import { useState } from 'react'
import { FileOutput, ChevronDown, ChevronRight, Download, FileText } from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType } from '../../nodes'
import type { RunLogEntry } from '../../types'
import Shell, { Empty, SectionHeader } from './Shell'

function formatDuration(ms?: number): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function resolveDownloadHref(url: string): string {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/')) return url
  if (url.startsWith('/')) return `/api${url}`
  return `/api/${url}`
}

function KV({ k, v, vColor, bold, mono }: { k: string; v: string; vColor?: string; bold?: boolean; mono?: boolean }) {
  return (
    <span>
      <span style={{ color: 'var(--text-3)' }}>{k}: </span>
      <span className={mono ? 'num' : ''} style={{ color: vColor ?? 'var(--text-0)', fontWeight: bold ? 600 : 400 }}>
        {v}
      </span>
    </span>
  )
}

/** Structured renderer for a single node's output payload. */
function StageOutput({ entry }: { entry: RunLogEntry }) {
  if (entry.error) {
    return (
      <div
        className="p-2 rounded"
        style={{
          fontSize: 11, color: 'var(--danger)', lineHeight: 1.5,
          background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
          border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: entry.trace ? 4 : 0 }}>{entry.error}</div>
        {entry.trace && (
          <pre className="num overflow-x-auto" style={{ fontSize: 10, color: 'var(--text-2)', maxHeight: 160 }}>
            {entry.trace}
          </pre>
        )}
      </div>
    )
  }

  const out = entry.output
  if (!out) {
    return <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No output recorded.</div>
  }

  const datasets = out.datasets ? Object.entries(out.datasets) : []
  const showRawContext = !out.agent_response && out.context && Object.keys(out.context).length > 0
  return (
    <div className="space-y-2">
      {out.agent_response && (
        <div
          className="rounded p-2"
          style={{
            background: 'color-mix(in srgb, var(--accent) 8%, var(--bg-0))',
            border: '1px solid color-mix(in srgb, var(--accent) 26%, var(--border-soft))',
          }}
        >
          <div
            className="font-mono mb-1"
            style={{ fontSize: 9.5, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--text-3)' }}
          >
            agent response
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--text-0)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {out.agent_response}
          </p>
        </div>
      )}

      {datasets.map(([name, ds]) => (
        <div
          key={name}
          className="rounded overflow-hidden"
          style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
        >
          <div
            className="flex items-center justify-between px-2 py-1"
            style={{ background: 'var(--bg-2)', fontSize: 10.5 }}
          >
            <span className="num" style={{ color: 'var(--info)', fontWeight: 600 }}>{name}</span>
            <span className="num" style={{ color: 'var(--text-2)' }}>
              {ds.rows} rows · {ds.columns.length} cols
            </span>
          </div>
          {ds.sample.length > 0 && (
            <div className="overflow-x-auto">
              <table className="num" style={{ minWidth: '100%', fontSize: 10 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-1)' }}>
                    {ds.columns.slice(0, 5).map((c) => (
                      <th
                        key={c}
                        className="text-left px-2 py-1 whitespace-nowrap font-mono"
                        style={{ color: 'var(--text-3)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase' }}
                      >
                        {c}
                      </th>
                    ))}
                    {ds.columns.length > 5 && (
                      <th className="text-left px-2 py-1" style={{ color: 'var(--text-3)' }}>+{ds.columns.length - 5}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {ds.sample.slice(0, 3).map((row, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--border-soft)' }}>
                      {ds.columns.slice(0, 5).map((c) => {
                        const v = row[c]
                        const text = v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)
                        return (
                          <td
                            key={c}
                            className="px-2 py-1 whitespace-nowrap overflow-hidden"
                            style={{ color: 'var(--text-1)', maxWidth: 140, textOverflow: 'ellipsis' }}
                            title={text}
                          >
                            {text}
                          </td>
                        )
                      })}
                      {ds.columns.length > 5 && <td className="px-2 py-1" style={{ color: 'var(--text-3)' }}>…</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}

      {out.disposition != null && (
        <div className="flex flex-wrap gap-x-3 gap-y-1" style={{ fontSize: 11 }}>
          <KV k="disposition" v={out.disposition || '—'} vColor="var(--accent)" bold />
          <KV k="flags" v={String(out.flag_count ?? 0)} vColor="var(--text-0)" bold />
          {out.output_branch && <KV k="branch" v={out.output_branch} mono />}
        </div>
      )}

      {out.section && (
        <div className="rounded p-2" style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}>
          <div className="flex items-center gap-2 mb-1" style={{ fontSize: 10.5 }}>
            <span style={{ color: 'var(--text-3)' }}>section</span>
            <span className="num" style={{ color: 'var(--accent)' }}>{out.section.name}</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.55 }}>
            {out.section.narrative_preview}
          </p>
        </div>
      )}

      {out.executive_summary_preview && (
        <div className="rounded p-2" style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}>
          <div className="font-mono mb-1" style={{ fontSize: 9.5, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            executive summary · {out.executive_summary_chars} chars
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
            {out.executive_summary_preview}
          </p>
        </div>
      )}

      {out.report_path && (
        <div className="num" style={{ fontSize: 10.5, color: 'var(--success)' }}>
          report: {out.report_path}
        </div>
      )}

      {showRawContext && (
        <details>
          <summary
            className="cursor-pointer font-mono"
            style={{ fontSize: 9.5, color: 'var(--text-3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}
          >
            context · {Object.keys(out.context ?? {}).length}
          </summary>
          <pre
            className="num mt-1 p-2 rounded overflow-x-auto"
            style={{ fontSize: 10, color: 'var(--text-2)', background: 'var(--bg-0)', border: '1px solid var(--border-soft)', maxHeight: 160 }}
          >
            {JSON.stringify(out.context, null, 2)}
          </pre>
        </details>
      )}

      {datasets.length === 0
        && out.disposition == null
        && !out.section
        && !out.executive_summary_preview
        && !out.report_path
        && !out.agent_response
        && !showRawContext && (
          <pre
            className="num p-2 rounded overflow-x-auto"
            style={{ fontSize: 10, color: 'var(--text-1)', background: 'var(--bg-0)', border: '1px solid var(--border-soft)', maxHeight: 200 }}
          >
            {JSON.stringify(out, null, 2)}
          </pre>
        )}
    </div>
  )
}

function OutputCard({ entry, defaultOpen }: { entry: RunLogEntry; defaultOpen: boolean }) {
  const meta = useNodeRegistryStore((s) => s.nodeUI[entry.node_type as NodeType] ?? UNKNOWN_NODE_UI)
  const [open, setOpen] = useState(defaultOpen)
  const IconComp = meta.Icon
  const tone =
    entry.status === 'error' ? 'var(--danger)' :
    entry.status === 'running' ? 'var(--running)' :
    'var(--success)'

  return (
    <div
      className="rounded overflow-hidden"
      style={{
        background: 'var(--bg-1)',
        border: `1px solid color-mix(in srgb, ${tone} 22%, var(--border-soft))`,
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left"
        style={{ background: 'var(--bg-2)' }}
      >
        <span className="num" style={{ fontSize: 9.5, color: 'var(--text-3)', width: 16, textAlign: 'right' }}>
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
          <div className="truncate" style={{ fontSize: 11.5, color: 'var(--text-0)', fontWeight: 500 }}>
            {entry.label}
          </div>
        </div>
        <span className="num shrink-0" style={{ fontSize: 10.5, color: tone, fontWeight: 600 }}>
          {entry.status === 'running' ? 'running…' : formatDuration(entry.duration_ms)}
        </span>
        {open
          ? <ChevronDown size={12} style={{ color: 'var(--text-3)' }} />
          : <ChevronRight size={12} style={{ color: 'var(--text-3)' }} />}
      </button>
      {open && (
        <div className="px-2.5 py-2">
          <StageOutput entry={entry} />
        </div>
      )}
    </div>
  )
}

function FinalResult() {
  const result = useWorkflowStore((s) => s.runResult)
  const totalMs = useWorkflowStore((s) => s.runTotalMs)
  if (!result) return null

  const disp = result.disposition || 'COMPLETED'
  const tone =
    disp === 'ESCALATE' ? 'var(--danger)' :
    disp === 'REVIEW' ? 'var(--accent)' :
    'var(--success)'
  const downloadHref = result.download_url ? resolveDownloadHref(result.download_url) : null
  const sections = Object.entries(result.sections || {})

  return (
    <div className="px-4 py-4 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
      <SectionHeader>Final Output</SectionHeader>

      <div
        className="rounded-lg text-center"
        style={{
          padding: '12px 12px',
          background: `color-mix(in srgb, ${tone} 12%, var(--bg-1))`,
          border: `1px solid color-mix(in srgb, ${tone} 45%, transparent)`,
        }}
      >
        <div className="font-mono" style={{ fontSize: 18, fontWeight: 600, letterSpacing: '0.06em', color: tone }}>
          {disp}
        </div>
        <div className="font-mono mt-1" style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
          <span className="num" style={{ color: 'var(--text-1)' }}>{result.flag_count}</span> signal flags
          {totalMs != null && <> · <span className="num" style={{ color: 'var(--text-1)' }}>{formatDuration(totalMs)}</span></>}
        </div>
      </div>

      {downloadHref && (
        <a
          href={downloadHref}
          download={decodeURIComponent(downloadHref.split('/').pop() || 'report.xlsx')}
          target="_blank"
          rel="noopener"
          className="flex items-center justify-center gap-2 w-full rounded-lg"
          style={{
            padding: '9px 12px',
            fontSize: 12,
            fontWeight: 600,
            background: 'linear-gradient(180deg, var(--success) 0%, var(--success-lo) 100%)',
            color: '#FFFFFF',
            border: '1px solid color-mix(in srgb, var(--success-lo) 60%, black)',
            letterSpacing: '0.02em',
          }}
        >
          <Download size={13} strokeWidth={2.2} />
          <span>Download Excel Report</span>
        </a>
      )}

      {result.executive_summary && (
        <div>
          <div className="font-mono mb-1" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            <FileText size={10} strokeWidth={2} style={{ display: 'inline', marginRight: 4, verticalAlign: '-1px' }} />
            Executive summary
          </div>
          <div
            className="rounded p-2.5 whitespace-pre-wrap"
            style={{
              fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.6,
              background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
              maxHeight: 200, overflowY: 'auto',
            }}
          >
            {result.executive_summary}
          </div>
        </div>
      )}

      {result.datasets && result.datasets.length > 0 && (
        <div>
          <div className="font-mono mb-1" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            Datasets · {result.datasets.length}
          </div>
          <div className="flex flex-wrap gap-1">
            {result.datasets.map((ds) => (
              <span
                key={ds}
                className="num rounded px-2 py-0.5"
                style={{
                  fontSize: 10.5, color: 'var(--info)',
                  background: 'color-mix(in srgb, var(--info) 10%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--info) 25%, transparent)',
                }}
              >
                {ds}
              </span>
            ))}
          </div>
        </div>
      )}

      {sections.length > 0 && (
        <div className="space-y-1.5">
          <div className="font-mono" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            Sections · {sections.length}
          </div>
          {sections.map(([name, sec]) => (
            <details
              key={name}
              className="rounded"
              style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
            >
              <summary
                className="cursor-pointer px-2 py-1.5 num"
                style={{ fontSize: 11, color: 'var(--text-1)', fontWeight: 500 }}
              >
                {name.replace(/_/g, ' ')}
              </summary>
              <div className="px-2 pb-2">
                {Object.keys(sec.stats).length > 0 && (
                  <div className="mb-1.5" style={{ fontSize: 10, color: 'var(--text-3)' }}>
                    {Object.entries(sec.stats).map(([k, v]) => (
                      <span key={k} className="mr-3">
                        {k}: <span className="num" style={{ color: 'var(--text-1)' }}>{String(v)}</span>
                      </span>
                    ))}
                  </div>
                )}
                <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.55 }}>
                  {sec.narrative}
                </p>
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  )
}

export default function OutputView() {
  const runLog = useWorkflowStore((s) => s.runLog)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const runResult = useWorkflowStore((s) => s.runResult)

  const finished = runLog.filter((e) => e.status !== 'running')
  const hasAnything = finished.length > 0 || !!runResult

  return (
    <Shell
      icon={FileOutput}
      title="Output"
      eyebrow={isRunning ? 'STREAMING' : 'RESULTS'}
      accent="var(--success)"
      subtitle="Per-stage outputs and the final report from the latest run."
    >
      {!hasAnything ? (
        <Empty>
          <FileOutput size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
          <div style={{ color: 'var(--text-1)', fontWeight: 500, marginBottom: 4 }}>No output yet</div>
          <div>Outputs from each stage appear here as the run progresses.</div>
        </Empty>
      ) : (
        <>
          <div className="px-4 pt-3 pb-2">
            <SectionHeader>Stage outputs</SectionHeader>
          </div>
          <div className="px-3 pb-3 space-y-2">
            {finished.map((e) => (
              <OutputCard
                key={`out:${e.node_id}:${e.index}`}
                entry={e}
                defaultOpen={e.status === 'error'}
              />
            ))}
          </div>
          <FinalResult />
        </>
      )}
    </Shell>
  )
}
