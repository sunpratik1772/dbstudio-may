/**
 * Narrow icon rail that controls the right-side work area.
 *
 * Each button toggles `workflowStore.rightPanelMode`; clicking the active
 * mode collapses the panel back to rail-only. The visible panel body lives
 * in `RightPanel/index.tsx`, and the shared width is still named
 * `copilotWidth` for historical reasons even though Config/Run/Output use it.
 */
import { Settings2, Bot, Activity, FileOutput } from 'lucide-react'
import { useWorkflowStore } from '../store/workflowStore'

export default function ActivityRail() {
  const mode = useWorkflowStore((s) => s.rightPanelMode)
  const toggle = useWorkflowStore((s) => s.toggleRightPanelMode)

  return (
    <div
      className="panel-glass flex flex-col items-center py-3 gap-1 shrink-0"
      style={{
        width: 48,
        borderLeft: '1px solid var(--border)',
      }}
    >
      <RailButton
        icon={<Settings2 size={16} strokeWidth={1.8} />}
        active={mode === 'config'}
        onClick={() => toggle('config')}
        title="Inspector"
      />
      <RailButton
        icon={<Bot size={16} strokeWidth={1.8} />}
        active={mode === 'copilot'}
        onClick={() => toggle('copilot')}
        title="Copilot"
      />
      <RailButton
        icon={<Activity size={16} strokeWidth={1.8} />}
        active={mode === 'runlog'}
        onClick={() => toggle('runlog')}
        title="Run log"
      />
      <RailButton
        icon={<FileOutput size={16} strokeWidth={1.8} />}
        active={mode === 'output'}
        onClick={() => toggle('output')}
        title="Output"
      />
    </div>
  )
}

function RailButton({ icon, active, onClick, title }: { icon: React.ReactNode; active: boolean; onClick: () => void; title: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="flex items-center justify-center"
      style={{
        width: 36, height: 36,
        borderRadius: 8,
        background: active
          ? 'color-mix(in srgb, var(--accent) 22%, transparent)'
          : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-3)',
        border: 'none',
        cursor: 'pointer',
      }}
    >
      {icon}
    </button>
  )
}
