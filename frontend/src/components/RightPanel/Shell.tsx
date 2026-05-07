import { useRef } from 'react'
import { X as XIcon } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import ResizeHandle from '../ResizeHandle'
import { useWorkflowStore } from '../../store/workflowStore'

interface ShellProps {
  icon: LucideIcon
  title: string
  eyebrow?: string
  subtitle?: React.ReactNode
  accent?: string
  rightSlot?: React.ReactNode
  children: React.ReactNode
}

/**
 * Outer chrome shared by Config + Run Log views in the unified right panel.
 * Matches the existing Copilot panel's resize behaviour and width source so
 * the three modes feel like one component switching content.
 */
export default function Shell({ icon: Icon, title, eyebrow, subtitle, accent, rightSlot, children }: ShellProps) {
  const copilotWidth = useWorkflowStore((s) => s.copilotWidth)
  const setCopilotWidth = useWorkflowStore((s) => s.setCopilotWidth)
  const setMode = useWorkflowStore((s) => s.setRightPanelMode)
  const rootRef = useRef<HTMLDivElement>(null)

  const tone = accent ?? 'var(--text-1)'

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
      <ResizeHandle
        edge="left"
        ariaLabel="Resize right panel"
        onResize={(clientX) => {
          const right = rootRef.current?.getBoundingClientRect().right ?? window.innerWidth
          setCopilotWidth(right - clientX)
        }}
      />
      <div
        className="px-4 pt-4 pb-3 shrink-0"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <Icon size={16} strokeWidth={2} style={{ color: tone }} />
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-0)' }}>
            {title}
          </span>
          {eyebrow && (
            <span className="font-mono" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              {eyebrow}
            </span>
          )}
          <div className="flex-1" />
          {rightSlot}
          <button
            onClick={() => setMode(null)}
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
        {subtitle && (
          <div className="mt-2" style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            {subtitle}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Section primitives — used inside Shell bodies for visual consistency.      */
/* -------------------------------------------------------------------------- */
export function SectionHeader({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <div
      className="font-mono"
      style={{
        fontSize: 10,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: accent ?? 'var(--text-3)',
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  )
}

export function Section({ title, accent, children }: { title: string; accent?: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
      <SectionHeader accent={accent}>{title}</SectionHeader>
      {children}
    </div>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center px-6 py-12"
      style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6 }}
    >
      {children}
    </div>
  )
}
