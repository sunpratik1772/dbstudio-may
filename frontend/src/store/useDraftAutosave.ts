/**
 * Auto-save the current workflow to the /drafts folder whenever it changes.
 *
 * Rules:
 *   - Only kicks in for unpersisted workflows (sourceFilename === null) or
 *     workflows already backed by a draft file (sourceKind === 'draft').
 *     Saved workflows persist via the explicit Save button.
 *   - First change allocates a filename (slug-from-name + timestamp) so the
 *     draft appears in the drawer's Drafts section the moment the user
 *     starts building.
 *   - Debounced — we don't want to POST on every keystroke in a config
 *     field, every pixel of drag, etc.
 */
import { useEffect, useRef } from 'react'
import { useWorkflowStore } from './workflowStore'
import { api } from '../services/api'
import type { Workflow } from '../types'

const DEBOUNCE_MS = 800

function slugify(name: string | undefined | null): string {
  const base = (name || 'draft').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return base || 'draft'
}

function autoDraftFilename(w: Workflow): string {
  return `${slugify(w.name)}-${Date.now()}.yaml`
}

export function useDraftAutosave(): void {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const setDraftFilename = useWorkflowStore((s) => s.setDraftFilename)

  const timer = useRef<number | null>(null)
  const lastSerialised = useRef<string>('')

  useEffect(() => {
    // Nothing to save.
    if (!workflow) return
    // Saved workflows are managed by the explicit Save button.
    if (sourceKind === 'saved') return

    const serialised = JSON.stringify(workflow)
    // Skip no-op writes (e.g. re-render from a selection toggle).
    if (serialised === lastSerialised.current) return

    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      const filename = sourceFilename ?? autoDraftFilename(workflow)
      try {
        await api.saveDraft(filename, workflow)
        lastSerialised.current = serialised
        // Assign the draft filename once so subsequent autosaves overwrite
        // the same file instead of spawning new drafts on every edit.
        if (!sourceFilename) setDraftFilename(filename)
      } catch {
        // Auto-save failures should never hard-break the app. Silent retry
        // happens on the next edit.
      }
    }, DEBOUNCE_MS)

    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [workflow, sourceFilename, sourceKind, setDraftFilename])
}
