/**
 * Copilot panel — the LLM-driven workflow author / editor.
 *
 * Three modes:
 *   • Generate — type intent, get a brand-new validated workflow.
 *   • Edit     — describe a change to the current canvas, copilot
 *                returns a patched DAG. The diff is previewed before
 *                applying.
 *   • Explain  — ask questions about the current workflow.
 *
 * Streaming: copilot.streamGenerate / streamEdit yield SSE events
 * (planning → tool_call → patch → done). This component renders them
 * progressively so the user sees the agent's reasoning instead of
 * staring at a spinner. Events are typed in `types/index.ts` —
 * unrecognised event kinds are ignored, not crashed on, so the
 * backend can add new event types without breaking old clients.
 */
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
  MessageSquare,
} from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { api } from '../../services/api'
import type { CopilotGuardrailsPayload } from '../../services/api'
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
  generating: 'Drafting workflow',
  auto_fixing: 'Deterministic auto-fix',
  critiquing: 'Validating & repairing',
  finalizing: 'Finalizing workflow',
  complete: 'Workflow generated',
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
  status: 'pending' | 'running' | 'done' | 'error'
  detail?: string
  /** Error codes emitted by the validator on this critic attempt. */
  errorCodes?: string[]
  /** True on the final `complete` frame when the validator approved the DAG. */
  approved?: boolean
  /** Descriptions of deterministic fixes applied during an auto_fixing pass. */
  appliedFixes?: string[]
}

/**
 * Build the full ghost skeleton of phases the agent is going to walk
 * through. We render this immediately on send so the user sees the
 * core plan upfront. Repair passes are progressive: show pass 1 as
 * the validation gate, and add pass 2/3 only if the backend actually
 * enters them.
 */
function buildPendingPhases(): PhaseState[] {
  return [
    { id: 'understanding', phase: 'understanding', label: PHASE_LABEL.understanding, status: 'pending' },
    { id: 'planning', phase: 'planning', label: PHASE_LABEL.planning, status: 'pending' },
    { id: 'generating', phase: 'generating', label: PHASE_LABEL.generating, status: 'pending' },
    {
      id: 'critiquing:1',
      phase: 'critiquing',
      label: `${PHASE_LABEL.critiquing} · pass 1`,
      status: 'pending',
    },
    { id: 'finalizing', phase: 'finalizing', label: PHASE_LABEL.finalizing, status: 'pending' },
    { id: 'complete', phase: 'complete', label: PHASE_LABEL.complete, status: 'pending' },
  ]
}

function shouldEditExistingWorkflow(prompt: string): boolean {
  const text = prompt.toLowerCase()
  if (/\b(create|generate|build|make|new)\b/.test(text)) return false
  return /\b(fix|repair|edit|update|change|modify|add|remove|delete|replace|this|current|existing|canvas)\b/.test(text)
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
    <div className="mb-3 space-y-1 relative">
      <div
        className="font-mono mb-1.5"
        style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}
      >
        Pipeline · {phases.length} {phases.length === 1 ? 'stage' : 'stages'}
      </div>
      {phases.map((p, idx) => {
        const isPending = p.status === 'pending'
        const isRunning = p.status === 'running'
        const isError = p.status === 'error'
        const isDone = p.status === 'done'
        const color = isError
          ? 'var(--danger)'
          : isDone
            ? 'var(--success)'
            : isRunning
              ? 'var(--accent)'
              : 'var(--text-3)'
        const IconComp = PHASE_ICON[p.phase] ?? Sparkles
        const last = idx === phases.length - 1
        return (
          <div key={p.id} className="relative" style={{ opacity: isPending ? 0.55 : 1 }}>
            {!last && (
              <span
                aria-hidden
                style={{
                  position: 'absolute', left: 9, top: 22, bottom: -4, width: 1,
                  background: 'var(--border-soft)',
                }}
              />
            )}
            <div
              className="flex items-start gap-2 px-2 py-1.5 rounded-md"
              style={{
                background: isPending ? 'transparent' : 'var(--bg-2)',
                border: `1px solid ${isPending ? 'var(--border-soft)' : `color-mix(in srgb, ${color} 22%, var(--border-soft))`}`,
                fontSize: 11.5,
              }}
          >
            <div
              className="shrink-0 mt-0.5 w-4 h-4 rounded-full flex items-center justify-center"
              style={{
                background: isPending ? 'transparent' : `color-mix(in srgb, ${color} 15%, transparent)`,
                border: `1px ${isPending ? 'dashed' : 'solid'} ${color}`,
                color,
              }}
            >
              {isPending ? null : isRunning ? (
                <span className="w-1.5 h-1.5 rounded-full live-blink" style={{ background: color }} />
              ) : isError ? (
                <XIcon size={9} strokeWidth={3} />
              ) : (
                <Check size={9} strokeWidth={3} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <IconComp size={11} strokeWidth={2} style={{ color: 'var(--text-2)' }} />
                <span style={{ color: 'var(--text-0)', fontWeight: 500 }}>{p.label}</span>
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
              </div>
              {p.detail && (
                <div className="truncate mt-0.5" style={{ color: 'var(--text-2)', fontSize: 10.5 }} title={p.detail}>
                  {p.detail}
                </div>
              )}
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
  const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  // Tight, row-style messages — small radius, monospace timestamp eyebrow,
  // matching the EntryRow / param row visual language used elsewhere in the
  // right panel.
  return (
    <div className="mb-3">
      <div
        className="font-mono mb-1 flex items-center gap-1.5"
        style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}
      >
        {isUser ? (
          <span style={{ color: 'var(--info)' }}>You</span>
        ) : (
          <>
            <Sparkles size={10} strokeWidth={2} style={{ color: 'var(--accent)' }} />
            <span style={{ color: 'var(--accent)' }}>Copilot</span>
          </>
        )}
        <span style={{ color: 'var(--text-3)' }}>· {time}</span>
      </div>
      <div
        className="rounded-md"
        style={{
          fontSize: 12,
          padding: '8px 10px',
          background: isUser
            ? 'color-mix(in srgb, var(--info) 8%, var(--bg-2))'
            : 'var(--bg-2)',
          color: 'var(--text-0)',
          border: `1px solid ${isUser
            ? 'color-mix(in srgb, var(--info) 25%, transparent)'
            : 'var(--border-soft)'}`,
          lineHeight: 1.55,
        }}
      >
        {isJson ? (
          <pre
            className="num overflow-x-auto whitespace-pre-wrap break-all"
            style={{ fontSize: 10.5, color: 'var(--success)', maxHeight: 260, overflowY: 'auto' }}
          >
            {msg.content}
          </pre>
        ) : (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        )}
      </div>
    </div>
  )
}

function TypingDots() {
  return (
    <div className="flex gap-1 px-3 py-2 rounded-xl rounded-bl-sm" style={{ background: 'var(--bg-2)', border: '1px solid var(--border)' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-1.5 h-1.5 rounded-full animate-bounce"
          style={{ background: 'var(--accent)', animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  )
}

function GuardrailsCard({ guardrails, error }: { guardrails: CopilotGuardrailsPayload | null; error: string | null }) {
  const caps = guardrails?.capabilities
  const skillNames = guardrails?.skills.map((s) => s.name).slice(0, 4).join(', ')
  return (
    <div
      style={{
        padding: '12px 14px',
        borderRadius: 10,
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="font-mono mb-2" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
        ACTIVE GUARDRAILS
      </div>
      {guardrails ? (
        <div style={{ fontSize: 12.5, color: 'var(--text-1)', lineHeight: 1.55 }}>
          <p>
            Copilot is constrained to{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.nodes.length} live nodes</span>,{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.data_sources.length} data catalogs</span>, and{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.skills.length} skills</span>.
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="num px-2 py-1 rounded" style={{ background: 'var(--bg-3)', color: caps?.upload_script_enabled ? 'var(--warning)' : 'var(--success)', border: '1px solid var(--border-soft)', fontSize: 10.5 }}>
              upload_script {caps?.upload_script_enabled ? 'on' : 'off'}
            </span>
            <span className="num px-2 py-1 rounded" style={{ background: 'var(--bg-3)', color: 'var(--text-2)', border: '1px solid var(--border-soft)', fontSize: 10.5 }}>
              signal modes: {caps?.allowed_signal_modes.join(', ')}
            </span>
          </div>
          {skillNames && (
            <p className="mt-2" style={{ color: 'var(--text-2)' }}>
              Skills in prompt: {skillNames}{guardrails.skills.length > 4 ? '...' : ''}
            </p>
          )}
        </div>
      ) : (
        <p style={{ fontSize: 12.5, color: error ? 'var(--danger)' : 'var(--text-2)', lineHeight: 1.55 }}>
          {error ?? 'Loading node, source, skill, and host capability guardrails...'}
        </p>
      )}
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
  const [guardrails, setGuardrails] = useState<CopilotGuardrailsPayload | null>(null)
  const [guardrailError, setGuardrailError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [copilotMessages, isLoading, phases])

  useEffect(() => {
    let active = true
    api.getCopilotGuardrails()
      .then((payload) => {
        if (!active) return
        setGuardrails(payload)
        setGuardrailError(null)
      })
      .catch((err: Error) => {
        if (!active) return
        setGuardrailError(err.message || 'Unable to load guardrails')
      })
    return () => { active = false }
  }, [])

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
      // The backend emits one critic frame per repair attempt and one
      // `auto_fixing` frame per deterministic repair pass. The ghost
      // skeleton already has critic rows id'd as `critiquing:<n>`; we
      // line them up by attempt number. Auto-fixing rows are inserted
      // right after the matching critic row, since they aren't part
      // of the static plan.
      const rowId =
        ev.phase === 'critiquing'
          ? `critiquing:${ev.attempt ?? prev.filter((p) => p.phase === 'critiquing').length}`
          : ev.phase === 'auto_fixing'
            ? `auto_fixing:${prev.filter((p) => p.phase === 'auto_fixing').length + 1}`
            : ev.phase
      const existing = prev.findIndex((p) => p.id === rowId)
      const errorCodes = (ev.validation_errors ?? []).map((e) => e.code)
      const approved =
        ev.phase === 'complete'
          ? ev.validation?.valid ?? undefined
          : ev.approved ?? undefined
      const nextLabel = ev.phase === 'complete'
        ? PHASE_LABEL.complete
        : label
      const nextDetail = ev.phase === 'complete' && ev.status === 'done' && ev.workflow
        ? `${ev.workflow.name}: ${ev.workflow.nodes.length} nodes / ${ev.workflow.edges?.length ?? 0} edges`
        : ev.detail
      const next: PhaseState = {
        id: rowId,
        phase: ev.phase,
        label: nextLabel,
        status: ev.status,
        detail: nextDetail,
        errorCodes: errorCodes.length ? errorCodes : undefined,
        approved,
        appliedFixes: ev.applied && ev.applied.length ? ev.applied : undefined,
      }
      if (existing >= 0) {
        const copy = [...prev]
        copy[existing] = next
        // If the backend reaches finalizing/complete, no more critic rows are
        // coming. The initial ghost plan still contains all requested repair
        // passes, so close any untouched ones instead of leaving a fake spinner.
        if (ev.phase === 'finalizing' || ev.phase === 'complete') {
          for (let i = 0; i < copy.length; i++) {
            if (copy[i].phase === 'critiquing' && copy[i].status !== 'done' && copy[i].status !== 'error') {
              copy[i] = {
                ...copy[i],
                status: 'done',
                detail: copy[i].detail ?? 'Validator clean',
              }
            }
          }
        }
        // When a phase completes, eagerly mark the next still-pending
        // row as running so users see the baton being passed even if
        // the backend hasn't yet emitted its `running` frame.
        if (ev.status === 'done') {
          for (let i = existing + 1; i < copy.length; i++) {
            if (copy[i].status === 'pending') {
              copy[i] = { ...copy[i], status: 'running' }
              break
            }
          }
        }
        return copy
      }
      // Auto-fix rows aren't in the skeleton — splice in next to the
      // most recent critic row so they cluster with their cause.
      if (ev.phase === 'auto_fixing') {
        const lastCritic = [...prev].reverse().findIndex((p) => p.phase === 'critiquing')
        const insertAt = lastCritic === -1 ? prev.length : prev.length - lastCritic
        const copy = [...prev]
        copy.splice(insertAt, 0, next)
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
    // Seed the timeline with the full ghost plan so the user sees the
    // whole pipeline upfront. Each row lights up as its event arrives.
    setPhases(useGenerate ? buildPendingPhases() : [])

    // Build context only for explicit edit/fix requests. Plain "create /
    // generate / build" prompts are greenfield and replace whatever is on
    // the canvas when the final validated workflow arrives.
    const editExisting = Boolean(currentWorkflow && shouldEditExistingWorkflow(msg))
    const ctxWorkflow = editExisting ? currentWorkflow : null
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
          useWorkflowStore.getState().resetRun()
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
      className="panel-glass flex flex-col relative shrink-0"
      style={{
        width: copilotWidth,
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
      {/* Header — matches RightPanel/Shell: icon + title + eyebrow + close. */}
      <div className="px-4 pt-4 pb-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Sparkles size={16} strokeWidth={2} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-0)' }}>Copilot</span>
          <span className="font-mono" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
            GEMINI
          </span>
          <div className="flex-1" />
          {/* Chat / Plan tabs aligned right */}
          <div className="flex items-center gap-1">
            <SegTab active={!useGenerate} onClick={() => setUseGenerate(false)} icon={<MessageSquare size={11} strokeWidth={2} />}>Chat</SegTab>
            <SegTab active={useGenerate} onClick={() => setUseGenerate(true)} icon={<ListChecks size={11} strokeWidth={2} />}>Plan</SegTab>
          </div>
          <button
            onClick={() => useWorkflowStore.getState().setRightPanelMode(null)}
            aria-label="Close panel"
            className="flex items-center justify-center"
            style={{
              width: 24, height: 24, borderRadius: 6,
              background: 'transparent', color: 'var(--text-3)',
              border: '1px solid var(--border-soft)',
              cursor: 'pointer',
            }}
          >
            <XIcon size={12} strokeWidth={2} />
          </button>
        </div>
        <div className="mt-2 font-mono" style={{ fontSize: 10, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
          {useGenerate ? `PLAN · ${criticIter} CRITIC PASSES` : 'CHAT'}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {copilotMessages.length === 0 && (
          <div className="space-y-5">
            {useGenerate && (
              <GuardrailsCard guardrails={guardrails} error={guardrailError} />
            )}
            <div>
              <div className="font-mono mb-2 px-1" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
                PROMPTS
              </div>
              <div className="space-y-2">
                {EXAMPLE_PROMPTS.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(p)}
                    className="w-full text-left transition-colors"
                    style={{
                      fontSize: 12.5,
                      padding: '12px 14px',
                      borderRadius: 10,
                      background: 'var(--bg-2)',
                      color: 'var(--text-1)',
                      border: '1px solid var(--border)',
                      lineHeight: 1.5,
                    }}
                    onMouseEnter={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-0)'
                      ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border-strong)'
                    }}
                    onMouseLeave={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-1)'
                      ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)'
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {copilotMessages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {(isLoading || phases.length > 0) && useGenerate && (
          <>
            <div className="mb-3">
              <GuardrailsCard guardrails={guardrails} error={guardrailError} />
            </div>
            {isLoading && phases.length === 0 && (
              <div className="flex items-center gap-2 mb-3">
                <CopilotAvatar size={24} />
                <TypingDots />
              </div>
            )}
            <PhaseTimeline phases={phases} />
          </>
        )}
        {isLoading && !useGenerate && (
          <div className="flex items-center gap-2 mb-3">
            <CopilotAvatar size={24} />
            <TypingDots />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t shrink-0" style={{ borderColor: 'var(--border)' }}>
        {/* Context indicator — a loaded workflow is available for explicit
            edit/fix prompts, but greenfield create/generate prompts replace it. */}
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
          const willEdit = shouldEditExistingWorkflow(input)
          const parts: string[] = [
            willEdit
              ? `Editing "${currentWorkflow.name}"`
              : `Generate will replace "${currentWorkflow.name}"`,
          ]
          if (hints.length) {
            parts.push(`${hints.length} error${hints.length === 1 ? '' : 's'}`)
          } else {
            parts.push(`${currentWorkflow.nodes.length} node${currentWorkflow.nodes.length === 1 ? '' : 's'}`)
          }
          if (selected) {
            parts.push(`"this" = ${selected.id} (${selected.type})`)
          }
          const label = parts.join(' · ')
          const title = hints.length
            ? hints.map((h) => `${(h.kind || 'error').toUpperCase()}${h.node_id ? ' @' + h.node_id : ''}: ${h.message}`).join('\n')
            : willEdit && selected
              ? `This edit prompt will attach the current canvas. Deictic references like "this" / "here" resolve to ${selected.id} (${selected.type}).`
              : willEdit
                ? 'This prompt will attach the current canvas so Copilot can make a targeted edit.'
                : 'Create/generate prompts start from a fresh workflow and replace the loaded canvas only after validation succeeds.'
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
          ⏎ send · ⇧⏎ newline
        </p>
      </div>
    </div>
  )
}

function SegTab({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5"
      style={{
        height: 30,
        padding: '0 12px',
        borderRadius: 7,
        fontSize: 12,
        fontWeight: 500,
        background: active ? 'var(--text-0)' : 'transparent',
        color: active ? 'var(--bg-0)' : 'var(--text-2)',
        border: active ? 'none' : '1px solid var(--border)',
        cursor: 'pointer',
      }}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}
