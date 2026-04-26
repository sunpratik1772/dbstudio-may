import { useState, useRef, useEffect } from 'react'
import ResizeHandle from '../ResizeHandle'
import type { LucideIcon } from 'lucide-react'
import {
  Sparkles,
  Brain,
  ListChecks,
  Hammer,
  Search,
  Wand2,
  Wrench,
  CheckCircle2,
  XCircle,
  Check,
  X as XIcon,
  ArrowUp,
  Loader2,
} from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { api } from '../../services/api'
import type {
  CopilotMessage,
  CopilotStreamEvent,
  CopilotPhase,
  CopilotErrorHint,
  RunLogEntry,
  ValidationIssue,
} from '../../types'

const PHASE_LABEL: Record<CopilotPhase, string> = {
  understanding: 'Understanding the problem',
  planning: 'Retrieving skills & contracts',
  generating: 'Creating nodes',
  auto_fixing: 'Deterministic auto-fix',
  critiquing: 'Reviewing workflow',
  finalizing: 'Finalizing workflow',
  complete: 'Done',
  error: 'Error',
}

const PHASE_ICON: Record<CopilotPhase, LucideIcon> = {
  understanding: Brain,
  planning: ListChecks,
  generating: Hammer,
  auto_fixing: Wrench,
  critiquing: Search,
  finalizing: Wand2,
  complete: CheckCircle2,
  error: XCircle,
}

interface PhaseState {
  id: string
  phase: CopilotPhase
  label: string
  status: 'running' | 'done' | 'error'
  detail?: string
  /** Error codes emitted by the validator on this critic attempt. */
  errorCodes?: string[]
  /** True on the final `complete` frame when the validator approved the DAG. */
  approved?: boolean
  /** Descriptions of deterministic fixes applied during an auto_fixing pass. */
  appliedFixes?: string[]
}

function CopilotAvatar({ size = 24 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-lg shrink-0"
      style={{
        width: size,
        height: size,
        background: 'linear-gradient(145deg, var(--accent-hi), var(--accent-lo))',
        color: '#0A0A0A',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.22)',
      }}
    >
      <Sparkles size={Math.round(size * 0.54)} strokeWidth={2.2} />
    </div>
  )
}

function PhaseTimeline({ phases }: { phases: PhaseState[] }) {
  if (phases.length === 0) return null
  return (
    <div className="mb-2 space-y-2">
      {phases.map((p) => {
        const isRunning = p.status === 'running'
        const isError = p.status === 'error'
        const color = isError ? 'var(--danger)' : p.status === 'done' ? 'var(--success)' : 'var(--accent)'
        const IconComp = PHASE_ICON[p.phase] ?? Sparkles
        return (
            <div
              key={p.id}
              className="flex min-w-0 items-start gap-2 rounded-lg px-2.5 py-2"
              style={{
                background: 'color-mix(in srgb, var(--text-0) 4.5%, var(--bg-2))',
                border: `1.5px solid color-mix(in srgb, ${color} 50%, var(--border))`,
                fontSize: 11.5,
                boxShadow: '0 1px 0 color-mix(in srgb, var(--text-0) 5%, transparent)',
              }}
            >
            <div
              className="shrink-0 mt-0.5 w-4 h-4 rounded-full flex items-center justify-center"
              style={{
                background: `color-mix(in srgb, ${color} 22%, var(--bg-1))`,
                border: `1.5px solid color-mix(in srgb, ${color} 70%, var(--bg-0))`,
                color,
                boxShadow: 'inset 0 1px 0 color-mix(in srgb, #fff 12%, transparent)',
              }}
            >
              {isRunning ? (
                <Loader2 size={10} strokeWidth={2.5} className="animate-spin" style={{ color }} />
              ) : isError ? (
                <XIcon size={9} strokeWidth={3} />
              ) : (
                <Check size={9} strokeWidth={3} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 min-w-0">
                <IconComp size={11} strokeWidth={2} className="shrink-0" style={{ color: 'var(--text-2)' }} />
                <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{p.label}</span>
                {p.approved === true && (
                  <span
                    className="num"
                    style={{
                      fontSize: 9,
                      letterSpacing: '0.08em',
                      padding: '1px 5px',
                      borderRadius: 4,
                      background: 'color-mix(in srgb, var(--success) 18%, transparent)',
                      color: 'var(--success)',
                      border: '1px solid color-mix(in srgb, var(--success) 40%, transparent)',
                    }}
                  >
                    VALID
                  </span>
                )}
                {p.detail && (
                  <>
                    <span className="shrink-0" style={{ color: 'var(--text-3)', fontSize: 11, fontWeight: 400 }} aria-hidden>
                      —
                    </span>
                    <span
                      className="truncate min-w-0"
                      style={{ color: 'var(--text-2)', fontSize: 10.5, fontWeight: 400, flex: '1 1 120px' }}
                      title={p.detail}
                    >
                      {p.detail}
                    </span>
                  </>
                )}
              </div>
              {p.errorCodes && p.errorCodes.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {p.errorCodes.slice(0, 6).map((code, i) => (
                    <span
                      key={`${code}-${i}`}
                      className="num"
                      style={{
                        fontSize: 9,
                        letterSpacing: '0.04em',
                        padding: '1px 5px',
                        borderRadius: 4,
                        background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                        color: 'var(--danger)',
                        border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
                      }}
                      title={code}
                    >
                      {code}
                    </span>
                  ))}
                  {p.errorCodes.length > 6 && (
                    <span className="num" style={{ fontSize: 9, color: 'var(--text-3)' }}>
                      +{p.errorCodes.length - 6}
                    </span>
                  )}
                </div>
              )}
              {p.appliedFixes && p.appliedFixes.length > 0 && (
                <div className="flex flex-col gap-0.5 mt-1">
                  {p.appliedFixes.slice(0, 4).map((fix, i) => (
                    <span
                      key={`fix-${i}`}
                      style={{
                        fontSize: 10,
                        color: 'var(--success)',
                        fontFamily: 'var(--mono, ui-monospace)',
                      }}
                      title={fix}
                    >
                      → {fix}
                    </span>
                  ))}
                  {p.appliedFixes.length > 4 && (
                    <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
                      +{p.appliedFixes.length - 4} more
                    </span>
                  )}
                </div>
              )}
            </div>
            </div>
        )
      })}
    </div>
  )
}

/**
 * Roll up every error the UI is currently showing into the
 * `CopilotErrorHint[]` shape the backend's edit-mode prompt expects.
 * Sources, in priority order:
 *   1. Pre-flight validator issues (if any) — deterministic, structured.
 *   2. Per-node runtime errors from the last run (from runLog).
 *   3. Generic runError (used for network / non-structured failures).
 *
 * De-duplication is keyed on (node_id, message). Capped at 20 hints so
 * a pathological run doesn't blow the prompt context.
 */
function collectErrorHints(
  validationIssues: ValidationIssue[] | null,
  runLog: RunLogEntry[],
  runError: string | null,
): CopilotErrorHint[] {
  const hints: CopilotErrorHint[] = []
  const seen = new Set<string>()

  const push = (h: CopilotErrorHint) => {
    const key = `${h.node_id ?? ''}::${h.message}`
    if (seen.has(key)) return
    seen.add(key)
    hints.push(h)
  }

  for (const issue of validationIssues ?? []) {
    push({
      kind: 'validation',
      code: issue.code,
      node_id: issue.node_id ?? undefined,
      severity: issue.severity,
      message: issue.message,
    })
  }

  for (const entry of runLog) {
    if (entry.status !== 'error' || !entry.error) continue
    push({
      kind: 'runtime',
      node_id: entry.node_id,
      severity: 'error',
      // Include the node type in the message so the LLM doesn't have
      // to cross-reference it against the attached DAG to diagnose.
      message: entry.node_type
        ? `${entry.node_type} (${entry.node_id}): ${entry.error}`
        : `${entry.node_id}: ${entry.error}`,
    })
  }

  if (runError && !validationIssues?.length) {
    // Only include the generic runError if the structured validator
    // path didn't already cover the failure — otherwise we'd double-
    // report the same underlying issue.
    push({ kind: 'runtime', severity: 'error', message: runError })
  }

  return hints.slice(0, 20)
}

const EXAMPLE_PROMPTS = [
  'Create an FX Front-Running workflow for trader T001 in EUR/USD with 3 signals and a 3-iteration critic loop',
  'Create an FI Wash Trade workflow with counterparty circularity and price neutrality signals',
  'Add a SPOOFING signal to the current workflow and update the decision thresholds',
  'Generate an FI Layering workflow with cascading price level detection',
]

function MessageBubble({ msg }: { msg: CopilotMessage }) {
  const isUser = msg.role === 'user'
  const isJson = !isUser && msg.content.trim().startsWith('{')

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && <div className="mr-2 mt-0.5"><CopilotAvatar size={24} /></div>}
      <div
        className={`rounded-xl px-3 py-2 leading-relaxed ${isUser ? 'rounded-br-sm' : 'rounded-bl-sm'}`}
        style={{
          fontSize: 12,
          background: isUser
            ? 'color-mix(in srgb, var(--info) 22%, var(--bg-2))'
            : 'color-mix(in srgb, var(--text-0) 3%, var(--bg-2))',
          color: 'var(--text-0)',
          border: `1px solid ${isUser ? 'color-mix(in srgb, var(--info) 42%, var(--border))' : 'var(--border)'}`,
          maxWidth: '85%',
        }}
      >
        {isJson ? (
          <pre
            className="font-mono overflow-x-auto whitespace-pre-wrap break-all"
            style={{ fontSize: 11, color: 'var(--success)', maxHeight: 300, overflowY: 'auto' }}
          >
            {msg.content}
          </pre>
        ) : (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        )}
        <div className="num mt-1" style={{ color: 'var(--text-3)', fontSize: 10 }}>
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-xl rounded-bl-sm"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--border)' }}
    >
      <Loader2 size={14} strokeWidth={2.2} className="animate-spin shrink-0" style={{ color: 'var(--accent)' }} />
    </div>
  )
}

export default function Copilot() {
  const { copilotMessages, addCopilotMessage, clearCopilotMessages, setWorkflow } = useWorkflowStore()
  const copilotWidth = useWorkflowStore((s) => s.copilotWidth)
  const setCopilotWidth = useWorkflowStore((s) => s.setCopilotWidth)
  // Auto-attach context for edit-mode on every send. We subscribe to
  // these in the component so the values are always current — the
  // store is a single source of truth for the canvas state.
  const currentWorkflow = useWorkflowStore((s) => s.workflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const runError = useWorkflowStore((s) => s.runError)
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId)
  const copilotDraft = useWorkflowStore((s) => s.copilotDraft)
  const setCopilotDraft = useWorkflowStore((s) => s.setCopilotDraft)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [useGenerate, setUseGenerate] = useState(true)
  const [criticIter, setCriticIter] = useState(3)
  const [phases, setPhases] = useState<PhaseState[]>([])
  const messagesScrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = messagesScrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [copilotMessages, isLoading, phases])

  // "Fix with Copilot" CTAs elsewhere in the app set copilotDraft; we
  // adopt it into our local textarea state and clear the store slot so
  // it only fires once. Also focus the textarea so the user can either
  // hit Enter or tweak the prefilled text before sending.
  useEffect(() => {
    if (copilotDraft && copilotDraft !== input) {
      setInput(copilotDraft)
      setCopilotDraft(null)
      // Defer focus until after React re-renders the textarea with
      // the new value.
      requestAnimationFrame(() => inputRef.current?.focus())
    }
    // Intentional: only react to copilotDraft changes, not local input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copilotDraft])

  function handlePhaseEvent(ev: CopilotStreamEvent) {
    setPhases((prev) => {
      const label = ev.label || PHASE_LABEL[ev.phase] || ev.phase
      // The backend now emits one critic frame per repair attempt,
      // and one `auto_fixing` frame per deterministic repair pass.
      // Using `attempt` (when present) as the row key means repeated
      // runs produce distinct rows rather than stomping over the same
      // timeline row.
      const rowId =
        ev.phase === 'critiquing'
          ? `critiquing:${ev.attempt ?? label}`
          : ev.phase === 'auto_fixing'
            ? `auto_fixing:${prev.filter((p) => p.phase === 'auto_fixing').length + 1}`
            : ev.phase
      const existing = prev.findIndex((p) => p.id === rowId)
      const errorCodes = (ev.validation_errors ?? []).map((e) => e.code)
      const approved =
        ev.phase === 'complete'
          ? ev.validation?.valid ?? undefined
          : ev.approved ?? undefined
      const next: PhaseState = {
        id: rowId,
        phase: ev.phase,
        label,
        status: ev.status,
        detail: ev.detail,
        errorCodes: errorCodes.length ? errorCodes : undefined,
        approved,
        appliedFixes: ev.applied && ev.applied.length ? ev.applied : undefined,
      }
      if (existing >= 0) {
        const copy = [...prev]
        copy[existing] = next
        return copy
      }
      return [...prev, next]
    })
  }

  async function send() {
    const msg = input.trim()
    if (!msg || isLoading) return
    setInput('')

    const userMsg: CopilotMessage = { role: 'user', content: msg, timestamp: new Date() }
    addCopilotMessage(userMsg)
    setIsLoading(true)
    setPhases([])

    // Build the edit-mode context. When the canvas has a workflow
    // loaded we always attach it — the backend treats the absence of
    // current_workflow as "greenfield" and its presence as "edit this
    // DAG". We collect error hints from three sources the user would
    // want the Copilot to see: validator issues, per-node runtime
    // failures from the last run, and any generic runError the UI is
    // already showing in the topbar chip.
    const ctxWorkflow = currentWorkflow ?? null
    const errorHints = ctxWorkflow
      ? collectErrorHints(validationIssues, runLog, runError)
      : null

    try {
      let replyText: string
      if (useGenerate) {
        let finalWorkflow: NonNullable<CopilotStreamEvent['workflow']> | null = null
        let finalError: string | null = null
        let finalValidation: CopilotStreamEvent['validation'] | null = null

        await api.copilotGenerateStream(
          msg,
          criticIter,
          (ev) => {
            handlePhaseEvent(ev)
            if (ev.phase === 'complete' && ev.workflow) finalWorkflow = ev.workflow
            if (ev.phase === 'complete' && ev.validation) finalValidation = ev.validation
            if (ev.phase === 'error') finalError = ev.detail || 'Generation failed'
          },
          undefined,
          ctxWorkflow,
          errorHints,
          ctxWorkflow ? selectedNodeId : null,
        )

        if (finalWorkflow) {
          setWorkflow(finalWorkflow)
          const wf = finalWorkflow as NonNullable<CopilotStreamEvent['workflow']>
          const vr = finalValidation as CopilotStreamEvent['validation'] | null
          const header = `Workflow generated: **${wf.name}**\n${wf.nodes.length} nodes, ${wf.edges?.length ?? 0} edges`
          const validationLine = vr
            ? vr.valid
              ? '\n\nValidator: clean ✓'
              : `\n\nValidator: ${vr.errors.length} unresolved issue(s): ${vr.errors
                  .slice(0, 5)
                  .map((e) => e.code + (e.node_id ? `@${e.node_id}` : ''))
                  .join(', ')}`
            : ''
          replyText = `${header}${validationLine}\n\nLoaded into the canvas.\n\n${JSON.stringify(wf, null, 2)}`
        } else {
          replyText = `Generation failed: ${finalError ?? 'no workflow produced'}`
        }
      } else {
        const result = await api.copilotChat(msg)
        replyText = result.reply
      }

      addCopilotMessage({ role: 'assistant', content: replyText, timestamp: new Date() })
    } catch (e) {
      addCopilotMessage({
        role: 'assistant',
        content: `Error: ${(e as Error).message}\n\nMake sure the backend is running at http://localhost:8000`,
        timestamp: new Date(),
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      ref={rootRef}
      className="flex flex-col relative shrink-0 min-h-0"
      style={{
        width: copilotWidth,
        background: 'var(--bg-1)',
        borderLeft: '1px solid var(--border)',
        height: '100%',
      }}
    >
      {/* Drag the left edge to resize the copilot (VSCode-style). */}
      <ResizeHandle
        edge="left"
        ariaLabel="Resize copilot panel"
        onResize={(clientX) => {
          const right = rootRef.current?.getBoundingClientRect().right ?? window.innerWidth
          setCopilotWidth(right - clientX)
        }}
      />
      {/* Header */}
      <div className="px-3 py-2.5 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <CopilotAvatar size={24} />
            <div className="flex flex-col min-w-0">
              <span className="display" style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-0)', lineHeight: 1.2 }}>
                Copilot
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: 9.5,
                  color: 'var(--text-3)',
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                  marginTop: 1,
                }}
              >
                gemini — plan + chat
              </span>
            </div>
          </div>
          <button
            onClick={() => { clearCopilotMessages(); api.copilotChat('', true).catch(() => {}) }}
            className="eyebrow lift"
            style={{ color: 'var(--text-2)' }}
          >
            Clear
          </button>
        </div>
        <p style={{ fontSize: 11.5, color: 'var(--text-2)', marginTop: 6, lineHeight: 1.45 }}>
          Describe a surveillance scenario and I'll generate a validated workflow.
        </p>
      </div>

      {/* Mode toggle */}
      <div className="px-3 py-2 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={useGenerate}
              onChange={(e) => setUseGenerate(e.target.checked)}
              className="rounded"
              style={{ accentColor: 'var(--accent)' }}
            />
            <span style={{ fontSize: 11, color: 'var(--text-1)' }}>Generate + Critic</span>
          </label>
          {useGenerate && (
            <div className="flex items-center gap-1.5">
              <span className="eyebrow" style={{ color: 'var(--text-2)' }}>Iter</span>
              <select
                value={criticIter}
                onChange={(e) => setCriticIter(Number(e.target.value))}
                className="num rounded px-1.5 py-0.5"
                style={{
                  fontSize: 11,
                  background: 'var(--bg-2)',
                  color: 'var(--text-0)',
                  border: '1px solid var(--border)',
                }}
              >
                {[1, 2, 3, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div ref={messagesScrollRef} className="flex-1 min-h-0 overflow-y-auto px-3 pt-2 pb-3">
        {copilotMessages.length === 0 && (
          <div className="space-y-2">
            <p className="eyebrow text-center mb-4" style={{ color: 'var(--text-2)' }}>Try an example prompt</p>
            {EXAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setInput(p)}
                className="w-full text-left px-3 py-2 rounded-lg transition-colors leading-relaxed lift"
                style={{
                  fontSize: 11.5,
                  background: 'var(--bg-2)',
                  color: 'var(--text-1)',
                  border: '1px solid var(--border)',
                  lineHeight: 1.45,
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-0)' }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-1)' }}
              >
                {p}
              </button>
            ))}
          </div>
        )}

        {copilotMessages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {(isLoading || phases.length > 0) && useGenerate && (
          <>
            {isLoading && phases.length === 0 && (
              <div className="flex items-center gap-2 mb-3">
                <CopilotAvatar size={24} />
                <TypingIndicator />
              </div>
            )}
            <PhaseTimeline phases={phases} />
          </>
        )}
        {isLoading && !useGenerate && (
          <div className="flex items-center gap-2 mb-3">
            <CopilotAvatar size={24} />
            <TypingIndicator />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3 border-t shrink-0" style={{ borderColor: 'var(--border)' }}>
        {/* Context indicator — when the canvas has a workflow we're
            going to attach it (and any errors) to the next send. Let
            the user see that so they know "fix this" operates on what
            they're looking at. */}
        {currentWorkflow && (() => {
          const hints = collectErrorHints(validationIssues, runLog, runError)
          const selected = selectedNodeId
            ? currentWorkflow.nodes.find((n) => n.id === selectedNodeId)
            : null
          const chipBg = hints.length
            ? 'color-mix(in srgb, var(--danger) 12%, transparent)'
            : 'color-mix(in srgb, var(--accent) 10%, transparent)'
          const chipBorder = hints.length
            ? 'color-mix(in srgb, var(--danger) 35%, transparent)'
            : 'color-mix(in srgb, var(--accent) 30%, transparent)'
          const chipColor = hints.length ? 'var(--danger)' : 'var(--accent)'
          const parts: string[] = [`Editing "${currentWorkflow.name}"`]
          if (hints.length) {
            parts.push(`${hints.length} error${hints.length === 1 ? '' : 's'}`)
          } else {
            parts.push(`${currentWorkflow.nodes.length} node${currentWorkflow.nodes.length === 1 ? '' : 's'}`)
          }
          if (selected) {
            parts.push(`"this" = ${selected.id} (${selected.type})`)
          }
          const label = parts.join(' — ')
          const title = hints.length
            ? hints.map((h) => `${(h.kind || 'error').toUpperCase()}${h.node_id ? ' @' + h.node_id : ''}: ${h.message}`).join('\n')
            : selected
              ? `The current canvas workflow is attached. Deictic references like "this" / "here" resolve to ${selected.id} (${selected.type}).`
              : 'The current canvas workflow is sent with every prompt so Copilot can make targeted edits.'
          return (
            <div
              className="flex items-center gap-1.5 mb-2 px-2 py-1 rounded-md"
              style={{
                fontSize: 10.5,
                background: chipBg,
                border: `1px solid ${chipBorder}`,
                color: chipColor,
              }}
              title={title}
            >
              <Wrench size={10} strokeWidth={2.2} />
              <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>{label}</span>
            </div>
          )
        })()}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
            }}
            placeholder={
              currentWorkflow
                ? 'Describe a fix or edit (the canvas workflow is attached)…'
                : 'Describe a surveillance scenario…'
            }
            rows={2}
            className="flex-1 rounded-lg px-3 py-2 resize-none outline-none transition-colors"
            style={{
              fontSize: 12,
              background: 'var(--bg-2)',
              color: 'var(--text-0)',
              border: '1px solid var(--border)',
              lineHeight: 1.5,
            }}
            onFocus={(e) => { (e.target as HTMLTextAreaElement).style.border = '1px solid color-mix(in srgb, var(--accent) 50%, transparent)' }}
            onBlur={(e) => { (e.target as HTMLTextAreaElement).style.border = '1px solid var(--border)' }}
          />
          <button
            onClick={send}
            disabled={isLoading || !input.trim()}
            className="px-3 py-2 rounded-lg self-end flex items-center justify-center lift"
            style={{
              background: isLoading || !input.trim()
                ? 'var(--bg-3)'
                : 'linear-gradient(145deg, var(--accent-hi), var(--accent-lo))',
              color: isLoading || !input.trim() ? 'var(--text-3)' : '#0A0A0A',
              cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer',
              minWidth: 40, minHeight: 36,
              border: isLoading || !input.trim() ? '1px solid var(--border)' : '1px solid color-mix(in srgb, var(--accent-lo) 60%, black)',
            }}
            aria-label="Send"
          >
            {isLoading
              ? <span className="num">…</span>
              : <ArrowUp size={14} strokeWidth={2.5} />}
          </button>
        </div>
        <p className="num mt-2" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.02em' }}>
          ⏎ send — ⇧⏎ newline
        </p>
      </div>
    </div>
  )
}
