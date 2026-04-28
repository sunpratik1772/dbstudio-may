/**
 * Thin HTTP client for every backend endpoint the UI calls.
 *
 * Conventions:
 *   • One async function per endpoint; named after the action, not the
 *     URL ("listWorkflows" not "getWorkflows").
 *   • All requests go through `request()` so error parsing,
 *     ValidationError raising, and JSON content-type are centralised.
 *   • Streaming endpoints (/run/stream, /copilot/stream) return an
 *     async iterable of typed SSE events — components consume them
 *     with `for await (const ev of streamRun(...))`.
 *
 * Vite's dev server proxies `/api/*` to the FastAPI backend at
 * localhost:8000 (see vite.config.ts), so BASE stays relative.
 */
import type {
  Workflow,
  RunResult,
  CopilotStreamEvent,
  CopilotErrorHint,
  RunWorkflowStreamEvent,
  ValidationResult,
} from '../types'

const BASE = '/api'

/**
 * Thrown when `/run` (or any other endpoint) rejects a DAG because it
 * failed the deterministic validator. Callers can `instanceof` check it
 * to surface structured per-node errors instead of a generic message.
 */
/** Live NodeSpec bundle for Studio palette + config inspector (`GET /node-manifest`). */
export interface NodeManifestPayload {
  version: number
  palette_sections: Array<{ id: string; label: string; order: number; color: string }>
  nodes: Array<{
    type_id: string
    description: string
    color: string
    icon: string
    config_tags?: string[]
    palette_group: string
    palette_order: number
    display_name?: string
    input_ports: unknown[]
    output_ports: unknown[]
    params: unknown[]
    contract: {
      description: string
      inputs: Record<string, string>
      outputs: Record<string, string>
      config_schema: Record<string, string>
      constraints: string[]
    }
  }>
}

export interface CopilotGuardrailsPayload {
  nodes: Array<{ type_id: string; description: string; section?: string }>
  data_sources: Array<{ id: string; description: string; sources: string[] }>
  skills: Array<{ id: string; name: string; filename: string }>
  capabilities: {
    upload_script_enabled: boolean
    allowed_signal_modes: string[]
    builtin_signal_types: string[]
  }
  rules: string[]
}

export class ValidationError extends Error {
  readonly validation: ValidationResult

  constructor(validation: ValidationResult) {
    super(validation.summary || 'Workflow failed validation')
    this.name = 'ValidationError'
    this.validation = validation
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    // The /run endpoint surfaces validator failures as HTTP 422 with
    // `detail` shaped like ValidationResult — unwrap it into a typed
    // error so the UI can highlight the offending nodes.
    if (res.status === 422 && err && typeof err.detail === 'object' && err.detail?.errors) {
      throw new ValidationError(err.detail as ValidationResult)
    }
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export interface StoredWorkflow {
  filename: string
  name: string
  description: string
  node_count: number
  /** Epoch ms of last file modification. */
  modified_ms?: number
}

export const api = {
  // -- Saved workflows (named, promoted) -----------------------------
  listWorkflows: () => request<{ workflows: StoredWorkflow[] }>('GET', '/workflows'),
  getWorkflow: (filename: string) => request<Workflow>('GET', `/workflows/${filename}`),
  saveWorkflow: (filename: string, dag: Workflow) => request<{ saved: string }>('POST', `/workflows/${filename}`, dag),
  deleteWorkflow: (filename: string) => request<{ deleted: string }>('DELETE', `/workflows/${filename}`),
  workflowFromYaml: (content: string) =>
    request<{ workflow: Workflow }>('POST', '/workflow-format/yaml-to-json', { content }),
  workflowToYaml: (workflow: Workflow) =>
    request<{ content: string }>('POST', '/workflow-format/json-to-yaml', { workflow }),

  // -- Drafts (auto-saved, transient) --------------------------------
  listDrafts: () => request<{ drafts: StoredWorkflow[] }>('GET', '/drafts'),
  getDraft: (filename: string) => request<Workflow>('GET', `/drafts/${filename}`),
  saveDraft: (filename: string, dag: Workflow) => request<{ saved: string }>('POST', `/drafts/${filename}`, dag),
  deleteDraft: (filename: string) => request<{ deleted: string }>('DELETE', `/drafts/${filename}`),
  /** Move a draft to saved/, optionally updating the embedded name. */
  promoteDraft: (filename: string, target_filename: string, name?: string) =>
    request<{ promoted: string; saved_as: string }>('POST', `/drafts/${filename}/promote`, { target_filename, name }),

  // -- Validation ----------------------------------------------------
  /** Deterministic pre-flight check — safe to call continuously. */
  validateWorkflow: (dag: Workflow) => request<ValidationResult>('POST', '/validate', { dag }),

  runWorkflow: (dag: Workflow, alert_payload: Record<string, string>) => request<RunResult>('POST', '/run', { dag, alert_payload }),

  runWorkflowStream: async (
    dag: Workflow,
    alert_payload: Record<string, string>,
    onEvent: (ev: RunWorkflowStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(BASE + '/run/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ dag, alert_payload }),
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as RunWorkflowStreamEvent) } catch { /* skip malformed */ }
        }
      }
    }
  },

  reportDownloadUrl: (filename: string) => `${BASE}/report/${encodeURIComponent(filename)}`,
  copilotChat: (message: string, reset_history = false) => request<{ reply: string }>('POST', '/copilot/chat', { message, reset_history }),
  copilotGenerate: (
    prompt: string,
    critic_iterations = 3,
    current_workflow?: Workflow | null,
    recent_errors?: CopilotErrorHint[] | null,
    selected_node_id?: string | null,
  ) =>
    request<{ success: boolean; workflow?: Workflow; error?: string }>('POST', '/copilot/generate', {
      prompt,
      critic_iterations,
      current_workflow: current_workflow ?? null,
      recent_errors: recent_errors ?? null,
      selected_node_id: selected_node_id ?? null,
    }),

  /**
   * SSE stream that accepts the optional edit-mode fields. When
   * `current_workflow` is supplied the backend switches the planner
   * from greenfield generation to a targeted edit of the DAG —
   * preserving node IDs and only changing what the errors / user
   * request require. `selected_node_id` lets deictic phrases
   * ("this", "here") in the request resolve to a concrete node.
   */
  copilotGenerateStream: async (
    prompt: string,
    critic_iterations = 3,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    current_workflow?: Workflow | null,
    recent_errors?: CopilotErrorHint[] | null,
    selected_node_id?: string | null,
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        prompt,
        critic_iterations,
        current_workflow: current_workflow ?? null,
        recent_errors: recent_errors ?? null,
        selected_node_id: selected_node_id ?? null,
      }),
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as CopilotStreamEvent) } catch { /* ignore malformed */ }
        }
      }
    }
  },
  listSkills: () => request<{ skills: Array<{ id: string; name: string; filename: string }> }>('GET', '/copilot/skills'),
  getSkill: (id: string) => request<{ id: string; content: string }>('GET', `/copilot/skills/${id}`),
  getCopilotGuardrails: () => request<CopilotGuardrailsPayload>('GET', '/copilot/guardrails'),
  getContracts: () => request<Record<string, unknown>>('GET', '/contracts'),
  /** Palette + node metadata + contracts from the live backend registry. */
  getNodeManifest: () => request<NodeManifestPayload>('GET', '/node-manifest'),
}
