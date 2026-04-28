/**
 * Top action bar.
 *
 * Owns: workflow name editing, theme toggle, drawer toggle (saved
 * workflows), import/export YAML, validate, save, and run.
 * All actions delegate to workflowStore — this component is mostly a
 * styled set of buttons.
 *
 * "Run" calls `streamRun` (services/api.ts) and pipes events into the
 * store; the canvas + RunLogView subscribe and animate as events
 * arrive. The button itself only flips between idle / loading state.
 */
import { useMemo, useRef, useState } from 'react'
import {
  Sun, Moon, LayoutTemplate, Upload, Download, ShieldCheck, Save, Play, Loader2, Trash2,
} from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { useThemeStore } from '../../store/themeStore'
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

export default function Topbar() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const setRunning = useWorkflowStore((s) => s.setRunning)
  const setRunError = useWorkflowStore((s) => s.setRunError)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const applyRunEvent = useWorkflowStore((s) => s.applyRunEvent)
  const setRightPanelMode = useWorkflowStore((s) => s.setRightPanelMode)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const setValidationIssues = useWorkflowStore((s) => s.setValidationIssues)
  const markSaved = useWorkflowStore((s) => s.markSaved)
  const setWorkflow = useWorkflowStore((s) => s.setWorkflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runError = useWorkflowStore((s) => s.runError)
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow)
  const resetRunStore = useWorkflowStore((s) => s.resetRun)

  function handleClear() {
    resetRunStore()
    clearWorkflow()
  }
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validatedSignature, setValidatedSignature] = useState<string | null>(null)
  const [lastValidationValid, setLastValidationValid] = useState<boolean | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)

  const nodeCount = workflow?.nodes.length ?? 0
  const edgeCount = workflow?.edges.length ?? 0
  const title = workflow?.name || 'Untitled workflow'
  const workflowSignature = useMemo(() => workflow ? JSON.stringify(workflow) : null, [workflow])

  async function handleRun() {
    if (!workflow) return
    setRunning(true)
    resetRun()
    setRunError(null)
    setRightPanelMode('runlog')
    try {
      await api.runWorkflowStream(workflow, SAMPLE_PAYLOAD, (ev) => applyRunEvent(ev))
    } catch (e) {
      setRunError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  async function handleSave() {
    if (!workflow) return
    const suggested = sourceKind === 'saved' ? workflow.name : workflow.name || 'New workflow'
    const rawName = window.prompt('Save workflow as…', suggested)
    if (!rawName || !rawName.trim()) return
    const name = rawName.trim()
    const targetFilename =
      sourceKind === 'saved' && name === workflow.name
        ? (sourceFilename ?? `${slugify(name)}.yaml`)
        : `${slugify(name)}.yaml`
    setSaving(true)
    try {
      const updated = { ...workflow, name }
      if (sourceKind === 'draft' && sourceFilename) {
        await api.saveWorkflow(targetFilename, updated)
        await api.deleteDraft(sourceFilename).catch(() => void 0)
      } else {
        await api.saveWorkflow(targetFilename, updated)
      }
      useWorkflowStore.setState({ workflow: updated })
      markSaved(targetFilename)
    } finally {
      setSaving(false)
    }
  }

  async function handleExport() {
    if (!workflow) return
    setExporting(true)
    try {
      const { content } = await api.workflowToYaml(workflow)
      const blob = new Blob([content], { type: 'application/x-yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${slugify(workflow.name)}.yaml`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  async function handleImportFile(file: File) {
    const text = await file.text()
    const lower = file.name.toLowerCase()
    try {
      const imported =
        lower.endsWith('.json')
          ? JSON.parse(text)
          : (await api.workflowFromYaml(text)).workflow
      setWorkflow(imported)
      resetRun()
    } catch (e) {
      window.alert(`Could not import workflow: ${(e as Error).message}`)
    }
  }

  async function handleValidate() {
    if (!workflow || !workflowSignature) return
    setValidating(true)
    try {
      const result = await api.validateWorkflow(workflow)
      setValidationIssues(result.errors.length ? result.errors : null)
      useWorkflowStore.setState({
        runWarnings: result.warnings.length ? result.warnings : null,
        runError: result.valid ? null : result.summary,
      })
      setValidatedSignature(workflowSignature)
      setLastValidationValid(result.valid)
      if (!result.valid) setRightPanelMode('runlog')
    } catch (e) {
      setRunError((e as Error).message)
      setLastValidationValid(false)
      setRightPanelMode('runlog')
    } finally {
      setValidating(false)
    }
  }

  const isCurrentValidation = validatedSignature === workflowSignature
  const validateBadge = validationIssues && validationIssues.length > 0
  const validationClean = Boolean(workflow && isCurrentValidation && lastValidationValid)
  const validationTitle = !workflow
    ? 'Load or generate a workflow before validating'
    : validating
      ? 'Validating workflow...'
      : validationClean
        ? 'Workflow validated'
        : validateBadge && isCurrentValidation
          ? `${validationIssues!.length} validation issue(s)`
          : 'Validate workflow'

  return (
    <div
      className="flex items-center px-4 shrink-0"
      style={{
        height: 56,
        background: 'var(--bg-1)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Left: WF logo + brand */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center font-mono"
          style={{
            width: 32, height: 32,
            borderRadius: 6,
            background: 'var(--text-0)',
            color: 'var(--bg-0)',
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.04em',
          }}
        >
          ds
        </div>
        <div className="flex flex-col justify-center leading-tight gap-0.5">
          <span
            style={{
              fontFamily: 'Chivo, system-ui, sans-serif',
              fontWeight: 600,
              fontSize: 16,
              color: 'var(--text-0)',
              letterSpacing: '-0.01em',
            }}
          >
            dbSherpa Studio
          </span>
          <span style={{ color: 'var(--text-2)', fontSize: 10, fontWeight: 500, letterSpacing: '0.02em' }}>
            AI workflow builder
          </span>
        </div>
      </div>

      {/* Center: title + counts */}
      <div className="flex-1 flex items-center justify-center gap-6">
        <span style={{ color: 'var(--text-1)', fontSize: 14, fontWeight: 500 }}>{title}</span>
        <span className="font-mono" style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
          {nodeCount} nodes · {edgeCount} edges
        </span>
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-2">
        <IconButton onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <Sun size={15} strokeWidth={2} /> : <Moon size={15} strokeWidth={2} />}
        </IconButton>
        <BarButton onClick={() => setDrawerOpen(true)} icon={<LayoutTemplate size={14} strokeWidth={2} />}>Templates</BarButton>
        <input
          ref={importInputRef}
          type="file"
          accept=".yaml,.yml,.json,application/x-yaml,application/json"
          style={{ display: 'none' }}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) void handleImportFile(file)
          }}
        />
        <BarButton onClick={() => importInputRef.current?.click()} icon={<Upload size={14} strokeWidth={2} />}>Import</BarButton>
        <BarButton
          onClick={() => { void handleExport() }}
          icon={exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} strokeWidth={2} />}
          disabled={!workflow || exporting}
        >
          Export
        </BarButton>
        <StatusIconButton
          onClick={() => { void handleValidate() }}
          disabled={!workflow || validating}
          title={validationTitle}
          status={validationClean ? 'ok' : validateBadge && isCurrentValidation ? 'error' : 'idle'}
          badge={validateBadge && isCurrentValidation ? validationIssues!.length : undefined}
        >
          {validating ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} strokeWidth={2.2} />}
        </StatusIconButton>
        <BarButton
          onClick={resetRun}
          icon={<Trash2 size={14} strokeWidth={2} />}
          disabled={isRunning || (!workflow && runLog.length === 0 && !runResult && !runError)}
        >
          Clear
        </BarButton>
        <BarButton onClick={handleSave} icon={saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} strokeWidth={2} />} disabled={!workflow || saving}>
          Save
        </BarButton>
        <RunButton onClick={handleRun} disabled={!workflow || isRunning} running={isRunning} />
      </div>
    </div>
  )
}

function IconButton({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="flex items-center justify-center"
      style={{
        width: 36, height: 36,
        borderRadius: 8,
        background: 'transparent',
        color: 'var(--text-1)',
        border: '1px solid var(--border)',
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}

function StatusIconButton({
  children,
  onClick,
  disabled,
  title,
  status,
  badge,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  title?: string
  status: 'idle' | 'ok' | 'error'
  badge?: number
}) {
  const color = status === 'ok'
    ? 'var(--success)'
    : status === 'error'
      ? 'var(--danger)'
      : disabled
        ? 'var(--text-3)'
        : 'var(--text-2)'
  const border = status === 'ok'
    ? 'color-mix(in srgb, var(--success) 45%, var(--border))'
    : status === 'error'
      ? 'color-mix(in srgb, var(--danger) 45%, var(--border))'
      : 'var(--border)'
  const background = status === 'ok'
    ? 'color-mix(in srgb, var(--success) 10%, transparent)'
    : status === 'error'
      ? 'color-mix(in srgb, var(--danger) 10%, transparent)'
      : 'transparent'

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className="relative flex items-center justify-center"
      style={{
        width: 36,
        height: 36,
        borderRadius: 8,
        background,
        color,
        border: `1px solid ${border}`,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background 160ms, color 160ms, border-color 160ms, transform 160ms',
        transform: status === 'ok' ? 'scale(1.02)' : 'scale(1)',
      }}
    >
      {children}
      {badge != null && badge > 0 && (
        <span
          className="num"
          style={{
            position: 'absolute',
            top: -5,
            right: -5,
            minWidth: 16,
            height: 16,
            padding: '0 4px',
            borderRadius: 999,
            background: 'var(--danger)',
            color: '#fff',
            fontSize: 9,
            lineHeight: '16px',
            border: '1px solid var(--bg-1)',
          }}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

function BarButton({
  children, icon, onClick, disabled, tone,
}: { children: React.ReactNode; icon: React.ReactNode; onClick: () => void; disabled?: boolean; tone?: 'danger' }) {
  const danger = tone === 'danger'
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2"
      style={{
        height: 36,
        padding: '0 12px',
        borderRadius: 8,
        fontSize: 12.5,
        fontWeight: 500,
        background: 'transparent',
        color: danger ? 'var(--danger)' : disabled ? 'var(--text-3)' : 'var(--text-1)',
        border: `1px solid ${danger ? 'color-mix(in srgb, var(--danger) 50%, var(--border))' : 'var(--border)'}`,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}

function RunButton({ onClick, disabled, running }: { onClick: () => void; disabled: boolean; running: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2"
      style={{
        height: 36,
        padding: '0 16px',
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 600,
        background: 'var(--text-0)',
        color: 'var(--bg-0)',
        border: 'none',
        opacity: disabled && !running ? 0.55 : 1,
        cursor: disabled ? (running ? 'progress' : 'not-allowed') : 'pointer',
      }}
    >
      {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} strokeWidth={2.5} />}
      <span>{running ? 'Running…' : 'Run'}</span>
    </button>
  )
}
