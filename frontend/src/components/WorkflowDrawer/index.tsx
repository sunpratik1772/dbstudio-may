/**
 * Workflows drawer — two separate lists so saved workflows and
 * Copilot-generated / in-progress drafts don't get mixed up.
 *
 *   SAVED   — explicitly named workflows (workflows/ on backend)
 *   DRAFTS  — auto-persisted workflows (drafts/ on backend). Promote to
 *             Saved via the Save-As button in the topbar.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  X as XIcon,
  Search,
  FilePlus2,
  Workflow as WorkflowIcon,
  FileJson2,
  FileClock,
  Trash2,
  Loader2,
} from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { api, type StoredWorkflow } from '../../services/api'

type DrawerTab = 'saved' | 'drafts'

export default function WorkflowDrawer() {
  const open = useWorkflowStore((s) => s.workflowDrawerOpen)
  const setOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const loadWorkflowFromFile = useWorkflowStore((s) => s.loadWorkflowFromFile)
  const loadDraftFromFile = useWorkflowStore((s) => s.loadDraftFromFile)
  const newBlankWorkflow = useWorkflowStore((s) => s.newBlankWorkflow)

  const [tab, setTab] = useState<DrawerTab>('saved')
  const [saved, setSaved] = useState<StoredWorkflow[] | null>(null)
  const [drafts, setDrafts] = useState<StoredWorkflow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingFile, setLoadingFile] = useState<string | null>(null)
  const [deletingFile, setDeletingFile] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  // Refetch both lists every time the drawer opens so freshly generated
  // drafts and newly saved workflows appear immediately.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setError(null)
    setSaved(null)
    setDrafts(null)
    Promise.all([api.listWorkflows(), api.listDrafts()])
      .then(([sr, dr]) => {
        if (cancelled) return
        setSaved(sr.workflows)
        setDrafts(dr.drafts)
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  // Esc closes
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  const items = tab === 'saved' ? saved : drafts
  const filtered = useMemo(() => {
    if (!items) return null
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      (w) =>
        w.name?.toLowerCase().includes(q) ||
        w.description?.toLowerCase().includes(q) ||
        w.filename.toLowerCase().includes(q),
    )
  }, [items, query])

  async function handleOpen(filename: string) {
    setLoadingFile(filename)
    try {
      const dag =
        tab === 'saved'
          ? await api.getWorkflow(filename)
          : await api.getDraft(filename)
      if (tab === 'saved') loadWorkflowFromFile(filename, dag)
      else loadDraftFromFile(filename, dag)
      setOpen(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingFile(null)
    }
  }

  async function handleDelete(filename: string) {
    const ok = window.confirm(
      tab === 'drafts'
        ? `Delete draft "${filename}"?`
        : `Delete saved workflow "${filename}"? This cannot be undone.`,
    )
    if (!ok) return
    setDeletingFile(filename)
    try {
      if (tab === 'saved') await api.deleteWorkflow(filename)
      else await api.deleteDraft(filename)
      if (tab === 'saved') {
        setSaved((prev) => prev?.filter((w) => w.filename !== filename) ?? null)
      } else {
        setDrafts((prev) => prev?.filter((w) => w.filename !== filename) ?? null)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setDeletingFile(null)
    }
  }

  function handleNew() {
    newBlankWorkflow()
    setOpen(false)
  }

  if (!open) return null

  const savedCount = saved?.length ?? null
  const draftsCount = drafts?.length ?? null

  return (
    <>
      <div className="drawer-backdrop" onClick={() => setOpen(false)} />
      <aside
        className="drawer panel-glass"
        role="dialog"
        aria-label="Stored workflows"
        style={{
          width: 360,
          borderRight: '1px solid var(--border-strong)',
          boxShadow: '12px 0 32px -16px rgba(0,0,0,.35)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4"
          style={{ height: 48, borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <WorkflowIcon size={14} strokeWidth={2} style={{ color: 'var(--accent)' }} />
            <span className="eyebrow" style={{ color: 'var(--text-0)' }}>
              Workflows
            </span>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close drawer"
            className="lift flex items-center justify-center"
            style={{
              width: 26, height: 26, borderRadius: 6,
              background: 'transparent',
              color: 'var(--text-2)',
              border: '1px solid transparent',
            }}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-2)'
              ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-0)'
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
              ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-2)'
            }}
          >
            <XIcon size={14} strokeWidth={2} />
          </button>
        </div>

        {/* New button + Search */}
        <div className="px-3 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
          <button
            onClick={handleNew}
            className="lift flex items-center justify-center gap-2 w-full"
            style={{
              padding: '8px 12px',
              borderRadius: 7,
              background: 'linear-gradient(180deg, var(--accent-hi) 0%, var(--accent-lo) 100%)',
              color: '#fff',
              border: '1px solid color-mix(in srgb, var(--accent-hi) 35%, var(--accent-lo))',
              boxShadow: '0 1px 0 rgba(255,255,255,0.25) inset, 0 8px 18px -8px color-mix(in srgb, var(--accent) 55%, transparent)',
              fontSize: 12.5,
              fontWeight: 600,
              letterSpacing: 0,
            }}
          >
            <FilePlus2 size={13} strokeWidth={2.2} />
            <span>New workflow</span>
          </button>

          <div
            className="flex items-center gap-2 mt-3 px-2"
            style={{
              height: 30,
              borderRadius: 6,
              background: 'var(--bg-2)',
              border: '1px solid var(--border)',
            }}
          >
            <Search size={12} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search ${tab}`}
              className="flex-1 outline-none"
              style={{
                fontSize: 12,
                background: 'transparent',
                color: 'var(--text-0)',
                border: 'none',
              }}
              spellCheck={false}
            />
          </div>
        </div>

        {/* Tabs: Saved | Drafts */}
        <div
          className="flex items-stretch shrink-0"
          style={{
            borderBottom: '1px solid var(--border)',
            height: 36,
            background: 'var(--bg-0)',
          }}
        >
          <TabButton
            label="Saved"
            icon={<FileJson2 size={12} strokeWidth={2} />}
            active={tab === 'saved'}
            count={savedCount}
            onClick={() => setTab('saved')}
          />
          <TabButton
            label="Drafts"
            icon={<FileClock size={12} strokeWidth={2} />}
            active={tab === 'drafts'}
            count={draftsCount}
            onClick={() => setTab('drafts')}
          />
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2">
          {items === null && !error && (
            <div
              className="flex items-center justify-center gap-2 py-10"
              style={{ color: 'var(--text-2)', fontSize: 12 }}
            >
              <Loader2 size={13} className="animate-spin" strokeWidth={2} />
              Loading…
            </div>
          )}

          {error && (
            <div
              className="px-3 py-2 rounded"
              style={{
                background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                color: 'var(--danger)',
                border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
                fontSize: 11.5,
              }}
            >
              {error}
            </div>
          )}

          {filtered && filtered.length === 0 && (
            <div
              className="text-center py-10 px-4"
              style={{ color: 'var(--text-3)', fontSize: 12, lineHeight: 1.5 }}
            >
              {query
                ? `No ${tab} match your search.`
                : tab === 'saved'
                  ? 'No saved workflows yet. Build one, then use Save-as in the topbar.'
                  : 'No drafts yet. The Copilot and manual builds drop here automatically.'}
            </div>
          )}

          {filtered?.map((w) => {
            const active =
              w.filename === sourceFilename &&
              ((tab === 'saved' && sourceKind === 'saved') ||
                (tab === 'drafts' && sourceKind === 'draft'))
            const loading = w.filename === loadingFile
            const deleting = w.filename === deletingFile
            return (
              <DrawerItem
                key={w.filename}
                item={w}
                tab={tab}
                active={active}
                loading={loading}
                deleting={deleting}
                onOpen={() => handleOpen(w.filename)}
                onDelete={() => handleDelete(w.filename)}
              />
            )
          })}
        </div>

        {/* Footer hint */}
        <div
          className="px-3 py-2 flex items-center justify-between"
          style={{ borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--text-3)' }}
        >
          <span>
            {tab === 'saved'
              ? saved
                ? `${saved.length} saved`
                : '—'
              : drafts
                ? `${drafts.length} draft${drafts.length === 1 ? '' : 's'}`
                : '—'}
          </span>
          <span className="num">Esc · close</span>
        </div>
      </aside>
    </>
  )
}

function TabButton({
  label,
  icon,
  active,
  count,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  active: boolean
  count: number | null
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="flex-1 flex items-center justify-center gap-1.5"
      style={{
        background: active ? 'var(--bg-1)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-2)',
        borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        borderRight: '1px solid var(--border-soft)',
      }}
    >
      {icon}
      <span>{label}</span>
      {count != null && (
        <span
          className="num"
          style={{
            fontSize: 9.5,
            color: active ? 'var(--accent)' : 'var(--text-3)',
            background: active ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--bg-2)',
            border: '1px solid var(--border)',
            padding: '1px 5px',
            borderRadius: 999,
            letterSpacing: 0,
          }}
        >
          {count}
        </span>
      )}
    </button>
  )
}

function DrawerItem({
  item: w,
  tab,
  active,
  loading,
  deleting,
  onOpen,
  onDelete,
}: {
  item: StoredWorkflow
  tab: DrawerTab
  active: boolean
  loading: boolean
  deleting: boolean
  onOpen: () => void
  onDelete: () => void
}) {
  const accent = tab === 'saved' ? 'var(--accent)' : 'var(--info)'
  const Icon = tab === 'saved' ? FileJson2 : FileClock
  return (
    <div
      className="relative lift flex items-start gap-3 p-3 rounded-lg mb-1.5"
      style={{
        background: active
          ? `color-mix(in srgb, ${accent} 10%, var(--bg-2))`
          : 'var(--bg-2)',
        border: active
          ? `1px solid color-mix(in srgb, ${accent} 45%, transparent)`
          : '1px solid var(--border)',
        cursor: loading ? 'progress' : 'pointer',
      }}
      onClick={loading || deleting ? undefined : onOpen}
      onMouseEnter={(e) => {
        if (!active) {
          ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-3)'
          ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)'
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-2)'
          ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'
        }
      }}
    >
      {active && (
        <div
          style={{
            position: 'absolute',
            left: -1, top: 10, bottom: 10,
            width: 3, borderRadius: 3,
            background: accent,
          }}
        />
      )}
      <span
        className="flex items-center justify-center rounded shrink-0"
        style={{
          width: 32, height: 32,
          background: `color-mix(in srgb, ${accent} ${active ? 22 : 12}%, transparent)`,
          border: `1px solid color-mix(in srgb, ${accent} ${active ? 50 : 30}%, transparent)`,
          color: accent,
        }}
      >
        <Icon size={15} strokeWidth={2} />
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          <div
            className="truncate"
            style={{
              fontSize: 12.5,
              fontWeight: 600,
              color: active ? accent : 'var(--text-0)',
              letterSpacing: 0,
            }}
          >
            {w.name || w.filename}
          </div>
          <span
            className="num shrink-0"
            style={{
              fontSize: 10.5,
              color: 'var(--text-2)',
              background: 'var(--bg-0)',
              border: '1px solid var(--border)',
              padding: '1px 6px',
              borderRadius: 999,
            }}
          >
            {w.node_count} node{w.node_count === 1 ? '' : 's'}
          </span>
        </div>
        {w.description && (
          <div
            style={{
              marginTop: 3,
              fontSize: 11.5,
              color: 'var(--text-2)',
              lineHeight: 1.45,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {w.description}
          </div>
        )}
        <div
          className="flex items-center justify-between"
          style={{ marginTop: 6 }}
        >
          <span
            className="num truncate"
            style={{
              fontSize: 10,
              color: 'var(--text-3)',
              letterSpacing: 0,
              flex: 1,
              minWidth: 0,
            }}
          >
            {w.filename}
          </span>
          {w.modified_ms != null && (
            <span
              className="num shrink-0 ml-2"
              style={{ fontSize: 9.5, color: 'var(--text-3)' }}
            >
              {relativeTime(w.modified_ms)}
            </span>
          )}
        </div>
      </div>

      {/* Delete button — only visible on hover via :hover in CSS. Kept
          inline for simplicity and always visible with low opacity. */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        disabled={loading || deleting}
        aria-label="Delete"
        title="Delete"
        className="flex items-center justify-center rounded"
        style={{
          width: 24, height: 24,
          background: 'transparent',
          color: 'var(--text-3)',
          border: '1px solid transparent',
          opacity: 0.6,
          cursor: loading || deleting ? 'wait' : 'pointer',
        }}
        onMouseEnter={(e) => {
          ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--danger)'
          ;(e.currentTarget as HTMLButtonElement).style.background = 'color-mix(in srgb, var(--danger) 10%, transparent)'
          ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'color-mix(in srgb, var(--danger) 30%, transparent)'
          ;(e.currentTarget as HTMLButtonElement).style.opacity = '1'
        }}
        onMouseLeave={(e) => {
          ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-3)'
          ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
          ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent'
          ;(e.currentTarget as HTMLButtonElement).style.opacity = '0.6'
        }}
      >
        {deleting ? (
          <Loader2 size={12} strokeWidth={2} className="animate-spin" />
        ) : (
          <Trash2 size={12} strokeWidth={2} />
        )}
      </button>

      {loading && (
        <Loader2
          size={13}
          strokeWidth={2}
          className="animate-spin shrink-0"
          style={{ color: accent, marginTop: 2 }}
        />
      )}
    </div>
  )
}

function relativeTime(epochMs: number): string {
  const delta = Date.now() - epochMs
  if (delta < 60_000) return 'just now'
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h ago`
  const d = new Date(epochMs)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
