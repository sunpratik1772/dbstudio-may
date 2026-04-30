// NodeType is any backend type_id; UI metadata is hydrated from
// `GET /node-manifest` (see `nodeRegistryStore`). This file re-exports
// the *types* only so consumers avoid pulling in lucide or the store.
export type { NodeType, NodeUIMeta, NodeMeta } from '../nodes'
import type { NodeType } from '../nodes'

export interface WorkflowNode {
  id: string
  type: NodeType
  label: string
  config: Record<string, unknown>
  /** Persisted canvas position (flow coords). Optional — missing nodes fall back to auto-layout. */
  position?: { x: number; y: number }
  /** When true the engine should skip this node. Purely a UI concern today — backend honours it if the runner filters disabled nodes before topo sort. */
  disabled?: boolean
}

export interface WorkflowEdge {
  from: string
  to: string
}

export interface Workflow {
  workflow_id: string
  name: string
  version: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export interface RunResult {
  disposition: 'ESCALATE' | 'REVIEW' | 'DISMISS' | ''
  flag_count: number
  output_branch: string
  report_path: string
  download_url?: string
  datasets: string[]
  sections: Record<string, { stats: Record<string, unknown>; narrative: string }>
  executive_summary: string
  /** Non-blocking warnings emitted by the pre-flight validator. */
  warnings?: ValidationIssue[]
}

/** Matches the shape emitted by `engine.validator.ValidationIssue.to_json()` on the backend. */
export interface ValidationIssue {
  code: string
  message: string
  severity: 'error' | 'warning'
  node_id?: string | null
  field?: string | null
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  summary: string
}

export interface RunLogEntry {
  node_id: string
  node_type: NodeType | string
  label: string
  index: number
  total: number
  status: 'running' | 'ok' | 'error'
  started_at?: string
  duration_ms?: number
  output?: {
    datasets?: Record<string, { rows: number; columns: string[]; sample: Record<string, unknown>[] }>
    context?: Record<string, unknown>
    disposition?: string
    flag_count?: number
    output_branch?: string
    section?: { name: string; stats: Record<string, unknown>; narrative_preview: string }
    executive_summary_preview?: string
    executive_summary_chars?: number
    report_path?: string
    agent_response?: string
  }
  error?: string
  trace?: string
}

export interface RunWorkflowStreamEvent {
  type:
    | 'workflow_start'
    | 'node_start'
    | 'node_complete'
    | 'node_error'
    | 'workflow_complete'
    | 'workflow_error'
  name?: string
  total_nodes?: number
  order?: string[]
  node_id?: string
  node_type?: string
  label?: string
  index?: number
  total?: number
  started_at?: string
  duration_ms?: number
  status?: string
  output?: RunLogEntry['output']
  error?: string
  trace?: string
  total_duration_ms?: number
  result?: RunResult
  /** Present on `workflow_error` frames emitted when the pre-flight validator rejects the DAG. */
  validation?: ValidationResult
  /** Present on `workflow_complete` frames when the run had non-blocking warnings. */
  warnings?: ValidationIssue[]
}

export interface CopilotMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export type CopilotPhase =
  | 'understanding'
  | 'planning'
  | 'generating'
  | 'auto_fixing'
  | 'critiquing'
  | 'finalizing'
  | 'complete'
  | 'error'

/**
 * Normalised error hint the Copilot's edit-mode receives. The
 * backend prompt builder accepts a loose shape: anything with a
 * `message` is enough, and optional `code` / `node_id` / `kind` /
 * `severity` tighten the hint. Shaped here so every call site
 * (validation, runtime, save errors) has one target type.
 */
export interface CopilotErrorHint {
  /** Validator error code (e.g. `UNKNOWN_NODE_TYPE`) when known. */
  code?: string
  /** ID of the offending node when known. */
  node_id?: string
  /** "validation" | "runtime" | "save" — helps the LLM pick a repair strategy. */
  kind?: 'validation' | 'runtime' | 'save' | string
  /** "error" | "warning" | "info". Defaults to "error" in the backend. */
  severity?: 'error' | 'warning' | 'info' | string
  /** Free-form human-readable description. */
  message: string
}

export interface CopilotStreamEvent {
  phase: CopilotPhase
  label: string
  status: 'running' | 'done' | 'error'
  detail?: string
  workflow?: Workflow
  raw?: string
  skills?: string[]
  matched?: string[]
  approved?: boolean
  draft_summary?: { name?: string; node_count?: number; edge_count?: number; node_types?: string[] }
  summary?: { name?: string; node_count?: number; edge_count?: number; node_types?: string[] }
  /** 1..iterations on `critiquing` frames produced by the validator-driven repair loop. */
  attempt?: number
  /** Structured validator errors the repair loop is trying to fix. */
  validation_errors?: ValidationIssue[]
  /** Final validator verdict — present on the terminal `complete` frame. */
  validation?: ValidationResult
  /** Human-readable list of deterministic auto-fixes applied (on `auto_fixing` frames). */
  applied?: string[]
}

