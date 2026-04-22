import { useRef, type DragEvent } from 'react'
import { NODE_UI, NODE_TYPES, type NodeType } from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import { PALETTE_DND_MIME } from '../WorkflowCanvas'
import ResizeHandle from '../ResizeHandle'

export default function NodePanel() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const paletteWidth = useWorkflowStore((s) => s.paletteWidth)
  const setPaletteWidth = useWorkflowStore((s) => s.setPaletteWidth)
  const rootRef = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={rootRef}
      className="flex flex-col h-full overflow-y-auto relative shrink-0"
      style={{ width: paletteWidth, background: 'var(--bg-1)', borderRight: '1px solid var(--border)' }}
    >
      <div className="px-3 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 className="eyebrow" style={{ color: 'var(--text-1)' }}>Node Palette</h3>
        <p style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 4 }}>
          Drag a node onto the canvas. The ×N badge shows how many of that type are already in the current workflow.
        </p>
      </div>

      <div className="flex-1 p-2 space-y-1">
        {NODE_TYPES.map((type) => {
          const meta = NODE_UI[type]
          const IconComp = meta.Icon
          const usedCount = workflow?.nodes.filter((n) => n.type === type).length ?? 0
          return (
            <div
              key={type}
              draggable
              onDragStart={(e: DragEvent<HTMLDivElement>) => {
                // Both MIMEs — the custom one gives us a type-safe lookup on
                // the canvas, the text/plain fallback keeps Safari happy.
                e.dataTransfer.setData(PALETTE_DND_MIME, type)
                e.dataTransfer.setData('text/plain', type)
                e.dataTransfer.effectAllowed = 'copyMove'
              }}
              title={`${type.replace(/_/g, ' ')} — ${meta.description}\n\nDrag onto canvas to add.`}
              className="flex items-center gap-2 px-2 py-2 rounded-lg cursor-grab active:cursor-grabbing lift"
              style={{
                background: 'var(--bg-2)',
                border: `1px solid color-mix(in srgb, ${meta.color} 22%, var(--border))`,
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.borderColor = `color-mix(in srgb, ${meta.color} 55%, transparent)`
                ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-3)'
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.borderColor = `color-mix(in srgb, ${meta.color} 22%, var(--border))`
                ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-2)'
              }}
            >
              <span
                className="flex items-center justify-center rounded shrink-0"
                style={{
                  width: 22, height: 22,
                  background: `${meta.color}14`,
                  border: `1px solid ${meta.color}35`,
                  color: meta.color,
                }}
              >
                <IconComp size={13} strokeWidth={2} />
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="truncate"
                  style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-0)', lineHeight: 1.2 }}
                >
                  {type.replace(/_/g, ' ')}
                </div>
              </div>
              {usedCount > 0 && (
                <span
                  className="num rounded-full px-1.5 py-0.5"
                  style={{
                    fontSize: 10,
                    background: `color-mix(in srgb, ${meta.color} 18%, transparent)`,
                    color: meta.color,
                    fontWeight: 600,
                  }}
                  title={`${usedCount} ${type.replace(/_/g, ' ').toLowerCase()} node${usedCount === 1 ? '' : 's'} in the current workflow`}
                >
                  ×{usedCount}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {workflow && (
        <div className="p-3" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="space-y-1" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
            <StatRow k="Nodes" v={String(workflow.nodes.length)} />
            <StatRow k="Edges" v={String(workflow.edges.length)} />
            <StatRow k="Version" v={workflow.version} />
          </div>
        </div>
      )}

      {/* Drag the right edge to resize the palette (VSCode-style). */}
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

function StatRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="eyebrow" style={{ color: 'var(--text-2)' }}>{k}</span>
      <span className="num" style={{ color: 'var(--text-0)', fontSize: 11.5, fontWeight: 500 }}>{v}</span>
    </div>
  )
}
