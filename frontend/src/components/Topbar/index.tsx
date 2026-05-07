/**
 * Top action bar — layout aligned with dbSherpa Studio v5 (brand / breadcrumbs /
 * center tabs / Share · theme · profile + workflow tools).
 */
import { useMemo, useRef, useState } from 'react'
import {
  Sun,
  Moon,
  LayoutTemplate,
  Upload,
  Download,
  ShieldCheck,
  Save,
  Play,
  Loader2,
  Trash2,
  Star,
  MoreHorizontal,
  ChevronDown,
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

type StudioTab = 'workflow' | 'skills' | 'tables' | 'nodes' | 'agents'

const STUDIO_TABS: { id: StudioTab; label: string; disabled?: boolean }[] = [
  { id: 'workflow', label: 'Workflow' },
  { id: 'skills', label: 'Skills', disabled: true },
  { id: 'tables', label: 'Tables', disabled: true },
  { id: 'nodes', label: 'Node Library' },
  { id: 'agents', label: 'Agents' },
]

export default function Topbar() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const setRightPanelMode = useWorkflowStore((s) => s.setRightPanelMode)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const setRunning = useWorkflowStore((s) => s.setRunning)
  const setRunError = useWorkflowStore((s) => s.setRunError)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const applyRunEvent = useWorkflowStore((s) => s.applyRunEvent)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const setValidationIssues = useWorkflowStore((s) => s.setValidationIssues)
  const markSaved = useWorkflowStore((s) => s.markSaved)
  const setWorkflow = useWorkflowStore((s) => s.setWorkflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runError = useWorkflowStore((s) => s.runError)
  const resetRunStore = useWorkflowStore((s) => s.resetRun)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validatedSignature, setValidatedSignature] = useState<string | null>(null)
  const [lastValidationValid, setLastValidationValid] = useState<boolean | null>(null)
  const [studioTab, setStudioTab] = useState<StudioTab>('workflow')
  const importInputRef = useRef<HTMLInputElement | null>(null)

  const nodeCount = workflow?.nodes.length ?? 0
  const edgeCount = workflow?.edges.length ?? 0
  const title = workflow?.name || 'Untitled workflow'
  const workflowSlug = useMemo(() => slugify(workflow?.name), [workflow?.name])
  const workflowSignature = useMemo(() => (workflow ? JSON.stringify(workflow) : null), [workflow])

  function onStudioTab(id: StudioTab) {
    const spec = STUDIO_TABS.find((t) => t.id === id)
    if (spec?.disabled) return
    setStudioTab(id)
    if (id === 'agents') setRightPanelMode('copilot')
    if (id === 'nodes') setDrawerOpen(true)
  }

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
        lower.endsWith('.json') ? JSON.parse(text) : (await api.workflowFromYaml(text)).workflow
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

  const borderHi = 'var(--border-strong)'

  return (
    <div
      className="panel-glass flex items-center shrink-0 relative z-20 min-h-[52px]"
      style={{
        padding: '10px 22px',
        gap: 18,
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Left — brand + breadcrumbs (v5) */}
      <div className="flex items-center shrink-0" style={{ gap: 10 }}>
        <div
          className="flex items-center justify-center overflow-hidden shrink-0"
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-cyan))',
            boxShadow: '0 4px 12px color-mix(in srgb, var(--accent) 35%, transparent)',
          }}
          aria-label="dbSherpa"
        >
          <img
            src={theme === 'dark' ? '/brand/dbsherpa-logo-dark.png' : '/brand/dbsherpa-logo-light.png'}
            alt=""
            style={{
              width: 25,
              height: 25,
              objectFit: 'contain',
              display: 'block',
              filter: 'brightness(0) invert(1)',
            }}
          />
        </div>
        <div className="flex flex-col justify-center leading-[1.15] shrink-0 hidden sm:flex">
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-0)' }}>dbSherpa Studio</span>
          <span className="font-mono" style={{ fontSize: 10.5, color: 'var(--text-3)', letterSpacing: '0.02em' }}>
            AI workflow builder
          </span>
        </div>
        <div className="w-px h-6 shrink-0 hidden md:block" style={{ background: borderHi, marginLeft: 2, marginRight: 2 }} />
        <BreadcrumbPill label="Main" />
        <span style={{ color: 'var(--text-3)', fontSize: 13, margin: '0 2px' }} aria-hidden>
          ›
        </span>
        <BreadcrumbPill label={workflowSlug} mono />
        <IconGhost title="Star" onMouseAccent="warning">
          <Star size={13} strokeWidth={1.3} />
        </IconGhost>
        <IconGhost title="More">
          <MoreHorizontal size={13} strokeWidth={1.8} />
        </IconGhost>
      </div>

      <div className="flex-1 min-w-[12px]" />

      {/* Center — studio tabs */}
      <div className="flex items-center shrink-0" style={{ gap: 2 }}>
        {STUDIO_TABS.map(({ id, label, disabled }) => {
          const active = studioTab === id
          return (
            <button
              key={id}
              type="button"
              disabled={disabled}
              onClick={() => onStudioTab(id)}
              className="relative border-0 cursor-pointer bg-transparent"
              style={{
                padding: '7px 12px',
                fontSize: 12.5,
                fontWeight: active ? 600 : 500,
                color: disabled ? 'var(--text-3)' : active ? 'var(--text-0)' : 'var(--text-2)',
                opacity: disabled ? 0.45 : 1,
                cursor: disabled ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {label}
              {active && !disabled && (
                <span
                  className="absolute rounded-sm pointer-events-none"
                  style={{
                    left: 12,
                    right: 12,
                    bottom: -11,
                    height: 2,
                    background: 'var(--accent)',
                  }}
                />
              )}
            </button>
          )
        })}
      </div>

      <div className="flex-1 min-w-[12px]" />

      {/* Right — workflow tools + v5 chrome */}
      <div className="flex items-center shrink-0" style={{ gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
        <span className="font-mono whitespace-nowrap hidden lg:inline" style={{ color: 'var(--text-3)', fontSize: 11, letterSpacing: '0.02em' }}>
          {nodeCount} nd · {edgeCount} ed
        </span>
        <span className="w-px h-[18px] shrink-0 hidden sm:block" style={{ background: borderHi }} />

        <GhostButton disabled title="Coming soon">
          Share
        </GhostButton>
        <BarButton onClick={() => setDrawerOpen(true)} icon={<LayoutTemplate size={14} strokeWidth={2} />}>
          Templates
        </BarButton>
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
        <BarButton onClick={() => importInputRef.current?.click()} icon={<Upload size={14} strokeWidth={2} />}>
          Import
        </BarButton>
        <BarButton
          onClick={() => {
            void handleExport()
          }}
          icon={exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} strokeWidth={2} />}
          disabled={!workflow || exporting}
        >
          Export
        </BarButton>
        <StatusIconButton
          onClick={() => {
            void handleValidate()
          }}
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
        <BarButton
          onClick={() => {
            void handleSave()
          }}
          icon={saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} strokeWidth={2} />}
          disabled={!workflow || saving}
        >
          Save
        </BarButton>
        <RunButton onClick={handleRun} disabled={!workflow || isRunning} running={isRunning} />

        <span className="w-px h-[18px] shrink-0" style={{ background: borderHi }} />

        <ThemeIconButton onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <Sun size={14} strokeWidth={1.4} /> : <Moon size={14} strokeWidth={1.4} />}
        </ThemeIconButton>
        <button
          type="button"
          title="Account"
          className="shrink-0 border-0 p-0 cursor-default"
          style={{
            width: 30,
            height: 30,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent), var(--accent-cyan))',
            boxShadow: `
              0 0 0 2px color-mix(in srgb, var(--panel-glass-bg) 95%, transparent),
              0 0 0 3px color-mix(in srgb, var(--accent) 35%, transparent)
            `,
          }}
          aria-label="Profile"
        />
      </div>

      {/* Title tooltip strip — workflow name (secondary to breadcrumbs) */}
      <span className="sr-only">{title}</span>
    </div>
  )
}

function BreadcrumbPill({ label, mono }: { label: string; mono?: boolean }) {
  return (
    <button
      type="button"
      className="flex items-center gap-1.5 border-0 rounded-[7px] cursor-pointer bg-transparent shrink-0"
      style={{
        padding: '5px 9px',
        color: 'var(--text-0)',
        fontSize: 13,
        fontWeight: 500,
        fontFamily: mono ? 'IBM Plex Mono, ui-monospace, monospace' : 'inherit',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--accent-soft)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      {label}
      <ChevronDown size={10} strokeWidth={1.4} style={{ color: 'var(--text-2)', opacity: 0.85 }} />
    </button>
  )
}

function IconGhost({
  children,
  title,
  onMouseAccent,
}: {
  children: React.ReactNode
  title: string
  onMouseAccent?: 'warning'
}) {
  return (
    <button
      type="button"
      title={title}
      className="flex items-center justify-center border-0 rounded-[5px] cursor-pointer bg-transparent"
      style={{ padding: 4, color: 'var(--text-3)' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--accent-soft)'
        if (onMouseAccent === 'warning') e.currentTarget.style.color = 'var(--warning)'
        else e.currentTarget.style.color = 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text-3)'
      }}
    >
      {children}
    </button>
  )
}

function GhostButton({
  children,
  disabled,
  title,
  onClick,
}: {
  children: React.ReactNode
  disabled?: boolean
  title?: string
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className="cursor-pointer bg-transparent"
      style={{
        padding: '7px 14px',
        borderRadius: 8,
        border: `1px solid ${disabled ? 'var(--border-soft)' : 'var(--border)'}`,
        color: disabled ? 'var(--text-3)' : 'var(--text-0)',
        fontSize: 13,
        fontWeight: 500,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        e.currentTarget.style.background = 'var(--accent-soft)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = disabled ? 'var(--border-soft)' : 'var(--border)'
      }}
    >
      {children}
    </button>
  )
}

function ThemeIconButton({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex items-center justify-center border-0 cursor-pointer bg-transparent"
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        border: '1px solid var(--border)',
        color: 'var(--text-0)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--accent-soft)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = 'var(--border)'
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
  const color =
    status === 'ok'
      ? 'var(--success)'
      : status === 'error'
        ? 'var(--danger)'
        : disabled
          ? 'var(--text-3)'
          : 'var(--text-2)'
  const border =
    status === 'ok'
      ? 'color-mix(in srgb, var(--success) 45%, var(--border))'
      : status === 'error'
        ? 'color-mix(in srgb, var(--danger) 45%, var(--border))'
        : 'var(--border)'
  const background =
    status === 'ok'
      ? 'color-mix(in srgb, var(--success) 10%, transparent)'
      : status === 'error'
        ? 'color-mix(in srgb, var(--danger) 10%, transparent)'
        : 'transparent'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className="relative flex items-center justify-center border-0"
      style={{
        width: 32,
        height: 32,
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
            border: '1px solid var(--panel-glass-bg)',
          }}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

function BarButton({
  children,
  icon,
  onClick,
  disabled,
  tone,
}: {
  children: React.ReactNode
  icon: React.ReactNode
  onClick: () => void
  disabled?: boolean
  tone?: 'danger'
}) {
  const danger = tone === 'danger'
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 border-0 cursor-pointer bg-transparent"
      style={{
        height: 32,
        padding: '0 12px',
        borderRadius: 8,
        fontSize: 12.5,
        fontWeight: 500,
        color: danger ? 'var(--danger)' : disabled ? 'var(--text-3)' : 'var(--text-0)',
        border: `1px solid ${danger ? 'color-mix(in srgb, var(--danger) 50%, var(--border))' : 'var(--border)'}`,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        fontFamily: 'inherit',
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        e.currentTarget.style.background = 'var(--accent-soft)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = danger ? 'color-mix(in srgb, var(--danger) 50%, var(--border))' : 'var(--border)'
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
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 border-0 cursor-pointer"
      style={{
        height: 32,
        padding: '0 14px',
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 600,
        background:
          disabled && !running
            ? 'var(--border-solid)'
            : 'linear-gradient(135deg, var(--accent-hi) 0%, var(--accent-lo) 55%, color-mix(in srgb, var(--accent-cyan) 70%, var(--accent-lo)) 100%)',
        color: '#fff',
        border: '1px solid color-mix(in srgb, var(--accent-lo) 45%, transparent)',
        boxShadow: disabled && !running ? 'none' : '0 4px 14px color-mix(in srgb, var(--accent) 35%, transparent)',
        opacity: disabled && !running ? 0.55 : 1,
        cursor: disabled ? (running ? 'progress' : 'not-allowed') : 'pointer',
        fontFamily: 'inherit',
      }}
    >
      {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} strokeWidth={2.5} />}
      <span>{running ? 'Running…' : 'Run'}</span>
    </button>
  )
}
