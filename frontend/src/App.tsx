/**
 * Top-level layout. Five regions, all driven by the workflow store:
 *
 *   ┌─────────────────────────────────────────────────────────┐
 *   │ Topbar               (workflow name, run/save buttons)   │
 *   ├──────────┬─────────────────────┬──────────┬──────────────┤
 *   │ NodePanel│ WorkflowCanvas      │ Activity │ RightPanel   │
 *   │ (palette)│ (React Flow graph)  │ Rail     │ (config /     │
 *   │          │                     │ (run log)│  copilot)    │
 *   ├──────────┴─────────────────────┴──────────┴──────────────┤
 *   │ WorkflowDrawer  (saved workflows list, slides up)         │
 *   └─────────────────────────────────────────────────────────┘
 *
 * This file is intentionally tiny — every region owns its own state
 * and reads from `useWorkflowStore` directly. Two cross-cutting hooks
 * run here so they outlive any individual region:
 *
 *   • useApplyTheme       — applies the user's dark/light choice to
 *                           the document root.
 *   • useDraftAutosave    — debounced autosave to /drafts when the
 *                           current workflow changes.
 */
import { useEffect } from 'react'
import WorkflowCanvas from './components/WorkflowCanvas'
import NodePanel from './components/NodePanel'
import RightPanel from './components/RightPanel'
import Topbar from './components/Topbar'
import WorkflowDrawer from './components/WorkflowDrawer'
import ActivityRail from './components/ActivityRail'
import { useApplyTheme } from './store/themeStore'
import { useDraftAutosave } from './store/useDraftAutosave'
import { useNodeRegistryStore } from './store/nodeRegistryStore'

export default function App() {
  useApplyTheme()
  useDraftAutosave()
  useEffect(() => {
    void useNodeRegistryStore.getState().refreshFromBackend()
  }, [])

  return (
    <div className="relative h-screen overflow-hidden text-[var(--text-0)]">
      <div className="studio-backdrop" aria-hidden>
        <div className="studio-backdrop__wash" />
        <div className="studio-backdrop__blob studio-backdrop__blob--1" />
        <div className="studio-backdrop__blob studio-backdrop__blob--2" />
        <div className="studio-backdrop__blob studio-backdrop__blob--3" />
      </div>
      <div className="relative z-10 flex flex-col h-full">
        <Topbar />
        <div className="flex flex-1 overflow-hidden relative min-h-0">
          <NodePanel />
          <WorkflowCanvas />
          <ActivityRail />
          <RightPanel />
          <WorkflowDrawer />
        </div>
      </div>
    </div>
  )
}
