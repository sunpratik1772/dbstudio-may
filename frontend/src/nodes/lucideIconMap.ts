/**
 * AUTO-GENERATED — do not edit by hand.
 * Run `python backend/scripts/gen_artifacts.py` to regenerate.
 * Maps NodeSpec `ui.icon` strings to Lucide components (tree-shaken).
 */
import type { LucideIcon } from 'lucide-react'
import {
  ArrowLeftRight,
  Box,
  CandlestickChart,
  Clock,
  Crosshair,
  Database,
  FileSpreadsheet,
  FileStack,
  Gavel,
  Highlighter,
  ListFilter,
  ListOrdered,
  MessageSquareText,
  NotebookText,
  Repeat,
  Signal,
  Siren,
  SlidersHorizontal,
  Split,
} from 'lucide-react'

export const LUCIDE_ICON_MAP: Record<string, LucideIcon> = {
  ArrowLeftRight,
  Box,
  CandlestickChart,
  Clock,
  Crosshair,
  Database,
  FileSpreadsheet,
  FileStack,
  Gavel,
  Highlighter,
  ListFilter,
  ListOrdered,
  MessageSquareText,
  NotebookText,
  Repeat,
  Signal,
  Siren,
  SlidersHorizontal,
  Split,
}

export function resolveLucideIcon(name: string | undefined): LucideIcon {
  if (!name) return Box
  return LUCIDE_ICON_MAP[name] ?? Box
}
