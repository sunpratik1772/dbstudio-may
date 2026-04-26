/**
 * ConfigInspector
 * ---------------
 * The single surface where a user (or the Copilot, via the same store
 * actions) edits everything about a selected node:
 *
 *   1. Header     — what this node is.
 *   2. Wiring     — inputs this node consumes (with the upstream node that
 *                   produces each one) and outputs this node emits (with
 *                   the downstream nodes that consume each one).
 *                   Input of one === output of the next.
 *   3. Config     — fields from **generated** `NODE_TYPED.params` (ParamSpec);
 *                   `input_ref` / enums / widgets match the backend YAML.
 *   4. Last run   — runtime output for this node from the most recent run.
 */
import { useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  ArrowLeftRight,
  ArrowRight,
  Info,
  AlertTriangle,
  Link2,
  Eye,
} from 'lucide-react'
import {
  NODE_UI,
  getNodeConstraints,
  getNodeTypedSpec,
  type NodeType,
  type NodeParamSpec,
} from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import type { WorkflowNode, RunLogEntry } from '../../types'

type FieldKind =
  | 'input-ref'      // dropdown of upstream output_names
  | 'output-name'    // free text, defaults to a sensible slug
  | 'boolean'
  | 'number'
  | 'string'
  | 'stringEnum'     // single-line with known options from the schema
  | 'stringArray'
  | 'json'

interface FieldDescriptor {
  key: string
  hint: string
  kind: FieldKind
  enumValues?: readonly string[]
  /** From ParamSpec.widget — long text / code editors. */
  multiline?: boolean
}

/* -------------------------------------------------------------------------- */
/* ParamSpec (generated NODE_TYPED) → field descriptors — preferred path.    */
/* -------------------------------------------------------------------------- */
function paramSpecToFieldDescriptor(p: NodeParamSpec): FieldDescriptor {
  const hint = p.description
  if (p.type === 'input_ref' || p.widget === 'input_ref') {
    return { key: p.name, hint, kind: 'input-ref' }
  }
  if (p.name === 'output_name' || p.name.endsWith('_output_name') || p.name === 'output_path') {
    return { key: p.name, hint, kind: 'output-name' }
  }
  if (p.type === 'boolean') {
    return { key: p.name, hint, kind: 'boolean' }
  }
  if (p.type === 'integer' || p.type === 'number') {
    return { key: p.name, hint, kind: 'number' }
  }
  if (p.type === 'enum' && p.enum && p.enum.length > 0) {
    return { key: p.name, hint, kind: 'stringEnum', enumValues: p.enum }
  }
  if (p.type === 'string_list') {
    return { key: p.name, hint, kind: 'stringArray' }
  }
  if (p.type === 'object' || p.type === 'array' || p.widget === 'json') {
    return { key: p.name, hint, kind: 'json' }
  }
  if (p.type === 'code' || p.widget === 'code') {
    return { key: p.name, hint, kind: 'string', multiline: true }
  }
  if (p.widget === 'textarea') {
    return { key: p.name, hint, kind: 'string', multiline: true }
  }
  return { key: p.name, hint, kind: 'string' }
}

/* -------------------------------------------------------------------------- */
/* Wiring — walk the DAG once per render to figure out who feeds whom.        */
/* -------------------------------------------------------------------------- */
interface UpstreamOutput {
  /** Node id that produces this output. */
  producerId: string
  producerLabel: string
  producerType: string
  /** Value of the producer's config.output_name (what goes on the wire). */
  name: string
}

interface WiringInfo {
  /**
   * Every upstream dataset name reachable from this node, along with its
   * producer. Direct parents come first; transitive reach-back comes after.
   */
  upstreamOutputs: UpstreamOutput[]
  /** Direct parent node ids. */
  parents: string[]
  /** Direct child node ids. */
  children: string[]
  /** Downstream consumers keyed by this node's output_name. */
  consumersByOutput: Record<string, { id: string; label: string }[]>
}

function computeWiring(node: WorkflowNode, nodes: WorkflowNode[], edges: { from: string; to: string }[]): WiringInfo {
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const parents = edges.filter((e) => e.to === node.id).map((e) => e.from)
  const children = edges.filter((e) => e.from === node.id).map((e) => e.to)

  // Walk backwards to collect every ancestor's output_name. BFS keeps
  // ordering roughly topological, which matters for the dropdown.
  const seen = new Set<string>()
  const order: string[] = []
  const queue = [...parents]
  while (queue.length > 0) {
    const id = queue.shift()!
    if (seen.has(id)) continue
    seen.add(id)
    order.push(id)
    const n = nodeById.get(id)
    if (!n) continue
    for (const e of edges) {
      if (e.to === id && !seen.has(e.from)) queue.push(e.from)
    }
  }

  const upstreamOutputs: UpstreamOutput[] = []
  for (const id of order) {
    const n = nodeById.get(id)
    if (!n) continue
    const outName = (n.config as Record<string, unknown> | undefined)?.output_name
    if (typeof outName === 'string' && outName.trim()) {
      upstreamOutputs.push({
        producerId: n.id,
        producerLabel: n.label,
        producerType: n.type,
        name: outName,
      })
    }
  }

  // Downstream consumers — match each child's input_name against this
  // node's output_name if we know it.
  const ourOutput = (node.config as Record<string, unknown> | undefined)?.output_name
  const consumersByOutput: Record<string, { id: string; label: string }[]> = {}
  if (typeof ourOutput === 'string' && ourOutput) {
    const consumers = children
      .map((id) => nodeById.get(id))
      .filter((n): n is WorkflowNode => !!n)
      .filter((n) => {
        const inName = (n.config as Record<string, unknown>)?.input_name
        return inName === ourOutput
      })
      .map((n) => ({ id: n.id, label: n.label }))
    if (consumers.length) consumersByOutput[ourOutput] = consumers
  }

  return { upstreamOutputs, parents, children, consumersByOutput }
}

/* -------------------------------------------------------------------------- */
/* Shared bits                                                                */
/* -------------------------------------------------------------------------- */
function SectionLabel({ icon: Icon, children, accent }: { icon: LucideIcon; children: React.ReactNode; accent?: string }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <Icon size={12} strokeWidth={2.2} />
      <span
        className="eyebrow"
        style={{ color: accent ?? 'var(--text-2)', letterSpacing: '0.14em' }}
      >
        {children}
      </span>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Field renderers                                                            */
/* -------------------------------------------------------------------------- */
interface FieldRowProps {
  field: FieldDescriptor
  value: unknown
  upstreamOutputs: UpstreamOutput[]
  onChange: (v: unknown) => void
}

function FieldRow({ field, value, upstreamOutputs, onChange }: FieldRowProps) {
  return (
    <div
      className="rounded-lg p-2.5"
      style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
    >
      <div className="flex items-center justify-between mb-1.5">
        <label className="num" style={{ fontSize: 11.5, color: 'var(--text-0)', fontWeight: 600 }}>
          {field.key}
        </label>
        <span className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 9.5 }}>
          {field.kind}
        </span>
      </div>
      <FieldInput field={field} value={value} upstreamOutputs={upstreamOutputs} onChange={onChange} />
      {field.hint && (
        <p className="mt-1.5" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {field.hint}
        </p>
      )}
    </div>
  )
}

function FieldInput({ field, value, upstreamOutputs, onChange }: FieldRowProps) {
  const inputStyle: React.CSSProperties = {
    width: '100%',
    fontSize: 11.5,
    color: 'var(--text-0)',
    background: 'var(--bg-1)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    padding: '6px 8px',
    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
  }

  if (field.kind === 'input-ref') {
    const current = typeof value === 'string' ? value : ''
    // Always allow free-text too — copilot may point at an output_name that
    // hasn't been set yet. Dropdown is a convenience, not a constraint.
    return (
      <div className="space-y-1.5">
        {upstreamOutputs.length > 0 ? (
          <select
            value={upstreamOutputs.some((u) => u.name === current) ? current : ''}
            onChange={(e) => onChange(e.target.value || null)}
            style={inputStyle}
          >
            <option value="">— choose an upstream output —</option>
            {upstreamOutputs.map((u) => (
              <option key={`${u.producerId}:${u.name}`} value={u.name}>
                {u.name}  ·  from {u.producerId} ({u.producerType.toLowerCase().replace(/_/g, ' ')})
              </option>
            ))}
          </select>
        ) : (
          <div
            className="flex items-center gap-1.5"
            style={{ fontSize: 10.5, color: 'var(--warning, #B45309)' }}
          >
            <AlertTriangle size={11} strokeWidth={2.2} />
            No upstream nodes produce an <span className="num">output_name</span> yet.
          </div>
        )}
        <input
          type="text"
          value={current}
          onChange={(e) => onChange(e.target.value)}
          placeholder="or type a dataset name…"
          style={{ ...inputStyle, fontSize: 11 }}
        />
      </div>
    )
  }

  if (field.kind === 'boolean') {
    const checked = value === true
    return (
      <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 11.5, color: 'var(--text-1)' }}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          style={{ width: 14, height: 14 }}
        />
        <span>{checked ? 'true' : 'false'}</span>
      </label>
    )
  }

  if (field.kind === 'number') {
    const num = typeof value === 'number' ? value : value == null ? '' : Number(value)
    return (
      <input
        type="number"
        value={num === '' || Number.isNaN(num) ? '' : num}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
        style={inputStyle}
      />
    )
  }

  if (field.kind === 'stringEnum' && field.enumValues) {
    const current = typeof value === 'string' ? value : ''
    return (
      <select value={current} onChange={(e) => onChange(e.target.value || null)} style={inputStyle}>
        <option value="">— choose —</option>
        {field.enumValues.map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    )
  }

  if (field.kind === 'stringArray') {
    const arr = Array.isArray(value) ? value : []
    const text = arr.join(', ')
    return (
      <input
        type="text"
        value={text}
        onChange={(e) => {
          const next = e.target.value
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
          onChange(next)
        }}
        placeholder="comma-separated"
        style={inputStyle}
      />
    )
  }

  if (field.kind === 'output-name' || field.kind === 'string') {
    const current = typeof value === 'string' ? value : ''
    if (field.multiline) {
      return (
        <textarea
          value={current}
          onChange={(e) => onChange(e.target.value)}
          rows={5}
          spellCheck={field.key.includes('script') || field.key.includes('template') ? false : undefined}
          style={{ ...inputStyle, resize: 'vertical', minHeight: 80, lineHeight: 1.45 }}
        />
      )
    }
    return (
      <input
        type="text"
        value={current}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    )
  }

  // Fallback — JSON editor. Preserves invalid text while the user is typing
  // so we don't mangle half-written objects.
  return <JsonField value={value} onChange={onChange} style={inputStyle} />
}

function JsonField({ value, onChange, style }: { value: unknown; onChange: (v: unknown) => void; style: React.CSSProperties }) {
  const initial = useMemo(() => (value === undefined ? '' : JSON.stringify(value, null, 2)), [value])
  const [draft, setDraft] = useState<string>(initial)
  const [err, setErr] = useState<string | null>(null)

  return (
    <div>
      <textarea
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value)
          if (e.target.value.trim() === '') {
            setErr(null)
            onChange(null)
            return
          }
          try {
            const parsed = JSON.parse(e.target.value)
            setErr(null)
            onChange(parsed)
          } catch (ex) {
            setErr((ex as Error).message)
          }
        }}
        rows={Math.min(10, Math.max(3, draft.split('\n').length))}
        spellCheck={false}
        style={{ ...style, resize: 'vertical', minHeight: 60 }}
      />
      {err && (
        <div className="mt-1" style={{ fontSize: 10, color: 'var(--danger)' }}>
          {err}
        </div>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Wiring card — inputs / outputs from NODE_TYPED (PortSpec), not string maps. */
/* -------------------------------------------------------------------------- */
function WiringCard({ node, wiring }: { node: WorkflowNode; wiring: WiringInfo }) {
  const typed = getNodeTypedSpec(node.type)
  if (!typed) return null
  const inputs = typed.inputPorts
  const outputs = typed.outputPorts
  if (inputs.length === 0 && outputs.length === 0) return null

  const nodeCfg = (node.config ?? {}) as Record<string, unknown>
  const inputName = typeof nodeCfg.input_name === 'string' ? nodeCfg.input_name : undefined
  const outputName = typeof nodeCfg.output_name === 'string' ? nodeCfg.output_name : undefined

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
      <div
        className="rounded-lg p-3"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--border)' }}
      >
        <SectionLabel icon={ArrowRight} accent="var(--info)">Inputs</SectionLabel>
        {inputs.length === 0 ? (
          <p style={{ fontSize: 11, color: 'var(--text-3)' }}>No inputs.</p>
        ) : (
          <div className="space-y-1.5">
            {inputs.map((port) => {
              const isDataframe = port.type === 'dataframe'
              const wireName = isDataframe ? inputName : undefined
              const producer = wireName
                ? wiring.upstreamOutputs.find((u) => u.name === wireName)
                : undefined
              return (
                <div
                  key={port.name}
                  className="rounded p-2"
                  style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
                >
                  <div className="flex items-center gap-2" style={{ fontSize: 11 }}>
                    <span className="num" style={{ color: 'var(--info)' }}>{port.name}</span>
                    <span className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 9 }}>{port.type}</span>
                    {isDataframe && wireName && (
                      <>
                        <ArrowRight size={11} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
                        <span
                          className="num rounded px-1.5"
                          style={{
                            color: 'var(--text-0)',
                            background: 'color-mix(in srgb, var(--info) 12%, transparent)',
                            border: '1px solid color-mix(in srgb, var(--info) 30%, transparent)',
                          }}
                        >
                          {wireName}
                        </span>
                      </>
                    )}
                  </div>
                  <p className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {port.description}
                  </p>
                  {isDataframe && (
                    <div className="mt-1.5 flex items-center gap-1.5" style={{ fontSize: 10.5 }}>
                      <Link2 size={10} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
                      {producer ? (
                        <span style={{ color: 'var(--text-2)' }}>
                          produced by{' '}
                          <span className="num" style={{ color: 'var(--text-0)', fontWeight: 600 }}>
                            {producer.producerId}
                          </span>
                          {' · '}
                          <span style={{ color: 'var(--text-2)' }}>
                            {producer.producerType.toLowerCase().replace(/_/g, ' ')}
                          </span>
                        </span>
                      ) : wireName ? (
                        <span style={{ color: 'var(--warning, #B45309)' }}>
                          No upstream node emits <span className="num">{wireName}</span>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-3)' }}>
                          Set <span className="num">input_name</span> in config to wire a dataset
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div
        className="rounded-lg p-3"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--border)' }}
      >
        <SectionLabel icon={ArrowLeftRight} accent="var(--success)">Outputs</SectionLabel>
        {outputs.length === 0 ? (
          <p style={{ fontSize: 11, color: 'var(--text-3)' }}>No outputs.</p>
        ) : (
          <div className="space-y-1.5">
            {outputs.map((port) => {
              const isDataframe = port.type === 'dataframe'
              const wireName = isDataframe ? outputName : undefined
              const consumers = wireName ? (wiring.consumersByOutput[wireName] ?? []) : []
              return (
                <div
                  key={port.name}
                  className="rounded p-2"
                  style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
                >
                  <div className="flex items-center gap-2" style={{ fontSize: 11 }}>
                    <span className="num" style={{ color: 'var(--success)' }}>{port.name}</span>
                    <span className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 9 }}>{port.type}</span>
                    {isDataframe && wireName && (
                      <>
                        <ArrowRight size={11} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
                        <span
                          className="num rounded px-1.5"
                          style={{
                            color: 'var(--text-0)',
                            background: 'color-mix(in srgb, var(--success) 12%, transparent)',
                            border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)',
                          }}
                        >
                          {wireName}
                        </span>
                      </>
                    )}
                  </div>
                  <p className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {port.description}
                  </p>
                  {isDataframe && wireName && (
                    <div className="mt-1.5" style={{ fontSize: 10.5 }}>
                      {consumers.length > 0 ? (
                        <span style={{ color: 'var(--text-2)' }}>
                          consumed by{' '}
                          {consumers.map((c, i) => (
                            <span key={c.id}>
                              {i > 0 && ', '}
                              <span className="num" style={{ color: 'var(--text-0)', fontWeight: 600 }}>
                                {c.id}
                              </span>
                            </span>
                          ))}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-3)' }}>
                          No downstream node consumes this yet
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Main inspector                                                             */
/* -------------------------------------------------------------------------- */
interface ConfigInspectorProps {
  /** Live runtime entry for this node, if the workflow has run. */
  runEntry?: RunLogEntry
  /** Render prop for the last-run preview so we can reuse NodeOutput as-is. */
  renderRunOutput?: (entry: RunLogEntry) => React.ReactNode
}

export default function ConfigInspector({ runEntry, renderRunOutput }: ConfigInspectorProps) {
  const selectedId = useWorkflowStore((s) => s.selectedNodeId)
  const workflow = useWorkflowStore((s) => s.workflow)
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig)
  const renameNode = useWorkflowStore((s) => s.renameNode)

  const node = useMemo(
    () => workflow?.nodes.find((n) => n.id === selectedId) ?? null,
    [workflow, selectedId],
  )

  // Hooks must run unconditionally — never place hooks after `if (!node) return`.
  const fields = useMemo<FieldDescriptor[]>(() => {
    if (!node) return []
    const typed = getNodeTypedSpec(node.type)
    if (typed && typed.params.length > 0) {
      return typed.params.map(paramSpecToFieldDescriptor)
    }
    return []
  }, [node])
  const constraints = useMemo(
    () => (node ? getNodeConstraints(node.type) : []),
    [node],
  )
  const wiring = useMemo((): WiringInfo => {
    if (!node || !workflow) {
      return { upstreamOutputs: [], parents: [], children: [], consumersByOutput: {} }
    }
    return computeWiring(node, workflow.nodes, workflow.edges)
  }, [node, workflow])

  if (!node) {
    return (
      <p className="text-center mt-8" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
        Click a node to inspect its config
      </p>
    )
  }

  const meta = NODE_UI[node.type as NodeType]
  const cfg = (node.config ?? {}) as Record<string, unknown>

  return (
    <div className="space-y-3">
      {/* ----------------- HEADER ----------------- */}
      <div
        className="rounded-lg p-3"
        style={{
          background: 'var(--bg-2)',
          border: meta
            ? `1px solid color-mix(in srgb, ${meta.color} 40%, var(--border))`
            : '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-2.5 mb-1.5">
          {meta && (
            <div
              className="flex items-center justify-center rounded-md"
              style={{
                width: 30, height: 30,
                background: `${meta.color}14`,
                border: `1px solid ${meta.color}40`,
                color: meta.color,
              }}
            >
              <meta.Icon size={16} strokeWidth={2} />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="eyebrow" style={{ color: meta?.color ?? 'var(--text-2)' }}>
              {node.type.replace(/_/g, ' ')}
            </div>
            <input
              type="text"
              value={node.label}
              onChange={(e) => renameNode(node.id, e.target.value)}
              className="w-full"
              style={{
                fontSize: 13.5,
                fontWeight: 500,
                color: 'var(--text-0)',
                background: 'transparent',
                border: 'none',
                outline: 'none',
                padding: 0,
              }}
            />
          </div>
          <span
            className="num rounded px-1.5 py-0.5"
            style={{
              fontSize: 10.5,
              color: 'var(--text-2)',
              background: 'var(--bg-0)',
              border: '1px solid var(--border-soft)',
            }}
          >
            {node.id}
          </span>
        </div>
        <p style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.55 }}>
          {meta?.description ?? ''}
        </p>
      </div>

      {/* ----------------- WIRING ----------------- */}
      <WiringCard node={node} wiring={wiring} />

      {/* ----------------- CONFIG ----------------- */}
      <div>
        <SectionLabel icon={Info}>Configuration</SectionLabel>
        {fields.length === 0 ? (
          <div
            className="rounded p-2"
            style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)', fontSize: 11, color: 'var(--text-2)' }}
          >
            This node has no configurable fields.
          </div>
        ) : (
          <div className="space-y-1.5">
            {fields.map((f) => (
              <FieldRow
                key={f.key}
                field={f}
                value={cfg[f.key]}
                upstreamOutputs={wiring.upstreamOutputs}
                onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
              />
            ))}
          </div>
        )}

        {constraints.length > 0 && (
          <div
            className="mt-2 rounded p-2"
            style={{
              background: 'color-mix(in srgb, var(--warning, #B45309) 8%, transparent)',
              border: '1px solid color-mix(in srgb, var(--warning, #B45309) 30%, transparent)',
            }}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <AlertTriangle size={11} strokeWidth={2.2} style={{ color: 'var(--warning, #B45309)' }} />
              <span className="eyebrow" style={{ color: 'var(--warning, #B45309)', fontSize: 10 }}>
                Constraints
              </span>
            </div>
            <ul className="space-y-0.5" style={{ fontSize: 10.5, color: 'var(--text-1)', lineHeight: 1.5 }}>
              {constraints.map((c, i) => (
                <li key={i}>· {c}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Raw JSON escape hatch — collapsed by default. Handy for Copilot
            debugging and for exotic keys not in the schema. */}
        <details className="mt-2">
          <summary
            className="cursor-pointer"
            style={{ fontSize: 10.5, color: 'var(--text-3)', userSelect: 'none' }}
          >
            raw config JSON
          </summary>
          <pre
            className="num mt-1 p-2 rounded overflow-x-auto"
            style={{
              fontSize: 10.5,
              color: 'var(--text-1)',
              background: 'var(--bg-0)',
              border: '1px solid var(--border)',
              maxHeight: 220,
            }}
          >
            {JSON.stringify(node.config ?? {}, null, 2)}
          </pre>
        </details>
      </div>

      {/* ----------------- LAST RUN ----------------- */}
      <div>
        <SectionLabel icon={Eye}>Last run output</SectionLabel>
        {!runEntry ? (
          <div
            className="rounded p-2"
            style={{
              background: 'var(--bg-0)',
              border: '1px solid var(--border-soft)',
              fontSize: 11,
              color: 'var(--text-2)',
            }}
          >
            Run the workflow to see this node's live output.
          </div>
        ) : (
          <div
            className="rounded-lg p-2.5"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-2 mb-1" style={{ fontSize: 11 }}>
              <span
                className="num rounded px-1.5"
                style={{
                  color:
                    runEntry.status === 'ok' ? 'var(--success)' :
                    runEntry.status === 'running' ? 'var(--running)' :
                    'var(--danger)',
                  background: 'var(--bg-0)',
                  border: '1px solid var(--border-soft)',
                  fontSize: 10.5,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}
              >
                {runEntry.status}
              </span>
              {runEntry.duration_ms != null && (
                <span className="num" style={{ color: 'var(--text-2)' }}>
                  {runEntry.duration_ms < 1000
                    ? `${Math.round(runEntry.duration_ms)} ms`
                    : `${(runEntry.duration_ms / 1000).toFixed(2)} s`}
                </span>
              )}
            </div>
            {renderRunOutput ? renderRunOutput(runEntry) : null}
          </div>
        )}
      </div>
    </div>
  )
}
