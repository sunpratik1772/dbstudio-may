/**
 * Left-side node palette — draggable catalogue built from backend NodeSpec.
 *
 * Section headers, grouping, and node metadata come from the live backend
 * `/node-manifest` payload, with generated.ts only as the offline fallback.
 */
import { useMemo, useRef, useState, type DragEvent } from 'react'
import { Check, RefreshCw, Search } from 'lucide-react'
import { getNodeDisplayName, UNKNOWN_NODE_UI, useNodeRegistryStore, type NodeType } from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import { PALETTE_DND_MIME } from '../WorkflowCanvas'
import ResizeHandle from '../ResizeHandle'

type Category = {
  key: string
  label: string
  color: string
  types: NodeType[]
}

export default function NodePanel() {
  const paletteWidth = useWorkflowStore((s) => s.paletteWidth)
  const setPaletteWidth = useWorkflowStore((s) => s.setPaletteWidth)
  const rootRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const nodeTypes = useNodeRegistryStore((s) => s.nodeTypes)
  const nodeUI = useNodeRegistryStore((s) => s.nodeUI)
  const paletteSections = useNodeRegistryStore((s) => s.paletteSections)
  const manifestError = useNodeRegistryStore((s) => s.error)
  const refreshNodeRegistry = useNodeRegistryStore((s) => s.refreshFromBackend)
  const registryLoading = useNodeRegistryStore((s) => s.loading)
  const lastLoadedAt = useNodeRegistryStore((s) => s.lastLoadedAt)
  const [syncFlash, setSyncFlash] = useState(false)

  async function handleRefreshNodes() {
    try {
      await refreshNodeRegistry()
      setSyncFlash(true)
      window.setTimeout(() => setSyncFlash(false), 1400)
    } catch {
      // The store keeps the previous manifest and exposes `manifestError`.
    }
  }

  const categories = useMemo((): Category[] => {
    return paletteSections.map((sec) => ({
      key: sec.id,
      label: sec.label,
      color: sec.color,
      types: [...nodeTypes]
        .filter((t) => nodeUI[t]?.paletteGroup === sec.id)
        .sort((a, b) => (nodeUI[a]?.paletteOrder ?? 0) - (nodeUI[b]?.paletteOrder ?? 0)),
    })).filter((c) => c.types.length > 0)
  }, [nodeTypes, nodeUI, paletteSections])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return categories
    return categories
      .map((c) => ({
        ...c,
        types: c.types.filter(
          (t) =>
            t.toLowerCase().includes(q) ||
            getNodeDisplayName(t).toLowerCase().includes(q) ||
            (nodeUI[t]?.description ?? '').toLowerCase().includes(q)
        ),
      }))
      .filter((c) => c.types.length > 0)
  }, [categories, nodeUI, query])

  return (
    <div
      ref={rootRef}
      className="panel-glass flex flex-col h-full overflow-hidden relative shrink-0"
      style={{ width: paletteWidth, borderRight: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-3.5 pt-3.5 pb-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex items-baseline gap-2 min-w-0">
            <span style={{ fontSize: 13, fontWeight: 650, color: 'var(--text-0)', letterSpacing: 0 }}>
              NODES
            </span>
            <span className="font-mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
              {nodeTypes.length}
            </span>
          </div>
          <div className="flex-1" />
          <button
            onClick={() => { void handleRefreshNodes() }}
            disabled={registryLoading}
            title={manifestError ? 'Refresh node catalog failed; retry' : lastLoadedAt ? 'Node catalog synced. Refresh from backend.' : 'Refresh node catalog from backend'}
            aria-label="Refresh node catalog"
            className="flex items-center justify-center"
            style={{
              width: 24,
              height: 24,
              borderRadius: 7,
              background: syncFlash
                ? 'color-mix(in srgb, var(--success) 14%, transparent)'
                : 'transparent',
              color: manifestError
                ? 'var(--danger)'
                : syncFlash
                  ? 'var(--success)'
                  : 'var(--text-2)',
              border: `1px solid ${syncFlash
                ? 'color-mix(in srgb, var(--success) 45%, var(--border))'
                : manifestError
                  ? 'color-mix(in srgb, var(--danger) 45%, var(--border))'
                  : 'var(--border-soft)'}`,
              cursor: registryLoading ? 'wait' : 'pointer',
              transition: 'background 180ms, color 180ms, border-color 180ms, transform 180ms',
              transform: syncFlash ? 'scale(1.04)' : 'scale(1)',
            }}
          >
            {syncFlash ? (
              <Check size={13} strokeWidth={2.6} />
            ) : (
              <RefreshCw size={13} strokeWidth={2.2} className={registryLoading ? 'animate-spin' : undefined} />
            )}
          </button>
        </div>
        {manifestError && (
          <div className="mt-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
            Using generated node catalog.
          </div>
        )}
      </div>

      {/* Search */}
      <div className="px-3.5 pb-3 shrink-0">
        <div
          className="flex items-center gap-2"
          style={{
            height: 32,
            padding: '0 10px',
            borderRadius: 6,
            background: 'var(--bg-0)',
            border: '1px solid var(--border-soft)',
          }}
        >
          <Search size={13} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search nodes…"
            className="flex-1 bg-transparent outline-none"
            style={{ fontSize: 12.5, color: 'var(--text-0)' }}
          />
        </div>
      </div>

      {/* Categories — labels/colors deduped from NodeSpec ui.palette */}
      <div className="flex-1 overflow-y-auto px-2.5 pb-3">
        {filtered.map((cat) => (
          <div key={cat.key} className="mb-3.5">
            <div className="flex items-center justify-between px-1.5 mb-1.5">
              <span
                className="font-mono"
                style={{ fontSize: 10, fontWeight: 650, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.16em' }}
              >
                {cat.label}
              </span>
              <span className="font-mono" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
                {cat.types.length}
              </span>
            </div>
            <div className="space-y-1.5">
              {cat.types.map((type) => (
                <NodeCard key={type} type={type} accent={cat.color} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-3.5 py-3 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="font-mono" style={{ fontSize: 10, color: 'var(--text-3)', lineHeight: 1.5 }}>
          drag or double-click to add<br />
          synced from backend NodeSpec
        </div>
      </div>

      <ResizeHandle
        edge="right"
        ariaLabel="Resize node palette"
        onResize={(clientX) => {
          const left = rootRef.current?.getBoundingClientRect().left ?? 0
          setPaletteWidth(clientX - left)
        }}
      />
    </div>
  )
}

function NodeCard({ type, accent }: { type: NodeType; accent: string }) {
  const meta = useNodeRegistryStore((s) => s.nodeUI[type] ?? UNKNOWN_NODE_UI)
  const Icon = meta.Icon
  const addNode = useWorkflowStore((s) => s.addNode)
  const title = getNodeDisplayName(type)

  return (
    <div
      draggable
      onDragStart={(e: DragEvent<HTMLDivElement>) => {
        e.dataTransfer.setData(PALETTE_DND_MIME, type)
        e.dataTransfer.setData('text/plain', type)
        e.dataTransfer.effectAllowed = 'copyMove'
      }}
      onDoubleClick={() => addNode(type, { x: 200, y: 200 })}
      title={meta.description}
      className="flex items-center gap-3 cursor-grab active:cursor-grabbing"
      style={{
        padding: '7px 8px',
        borderRadius: 6,
        background: 'transparent',
        border: '1px solid transparent',
        transition: 'border-color 140ms, background 140ms',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-soft)'
        ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-hover)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'transparent'
        ;(e.currentTarget as HTMLDivElement).style.background = 'transparent'
      }}
    >
      <span
        className="items-center justify-center shrink-0"
        style={{
          color: 'var(--text-2)',
          display: 'inline-flex',
          width: 20,
          height: 20,
          borderRadius: 5,
          background: 'transparent',
        }}
      >
        <Icon size={14} strokeWidth={1.9} />
      </span>
      <div className="flex-1 min-w-0">
        <div style={{ fontSize: 12, fontWeight: 540, color: 'var(--text-1)', lineHeight: 1.25 }}>
          {title}
        </div>
        <div className="font-mono truncate" style={{ fontSize: 9, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', marginTop: 1 }}>
          {type}
        </div>
      </div>
    </div>
  )
}
