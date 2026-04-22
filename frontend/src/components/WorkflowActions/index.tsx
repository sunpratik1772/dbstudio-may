/**
 * Workflow action cluster for the topbar.
 *
 * Lives next to Workflows/DocChip so all workflow-level verbs (Run, Reset,
 * Save-as, Clear) are colocated — the bottom bar is now status-only.
 *
 * Save-as is the bridge between drafts and saved workflows:
 *   - If the current workflow is a draft (or unpersisted), Save-as prompts
 *     for a name and promotes it to /workflows via the backend.
 *   - If the current workflow is already saved, Save-as writes straight
 *     through (name editable) so renaming is trivial.
 *
 * The old payload popover is intentionally gone — we run with a sample
 * alert_payload by default and any per-node overrides live in the config
 * inspector.
 */
import { useMemo, useState } from 'react'
import {
  CirclePlay,
  CircleDot,
  RotateCcw,
  Eraser,
  AlertOctagon,
  AlertTriangle,
  Save,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { api } from '../../services/api'

const SAMPLE_PAYLOAD = {
  trader_id: 'T001',
  book: 'FX-SPOT',
  alert_date: '2024-01-15',
  currency_pair: 'EUR/USD',
  alert_id: 'ALT-001',
}

function slugify(name: string | undefined | null): string {
  const s = (name || 'workflow').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return s || 'workflow'
}

export default function WorkflowActions() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const setRunning = useWorkflowStore((s) => s.setRunning)
  const runError = useWorkflowStore((s) => s.runError)
  const setRunError = useWorkflowStore((s) => s.setRunError)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const applyRunEvent = useWorkflowStore((s) => s.applyRunEvent)
  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const runWarnings = useWorkflowStore((s) => s.runWarnings)
  const selectNode = useWorkflowStore((s) => s.selectNode)
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow)
  const markSaved = useWorkflowStore((s) => s.markSaved)
  const setRightPanelTab = useWorkflowStore((s) => s.setRightPanelTab)
  const setCopilotOpen = useWorkflowStore((s) => s.setCopilotOpen)
  const setCopilotDraft = useWorkflowStore((s) => s.setCopilotDraft)

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const progress = useMemo(() => {
    if (!runLog.length) return null
    const done = runLog.filter((e) => e.status === 'ok' || e.status === 'error').length
    const total = runLog[0]?.total ?? runLog.length
    return { done, total }
  }, [runLog])

  // Per-node runtime errors from the last run — the user's screenshot
  // lives here ("n14 (SECTION_SUMMARY): 'str' object has no…"). These
  // aren't surfaced as validationIssues because they only manifest at
  // runtime.
  const runtimeNodeErrors = useMemo(
    () => runLog.filter((e) => e.status === 'error' && e.error),
    [runLog],
  )

  /**
   * Hand a prefilled "fix this" prompt to the Copilot and open the
   * panel. The Copilot component picks up `copilotDraft` on its next
   * render, auto-attaches the current workflow + all error hints, and
   * the user can either hit send immediately or tweak the message
   * first. We don't auto-send so the user stays in control.
   */
  function handleFixWithCopilot(kind: 'validation' | 'runtime' | 'generic', focusText?: string) {
    const lead =
      kind === 'validation'
        ? 'Fix the validation errors in this workflow.'
        : kind === 'runtime'
          ? 'Fix the runtime error(s) in this workflow.'
          : 'Fix the error in this workflow.'
    const prompt = focusText ? `${lead} Focus on: ${focusText}` : lead
    setCopilotOpen(true)
    setCopilotDraft(prompt)
  }

  const runDisabled = !workflow || isRunning
  const hasRunState = runLog.length > 0 || runResult != null || runError != null
  const resetDisabled = isRunning || !hasRunState
  const clearCanvasDisabled = !workflow || isRunning
  const saveDisabled = !workflow || isRunning || saving

  async function handleRun() {
    if (!workflow) return
    setRunning(true)
    resetRun()
    setRunError(null)
    setRightPanelTab('runlog')
    try {
      await api.runWorkflowStream(workflow, SAMPLE_PAYLOAD, (ev) => applyRunEvent(ev))
    } catch (e) {
      setRunError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  function handleResetRun() {
    resetRun()
    setRunError(null)
  }

  function handleClearCanvas() {
    if (workflow && workflow.nodes.length > 0) {
      const ok = window.confirm(
        `Clear "${workflow.name}"? All ${workflow.nodes.length} node${
          workflow.nodes.length === 1 ? '' : 's'
        } and run results will be removed.`,
      )
      if (!ok) return
    }
    resetRun()
    setRunError(null)
    clearWorkflow()
  }

  async function handleSaveAs() {
    if (!workflow) return
    const suggested =
      sourceKind === 'saved' ? workflow.name : workflow.name || 'New workflow'
    const rawName = window.prompt('Save workflow as…', suggested)
    if (!rawName || !rawName.trim()) return
    const name = rawName.trim()
    // When saving an already-saved workflow back to the same filename,
    // reuse it. Otherwise generate a filename from the chosen name.
    const targetFilename =
      sourceKind === 'saved' && name === workflow.name
        ? (sourceFilename ?? `${slugify(name)}.json`)
        : `${slugify(name)}.json`

    setSaving(true)
    setSaveError(null)
    try {
      const updated = { ...workflow, name }
      if (sourceKind === 'draft' && sourceFilename) {
        // Promote draft → saved. Backend copies then deletes the draft.
        await api.saveWorkflow(targetFilename, updated)
        await api.deleteDraft(sourceFilename).catch(() => void 0)
      } else {
        await api.saveWorkflow(targetFilename, updated)
      }
      // Local state: rename in-memory + mark saved so autosave stops writing
      // to drafts.
      useWorkflowStore.setState({ workflow: updated })
      markSaved(targetFilename)
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      {/* Running status chip — moved up from the old RunConsole so operators
          see liveness at the top where the action buttons also live. */}
      {isRunning && (
        <div
          className="flex items-center gap-1.5 px-2"
          style={{
            height: 28,
            borderRadius: 7,
            background: 'color-mix(in srgb, var(--running) 10%, var(--bg-2))',
            border: '1px solid color-mix(in srgb, var(--running) 40%, transparent)',
            color: 'var(--running)',
          }}
        >
          <CircleDot size={10} strokeWidth={2.2} className="live-blink" />
          <span className="num" style={{ letterSpacing: '0.1em', fontSize: 10, fontWeight: 600 }}>
            RUNNING
          </span>
          {progress && (
            <span className="num" style={{ fontSize: 10.5, opacity: 0.95 }}>
              {progress.done}/{progress.total}
            </span>
          )}
        </div>
      )}

      {/* Run + Reset — two-button group, Run is primary (green gradient),
          Reset is attached to its right-hand side. */}
      <div
        className="flex items-stretch rounded-[8px] overflow-hidden"
        style={{
          border: runDisabled
            ? '1px solid var(--border)'
            : '1px solid color-mix(in srgb, var(--accent-lo) 60%, black)',
          boxShadow: runDisabled
            ? 'none'
            : '0 1px 0 rgba(255,255,255,0.25) inset, 0 8px 18px -10px color-mix(in srgb, var(--accent) 55%, transparent)',
        }}
      >
        <button
          onClick={handleRun}
          disabled={runDisabled}
          className="lift"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 7,
            fontSize: 12, fontWeight: 600,
            padding: '0 14px',
            height: 30,
            background: runDisabled
              ? 'var(--bg-2)'
              : 'linear-gradient(180deg, var(--accent-hi) 0%, var(--accent-lo) 100%)',
            color: runDisabled ? 'var(--text-3)' : '#0A0A0A',
            border: 'none',
            cursor: runDisabled ? (isRunning ? 'progress' : 'not-allowed') : 'pointer',
            letterSpacing: '0.02em',
            opacity: !workflow ? 0.6 : 1,
          }}
          title={!workflow ? 'Load or build a workflow first' : 'Run workflow (⌘⏎)'}
        >
          <CirclePlay size={13} strokeWidth={2.2} />
          <span>{isRunning ? 'Running…' : 'Run'}</span>
        </button>
        <div
          style={{
            width: 1,
            background: runDisabled
              ? 'var(--border-soft)'
              : 'color-mix(in srgb, black 35%, transparent)',
          }}
        />
        <button
          onClick={handleResetRun}
          disabled={resetDisabled}
          className="lift flex items-center justify-center"
          style={{
            padding: '0 9px',
            height: 30,
            background: resetDisabled
              ? 'var(--bg-2)'
              : 'linear-gradient(180deg, var(--accent-hi) 0%, var(--accent-lo) 100%)',
            color: resetDisabled ? 'var(--text-3)' : '#0A0A0A',
            border: 'none',
            cursor: resetDisabled ? 'not-allowed' : 'pointer',
            opacity: resetDisabled ? 0.5 : 1,
          }}
          title={resetDisabled ? 'No run results to reset' : 'Reset run state (keeps the workflow)'}
          aria-label="Reset run state"
        >
          <RotateCcw size={12} strokeWidth={2.2} />
        </button>
      </div>

      {/* Save-as — primary path from drafts to saved workflows. */}
      <button
        onClick={handleSaveAs}
        disabled={saveDisabled}
        className="lift flex items-center gap-1.5"
        style={{
          height: 30,
          padding: '0 11px',
          borderRadius: 7,
          fontSize: 11.5,
          fontWeight: 500,
          background: 'var(--bg-2)',
          color: saveDisabled ? 'var(--text-3)' : 'var(--text-1)',
          border: '1px solid var(--border)',
          letterSpacing: '0.01em',
          opacity: saveDisabled ? 0.55 : 1,
          cursor: saveDisabled ? 'not-allowed' : 'pointer',
        }}
        title={
          !workflow
            ? 'Nothing to save'
            : sourceKind === 'saved'
              ? 'Save (rename if you like)'
              : 'Save draft as a named workflow'
        }
      >
        {saving ? (
          <Loader2 size={12} strokeWidth={2} className="animate-spin" />
        ) : (
          <Save size={12} strokeWidth={2} />
        )}
        <span>{sourceKind === 'saved' ? 'Save' : 'Save as…'}</span>
      </button>

      {/* Clear canvas — secondary, subdued. */}
      <button
        onClick={handleClearCanvas}
        disabled={clearCanvasDisabled}
        className="lift flex items-center gap-1.5"
        style={{
          height: 30,
          padding: '0 10px',
          borderRadius: 7,
          fontSize: 11.5,
          fontWeight: 500,
          background: 'var(--bg-2)',
          color: clearCanvasDisabled ? 'var(--text-3)' : 'var(--text-1)',
          border: '1px solid var(--border)',
          letterSpacing: '0.01em',
          opacity: clearCanvasDisabled ? 0.5 : 1,
          cursor: clearCanvasDisabled ? 'not-allowed' : 'pointer',
        }}
        title={clearCanvasDisabled ? 'Nothing on the canvas to clear' : 'Clear the entire canvas'}
      >
        <Eraser size={12} strokeWidth={2} />
        <span>Clear</span>
      </button>

      {/* Validation issue chip — clickable, jumps to the first offending
          node so the user goes straight to the failing config field. */}
      {validationIssues && validationIssues.length > 0 && (
        <div className="flex items-stretch">
          <button
            onClick={() => {
              const firstWithNode = validationIssues.find((i) => i.node_id)
              if (firstWithNode?.node_id) {
                selectNode(firstWithNode.node_id)
                setRightPanelTab('config')
              }
            }}
            className="flex items-center gap-1.5 px-2 min-w-0"
            style={{
              height: 26,
              borderTopLeftRadius: 6,
              borderBottomLeftRadius: 6,
              background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
              borderRight: 'none',
              color: 'var(--danger)',
              fontSize: 10.5,
              maxWidth: 300,
              cursor: 'pointer',
            }}
            title={validationIssues
              .map((i) => `${i.severity.toUpperCase()} [${i.code}] ${i.node_id ? `(${i.node_id}) ` : ''}${i.message}`)
              .join('\n')}
          >
            <AlertOctagon size={10} strokeWidth={2.2} />
            <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>
              {validationIssues.length} validation issue{validationIssues.length === 1 ? '' : 's'}
            </span>
          </button>
          <FixWithCopilotButton
            onClick={() =>
              handleFixWithCopilot(
                'validation',
                validationIssues
                  .slice(0, 3)
                  .map((i) => `[${i.code}]${i.node_id ? ' @' + i.node_id : ''} ${i.message}`)
                  .join(' · '),
              )
            }
            title="Ask Copilot to fix these validation errors (attaches the current workflow + errors)"
          />
        </div>
      )}

      {/* Per-node runtime error chip — covers the case where the DAG
          validated clean but a handler threw at runtime. Keeps the
          "n14 (SECTION_SUMMARY): 'str' object has no…" message visible
          instead of burying it in the run log. */}
      {!validationIssues?.length && runtimeNodeErrors.length > 0 && (
        <div className="flex items-stretch">
          <button
            onClick={() => {
              const first = runtimeNodeErrors[0]
              if (first?.node_id) {
                selectNode(first.node_id)
                setRightPanelTab('runlog')
              }
            }}
            className="flex items-center gap-1.5 px-2 min-w-0"
            style={{
              height: 26,
              borderTopLeftRadius: 6,
              borderBottomLeftRadius: 6,
              background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
              borderRight: 'none',
              color: 'var(--danger)',
              fontSize: 10.5,
              maxWidth: 340,
              cursor: 'pointer',
            }}
            title={runtimeNodeErrors
              .map((e) => `${e.node_id} (${e.node_type}): ${e.error}`)
              .join('\n')}
          >
            <AlertOctagon size={10} strokeWidth={2.2} />
            <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>
              {(() => {
                const first = runtimeNodeErrors[0]
                const rest = runtimeNodeErrors.length - 1
                const short = `${first.node_id} (${first.node_type}): ${first.error}`
                return rest > 0 ? `${short} · +${rest} more` : short
              })()}
            </span>
          </button>
          <FixWithCopilotButton
            onClick={() =>
              handleFixWithCopilot(
                'runtime',
                runtimeNodeErrors
                  .slice(0, 3)
                  .map((e) => `${e.node_id} (${e.node_type}): ${e.error}`)
                  .join(' · '),
              )
            }
            title="Ask Copilot to fix these runtime errors (attaches the workflow + per-node failures)"
          />
        </div>
      )}

      {/* Generic run/save error — shown when the failure isn't structured
          validation (e.g. network error, backend 500 mid-run). */}
      {!validationIssues?.length && !runtimeNodeErrors.length && (runError || saveError) && (
        <div className="flex items-stretch">
          <div
            className="flex items-center gap-1.5 px-2 min-w-0"
            style={{
              height: 26,
              borderTopLeftRadius: 6,
              borderBottomLeftRadius: 6,
              background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
              borderRight: 'none',
              color: 'var(--danger)',
              fontSize: 10.5,
              maxWidth: 260,
            }}
            title={runError || saveError || ''}
          >
            <AlertOctagon size={10} strokeWidth={2.2} />
            <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>
              {runError || saveError}
            </span>
          </div>
          {/* Fix-with-Copilot only makes sense when we have a workflow
              to edit — raw save errors against an empty canvas won't. */}
          {workflow && (
            <FixWithCopilotButton
              onClick={() => handleFixWithCopilot('generic', runError || saveError || undefined)}
              title="Ask Copilot to diagnose this error (attaches the current workflow)"
            />
          )}
        </div>
      )}

      {/* Warning chip — only shown after a successful run that produced
          non-blocking warnings (e.g. inferred param type mismatches). */}
      {runWarnings && runWarnings.length > 0 && !validationIssues?.length && (
        <div
          className="flex items-center gap-1.5 px-2 min-w-0"
          style={{
            height: 26,
            borderRadius: 6,
            background: 'color-mix(in srgb, var(--warning, #d97706) 12%, transparent)',
            border: '1px solid color-mix(in srgb, var(--warning, #d97706) 40%, transparent)',
            color: 'var(--warning, #d97706)',
            fontSize: 10.5,
            maxWidth: 260,
          }}
          title={runWarnings.map((w) => `[${w.code}] ${w.message}`).join('\n')}
        >
          <AlertTriangle size={10} strokeWidth={2.2} />
          <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>
            {runWarnings.length} warning{runWarnings.length === 1 ? '' : 's'}
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * Inline "Fix with Copilot" affordance glued to the right edge of an
 * error chip. Opens the Copilot panel and hands it a scoped prompt;
 * the Copilot auto-attaches the current workflow + error hints so
 * the LLM has the full context without the user retyping anything.
 */
function FixWithCopilotButton({
  onClick,
  title,
}: {
  onClick: () => void
  title: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label="Fix with Copilot"
      className="flex items-center gap-1 px-2 lift"
      style={{
        height: 26,
        borderTopRightRadius: 6,
        borderBottomRightRadius: 6,
        background: 'linear-gradient(145deg, var(--accent-hi), var(--accent-lo))',
        color: '#0A0A0A',
        border: '1px solid color-mix(in srgb, var(--accent-lo) 60%, black)',
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '0.02em',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      <Sparkles size={10} strokeWidth={2.4} />
      <span>Fix with Copilot</span>
    </button>
  )
}
