/**
 * Right-click context menu for canvas nodes — n8n-style.
 *
 * Rendered in a portal-esque fixed position so it escapes React Flow's
 * transformed parent and isn't clipped by the viewport. Backdrop captures
 * the next click / Esc to dismiss.
 */
import { useEffect, useRef } from 'react'
import { Copy, Files, Trash2, Power, Link2Off, type LucideIcon } from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'

export interface ContextMenuState {
  x: number
  y: number
  nodeId: string
}

interface Props {
  menu: ContextMenuState
  onClose: () => void
  onCopy: () => void
}

export default function NodeContextMenu({ menu, onClose, onCopy }: Props) {
  const deleteNodes = useWorkflowStore((s) => s.deleteNodes)
  const duplicateNodes = useWorkflowStore((s) => s.duplicateNodes)
  const toggleNodeDisabled = useWorkflowStore((s) => s.toggleNodeDisabled)
  const workflow = useWorkflowStore((s) => s.workflow)
  const node = workflow?.nodes.find((n) => n.id === menu.nodeId)
  const rootRef = useRef<HTMLDivElement>(null)

  // Dismiss on outside click or Esc.
  useEffect(() => {
    const down = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) onClose()
    }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('mousedown', down)
    window.addEventListener('keydown', key)
    return () => {
      window.removeEventListener('mousedown', down)
      window.removeEventListener('keydown', key)
    }
  }, [onClose])

  // Nudge the menu if it would overflow the viewport.
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight
    if (rect.right > vw) el.style.left = `${Math.max(4, vw - rect.width - 6)}px`
    if (rect.bottom > vh) el.style.top = `${Math.max(4, vh - rect.height - 6)}px`
  }, [menu.x, menu.y])

  if (!node) return null

  const isDisabled = !!node.disabled

  const Item = ({
    icon: Icon,
    label,
    shortcut,
    onClick,
    tone = 'default',
  }: {
    icon: LucideIcon
    label: string
    shortcut?: string
    onClick: () => void
    tone?: 'default' | 'danger'
  }) => (
    <button
      onClick={() => {
        onClick()
        onClose()
      }}
      className="flex items-center gap-2.5 w-full text-left px-2.5 py-1.5 rounded-md"
      style={{
        fontSize: 12,
        color: tone === 'danger' ? 'var(--danger)' : 'var(--text-0)',
        background: 'transparent',
        transition: 'background 100ms ease',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLButtonElement).style.background =
          tone === 'danger'
            ? 'color-mix(in srgb, var(--danger) 15%, transparent)'
            : 'var(--bg-3)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
      }}
    >
      <Icon size={13} strokeWidth={2} />
      <span className="flex-1">{label}</span>
      {shortcut && (
        <span className="num" style={{ color: 'var(--text-3)', fontSize: 10.5 }}>
          {shortcut}
        </span>
      )}
    </button>
  )

  const isMac = typeof navigator !== 'undefined' && /mac/i.test(navigator.platform)
  const mod = isMac ? '⌘' : 'Ctrl'

  return (
    <div
      ref={rootRef}
      className="fixed"
      style={{
        left: menu.x,
        top: menu.y,
        zIndex: 1000,
        minWidth: 200,
        background: 'var(--bg-1)',
        border: '1px solid var(--border-strong)',
        borderRadius: 8,
        boxShadow: '0 16px 40px -12px rgba(0,0,0,.45)',
        padding: 4,
      }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div
        className="eyebrow px-2.5 py-1.5"
        style={{ color: 'var(--text-2)', fontSize: 9.5, letterSpacing: '0.14em' }}
      >
        {node.type.replace(/_/g, ' ')} · {node.id}
      </div>
      <Item icon={Files} label="Duplicate" shortcut={`${mod}+D`} onClick={() => duplicateNodes([node.id])} />
      <Item icon={Copy} label="Copy" shortcut={`${mod}+C`} onClick={onCopy} />
      <Item
        icon={Power}
        label={isDisabled ? 'Enable node' : 'Disable node'}
        onClick={() => toggleNodeDisabled(node.id)}
      />
      <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
      <Item icon={Link2Off} label="Clear connections" onClick={() => {
        const { workflow: w, deleteEdge } = useWorkflowStore.getState()
        if (!w) return
        w.edges
          .filter((e) => e.from === node.id || e.to === node.id)
          .forEach((e) => deleteEdge(e.from, e.to))
      }} />
      <Item
        icon={Trash2}
        label="Delete"
        shortcut="Del"
        onClick={() => deleteNodes([node.id])}
        tone="danger"
      />
    </div>
  )
}
