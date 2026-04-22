import { useEffect } from 'react'
import { Library, BotMessageSquare, SunMedium, MoonStar, ShieldCheck } from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { useThemeStore } from '../../store/themeStore'
import WorkflowActions from '../WorkflowActions'

type ChipMode = 'edit' | 'draft' | 'new'

export default function Topbar() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const drawerOpen = useWorkflowStore((s) => s.workflowDrawerOpen)
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const copilotOpen = useWorkflowStore((s) => s.copilotOpen)
  const setCopilotOpen = useWorkflowStore((s) => s.setCopilotOpen)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)

  const chipMode: ChipMode =
    sourceKind === 'saved' ? 'edit' : sourceKind === 'draft' ? 'draft' : 'new'

  // Global hotkey: Cmd/Ctrl+O opens the workflows drawer
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        setDrawerOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setDrawerOpen])

  return (
    <div
      className="relative flex items-center gap-3 px-4 shrink-0 z-10"
      style={{
        height: 48,
        background: 'var(--bg-1)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Wordmark — gradient tile + shield glyph says "surveillance" at a
          glance without us having to write it out. */}
      <div className="flex items-center gap-2.5 mr-1">
        <div
          className="flex items-center justify-center"
          style={{
            width: 28, height: 28,
            borderRadius: 7,
            background: 'linear-gradient(145deg, var(--accent-hi), var(--accent-lo))',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.25), 0 6px 16px -6px color-mix(in srgb, var(--accent) 60%, transparent)',
            color: '#0A0A0A',
          }}
        >
          <ShieldCheck size={15} strokeWidth={2.3} />
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className="display"
            style={{ fontWeight: 600, fontSize: 17, color: 'var(--text-0)' }}
          >
            dbSherpa
          </span>
          <span className="eyebrow hidden sm:inline" style={{ color: 'var(--text-2)' }}>
            Surveillance · v1.0
          </span>
        </div>
      </div>

      <Divider />

      {/* Workflows drawer trigger */}
      <button
        onClick={() => setDrawerOpen(!drawerOpen)}
        className="lift flex items-center gap-2"
        style={{
          height: 30,
          padding: '0 10px',
          borderRadius: 7,
          fontSize: 11.5,
          fontWeight: 500,
          background: drawerOpen ? 'color-mix(in srgb, var(--accent) 12%, var(--bg-2))' : 'var(--bg-2)',
          color: drawerOpen ? 'var(--accent)' : 'var(--text-1)',
          border: `1px solid ${drawerOpen ? 'color-mix(in srgb, var(--accent) 40%, transparent)' : 'var(--border)'}`,
          letterSpacing: '0.01em',
        }}
        aria-pressed={drawerOpen}
      >
        <Library size={13} strokeWidth={2} />
        <span>Workflows</span>
        <span
          className="num"
          style={{
            fontSize: 9.5,
            color: 'var(--text-3)',
            border: '1px solid var(--border)',
            padding: '1px 5px',
            borderRadius: 4,
            letterSpacing: '0.05em',
          }}
        >
          ⌘O
        </span>
      </button>

      {workflow && (
        <>
          <Divider />
          <DocumentChip
            mode={chipMode}
            name={workflow.name}
            filename={sourceFilename}
            nodeCount={workflow.nodes.length}
          />
        </>
      )}

      <div className="flex-1" />

      {/* Primary workflow actions (Run / Reset / Save as / Clear).
          Moved up from the bottom bar so all workflow verbs live together. */}
      {workflow && (
        <>
          <WorkflowActions />
          <Divider />
        </>
      )}

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
        className="lift flex items-center justify-center"
        style={{
          width: 30, height: 30,
          borderRadius: 6,
          background: 'var(--bg-2)',
          color: 'var(--text-1)',
          border: '1px solid var(--border)',
        }}
      >
        {theme === 'dark' ? <SunMedium size={14} strokeWidth={2} /> : <MoonStar size={14} strokeWidth={2} />}
      </button>

      {/* Copilot toggle */}
      <button
        onClick={() => setCopilotOpen(!copilotOpen)}
        className="lift"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontSize: 11,
          padding: '5px 10px',
          borderRadius: 6,
          background: copilotOpen ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--bg-2)',
          color: copilotOpen ? 'var(--accent)' : 'var(--text-2)',
          border: `1px solid ${copilotOpen ? 'color-mix(in srgb, var(--accent) 40%, transparent)' : 'var(--border)'}`,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontWeight: 600,
        }}
      >
        <BotMessageSquare size={12} strokeWidth={2} />
        <span>Copilot</span>
      </button>
    </div>
  )
}

function Divider() {
  return <div style={{ width: 1, height: 22, background: 'var(--border)' }} />
}

function DocumentChip({
  mode,
  name,
  filename,
  nodeCount,
}: {
  mode: ChipMode
  name: string
  filename: string | null
  nodeCount: number
}) {
  // Label + accent shift per workflow origin so the operator always knows
  // whether they're editing a live saved workflow, a draft that hasn't
  // been named yet, or an in-memory scratch canvas.
  const style =
    mode === 'edit'
      ? {
          label: 'Editing',
          bg: 'color-mix(in srgb, var(--accent) 7%, var(--bg-2))',
          accent: 'var(--accent)',
          border: '3px solid color-mix(in srgb, var(--accent) 60%, transparent)',
          italic: false,
        }
      : mode === 'draft'
        ? {
            label: 'Draft',
            bg: 'color-mix(in srgb, var(--info) 7%, var(--bg-2))',
            accent: 'var(--info)',
            border: '3px solid color-mix(in srgb, var(--info) 55%, transparent)',
            italic: false,
          }
        : {
            label: 'New',
            bg: 'var(--bg-2)',
            accent: 'var(--text-3)',
            border: '3px dashed var(--border-strong)',
            italic: true,
          }

  return (
    <div
      className={`doc-chip doc-chip--${mode} flex items-center gap-2.5 min-w-0`}
      style={{
        height: 30,
        padding: '0 10px 0 11px',
        borderRadius: 7,
        background: style.bg,
        borderTop: '1px solid var(--border)',
        borderRight: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
        borderLeft: style.border,
      }}
      title={
        filename
          ? mode === 'draft'
            ? `Draft · ${filename}`
            : filename
          : 'Unsaved new workflow'
      }
    >
      <span
        className="eyebrow shrink-0"
        style={{ color: style.accent, letterSpacing: '0.12em' }}
      >
        {style.label}
      </span>

      <span
        className="truncate"
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          fontStyle: style.italic ? 'italic' : 'normal',
          color: mode === 'edit' ? 'var(--text-0)' : 'var(--text-1)',
          maxWidth: 220,
          letterSpacing: '-0.005em',
        }}
      >
        {name || 'Untitled workflow'}
      </span>

      <span
        className="num shrink-0"
        style={{
          fontSize: 10,
          color: 'var(--text-2)',
          background: 'var(--bg-0)',
          border: '1px solid var(--border)',
          padding: '1px 6px',
          borderRadius: 999,
        }}
      >
        {nodeCount} node{nodeCount === 1 ? '' : 's'}
      </span>
    </div>
  )
}
