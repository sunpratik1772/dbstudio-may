/**
 * Left-side node palette — the draggable catalogue of node types.
 *
 * Source of truth is the generated NODE_UI registry (auto-built from
 * each backend handler's YAML). Add a new node type on the backend,
 * regenerate, and it appears here grouped by category with the right
 * colour and icon. No edits to this file.
 *
 * Drag-and-drop hands off to WorkflowCanvas via the PALETTE_DND_MIME
 * payload — the canvas creates the node at the drop coordinates.
 */
import { useMemo, useRef, useState, type DragEvent } from 'react'
import { Search } from 'lucide-react'
import { NODE_UI, NODE_TYPES, getNodeDisplayName, type NodeType } from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import { PALETTE_DND_MIME } from '../WorkflowCanvas'
import ResizeHandle from '../ResizeHandle'

type Category = {
  key: string
  label: string
  color: string
  types: NodeType[]
}

const CATEGORIES: Category[] = [
  { key: 'trigger',   label: 'TRIGGER',   color: '#F5A623', types: ['ALERT_TRIGGER'] },
  { key: 'collector', label: 'INTEGRATIONS', color: '#00E5FF', types: ['COMMS_COLLECTOR', 'TRADE_DATA_COLLECTOR', 'MARKET_DATA_COLLECTOR'] },
  { key: 'transform', label: 'TRANSFORM', color: '#A78BFA', types: ['NORMALISE_ENRICH', 'DATA_HIGHLIGHTER'] },
  { key: 'signal',    label: 'SIGNAL',    color: '#F472B6', types: ['SIGNAL_CALCULATOR'] },
  { key: 'rule',      label: 'RULE',      color: '#FBBF24', types: ['DECISION_RULE'] },
  { key: 'narrative', label: 'NARRATIVE', color: '#F472B6', types: ['SECTION_SUMMARY', 'CONSOLIDATED_SUMMARY'] },
  { key: 'output',    label: 'OUTPUT',    color: '#10B981', types: ['REPORT_OUTPUT'] },
]

export default function NodePanel() {
  const paletteWidth = useWorkflowStore((s) => s.paletteWidth)
  const setPaletteWidth = useWorkflowStore((s) => s.setPaletteWidth)
  const rootRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return CATEGORIES
    return CATEGORIES.map((c) => ({
      ...c,
      types: c.types.filter((t) => t.toLowerCase().includes(q) || NODE_UI[t].description.toLowerCase().includes(q)),
    })).filter((c) => c.types.length > 0)
  }, [query])

  return (
    <div
      ref={rootRef}
      className="flex flex-col h-full overflow-hidden relative shrink-0"
      style={{ width: paletteWidth, background: 'var(--bg-1)', borderRight: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-4 pt-4 pb-3 shrink-0">
        <div className="flex items-baseline gap-2">
          <span className="font-mono" style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)', textTransform: 'uppercase', letterSpacing: '0.18em' }}>
            NODES
          </span>
          <span className="font-mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
            {NODE_TYPES.length}
          </span>
        </div>
      </div>

      {/* Search */}
      <div className="px-4 pb-3 shrink-0">
        <div
          className="flex items-center gap-2"
          style={{
            height: 36,
            padding: '0 10px',
            borderRadius: 8,
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
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

      {/* Categories */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {filtered.map((cat) => (
          <div key={cat.key} className="mb-4">
            <div className="flex items-center justify-between px-1 mb-1.5">
              <span
                className="font-mono"
                style={{ fontSize: 10.5, fontWeight: 700, color: cat.color, textTransform: 'uppercase', letterSpacing: '0.22em' }}
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
      <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="font-mono" style={{ fontSize: 10, color: 'var(--text-3)', lineHeight: 1.5 }}>
          drag or double-click to add ·<br />
          powered by spec-driven registry
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
  const meta = NODE_UI[type]
  const Icon = meta.Icon
  const addNode = useWorkflowStore((s) => s.addNode)
  const titleCase = getNodeDisplayName(type)

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
        padding: '10px 12px',
        borderRadius: 10,
        background: 'var(--bg-node)',
        border: '1px solid var(--border)',
        transition: 'border-color 140ms, background 140ms',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = `color-mix(in srgb, ${accent} 50%, var(--border))`
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)'
      }}
    >
      <span style={{ color: accent, display: 'inline-flex' }}>
        <Icon size={16} strokeWidth={2} />
      </span>
      <div className="flex-1 min-w-0">
        <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-0)', lineHeight: 1.25 }}>
          {titleCase}
        </div>
        <div className="font-mono truncate" style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>
          {type}
        </div>
      </div>
    </div>
  )
}
