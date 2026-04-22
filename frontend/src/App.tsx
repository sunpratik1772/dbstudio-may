import WorkflowCanvas from './components/WorkflowCanvas'
import NodePanel from './components/NodePanel'
import NodeConfig from './components/NodeConfig'
import Copilot from './components/Copilot'
import Topbar from './components/Topbar'
import WorkflowDrawer from './components/WorkflowDrawer'
import { useWorkflowStore } from './store/workflowStore'
import { useApplyTheme } from './store/themeStore'
import { useDraftAutosave } from './store/useDraftAutosave'

export default function App() {
  useApplyTheme()
  // Debounced background save of the current workflow to /drafts — so
  // anything the user builds shows up in the drawer's Drafts section.
  useDraftAutosave()
  const copilotOpen = useWorkflowStore((s) => s.copilotOpen)

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: 'var(--bg-0)', color: 'var(--text-0)' }}
    >
      <Topbar />
      <div className="flex flex-1 overflow-hidden relative">
        <NodePanel />
        <WorkflowCanvas />
        {copilotOpen && <Copilot />}
        {/* Drawer overlays the main row so its slide animation doesn't push siblings around */}
        <WorkflowDrawer />
      </div>
      {/* NodeConfig docks to the bottom — full width, collapsible. The old
          RunConsole is gone; Run / Reset / Save / Clear now live in the topbar. */}
      <NodeConfig />
    </div>
  )
}
