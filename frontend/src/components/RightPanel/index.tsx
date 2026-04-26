import { useWorkflowStore } from '../../store/workflowStore'
import Copilot from '../Copilot'
import ConfigView from './ConfigView'
import RunLogView from './RunLogView'
import OutputView from './OutputView'

/**
 * Single right-side panel that switches between Config / Run Log / Copilot
 * based on the activity rail selection. All three modes share the resizable
 * width (copilotWidth in the store) and visual chrome (Shell.tsx) so they
 * feel like one component swapping content.
 */
export default function RightPanel() {
  const mode = useWorkflowStore((s) => s.rightPanelMode)
  if (mode === null) return null
  if (mode === 'config') return <ConfigView />
  if (mode === 'runlog') return <RunLogView />
  if (mode === 'output') return <OutputView />
  if (mode === 'copilot') return <Copilot />
  return null
}
