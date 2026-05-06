/**
 * Right-panel inspector for the selected node (`rightPanelMode === 'config'`).
 *
 * It renders wiring, editable config fields, and node documentation from the
 * live NodeSpec registry. `classifyField` is the legacy fallback for
 * `contract.configSchema`; typed params from `/node-manifest` should be the
 * preferred path as the backend specs mature.
 */
import { useMemo, useState } from 'react'
import { Settings2, ChevronDown, ChevronRight, ArrowRight, ArrowLeftRight, Sliders, Eye } from 'lucide-react'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType, type NodeContract, type NodeTypedSpec } from '../../nodes'

const EMPTY_CONFIG_CONTRACT: NodeContract = {
  description: '',
  inputs: {},
  outputs: {},
  configSchema: {},
  constraints: [],
}
import type { WorkflowNode, WorkflowEdge } from '../../types'
import Shell, { Empty, SectionHeader } from './Shell'

/* -------------------------------------------------------------------------- */
/* Field inference — legacy fallback for older string-only contracts.         */
/* -------------------------------------------------------------------------- */
type FieldKind = 'input-ref' | 'output-name' | 'boolean' | 'number' | 'string' | 'textarea' | 'stringEnum' | 'stringArray' | 'json'

interface FieldDescriptor {
  key: string
  hint: string
  kind: FieldKind
  enumValues?: readonly string[]
}

type ParamSpec = NodeTypedSpec['params'][number]

function classifyField(key: string, hint: string): FieldDescriptor {
  const h = hint.toLowerCase()
  if (key === 'input_name' || key.endsWith('_input_name') || key === 'input') return { key, hint, kind: 'input-ref' }
  if (key === 'output_name' || key.endsWith('_output_name')) return { key, hint, kind: 'output-name' }
  if (key === 'system_prompt' || key === 'prompt_template' || key === 'llm_prompt_template') return { key, hint, kind: 'textarea' }
  if (h.startsWith('boolean')) return { key, hint, kind: 'boolean' }
  if (h.startsWith('number') || h.startsWith('integer') || h.startsWith('int')) return { key, hint, kind: 'number' }
  if (h.startsWith('array of strings') || h.startsWith('list of strings') || h.startsWith('list[str]')) return { key, hint, kind: 'stringArray' }
  if (h.startsWith('object') || h.startsWith('array') || h.startsWith('list')) return { key, hint, kind: 'json' }
  const enums = Array.from(hint.matchAll(/'([^']+)'/g)).map((m) => m[1])
  if (h.startsWith('string') && enums.length >= 2) return { key, hint, kind: 'stringEnum', enumValues: enums }
  return { key, hint, kind: 'string' }
}

function fieldFromParam(param: ParamSpec): FieldDescriptor {
  const key = param.name
  const hint = param.description
  if (param.widget === 'input_ref' || param.type === 'input_ref') return { key, hint, kind: 'input-ref' }
  if (key === 'output_name' || key.endsWith('_output_name')) return { key, hint, kind: 'output-name' }
  if (param.widget === 'checkbox' || param.type === 'boolean') return { key, hint, kind: 'boolean' }
  if (param.widget === 'number' || param.type === 'number' || param.type === 'integer') return { key, hint, kind: 'number' }
  if (param.widget === 'select' || param.type === 'enum') return { key, hint, kind: 'stringEnum', enumValues: param.enum ?? [] }
  if (param.widget === 'chips' || param.type === 'string_list') return { key, hint, kind: 'stringArray' }
  if (param.widget === 'textarea' || param.widget === 'code' || param.type === 'code') return { key, hint, kind: 'textarea' }
  if (param.widget === 'json' || param.type === 'object' || param.type === 'array') return { key, hint, kind: 'json' }
  return { key, hint, kind: 'string' }
}

interface UpstreamOutput { producerId: string; producerType: string; name: string }

function computeUpstream(node: WorkflowNode, nodes: WorkflowNode[], edges: WorkflowEdge[]): UpstreamOutput[] {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const seen = new Set<string>()
  const order: string[] = []
  const queue = edges.filter((e) => e.to === node.id).map((e) => e.from)
  while (queue.length) {
    const id = queue.shift()!
    if (seen.has(id)) continue
    seen.add(id)
    order.push(id)
    for (const e of edges) if (e.to === id && !seen.has(e.from)) queue.push(e.from)
  }
  const out: UpstreamOutput[] = []
  for (const id of order) {
    const n = byId.get(id)
    if (!n) continue
    const name = (n.config as Record<string, unknown>)?.output_name
    if (typeof name === 'string' && name.trim()) {
      out.push({ producerId: n.id, producerType: n.type, name })
    }
  }
  return out
}

/* -------------------------------------------------------------------------- */
/* Group — collapsible labelled section inside the Config view.               */
/* -------------------------------------------------------------------------- */
function Group({
  title, count, defaultOpen = true, children,
}: { title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ borderBottom: '1px solid var(--border-soft)' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left"
        style={{ background: 'transparent', cursor: 'pointer' }}
      >
        {open ? <ChevronDown size={12} style={{ color: 'var(--text-3)' }} /> : <ChevronRight size={12} style={{ color: 'var(--text-3)' }} />}
        <span
          className="font-mono"
          style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-2)' }}
        >
          {title}
        </span>
        {count != null && (
          <span className="num" style={{ fontSize: 10, color: 'var(--text-3)' }}>
            {count}
          </span>
        )}
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Port row — uniform layout for both inputs (←) and outputs (→).             */
/* -------------------------------------------------------------------------- */
function PortRow({
  name, dir, hint, wireName, wireColor,
}: {
  name: string
  dir: 'in' | 'out'
  hint: string
  wireName?: string | null
  wireColor: string
}) {
  return (
    <div
      className="rounded-md p-2 mb-1.5"
      style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
    >
      <div className="flex items-center gap-1.5" style={{ fontSize: 11 }}>
        <span style={{ color: 'var(--text-3)' }}>{dir === 'in' ? '←' : '→'}</span>
        <span className="num" style={{ color: 'var(--text-1)', fontWeight: 500 }}>{name}</span>
        {wireName && (
          <>
            <ArrowRight size={10} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
            <span
              className="num"
              style={{
                fontSize: 10.5, padding: '1px 6px', borderRadius: 4,
                color: 'var(--text-0)',
                background: `color-mix(in srgb, ${wireColor} 12%, transparent)`,
                border: `1px solid color-mix(in srgb, ${wireColor} 30%, transparent)`,
              }}
            >
              {wireName}
            </span>
          </>
        )}
      </div>
      {hint && (
        <div className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {hint}
        </div>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Param row — label + control + hint.                                        */
/* -------------------------------------------------------------------------- */
const inputStyle: React.CSSProperties = {
  width: '100%',
  fontSize: 11.5,
  color: 'var(--text-0)',
  background: 'var(--bg-0)',
  border: '1px solid var(--border)',
  borderRadius: 7,
  padding: '6px 8px',
  fontFamily: 'var(--font-mono, ui-monospace, monospace)',
}

function ParamRow({
  field, value, upstream, onChange,
}: {
  field: FieldDescriptor
  value: unknown
  upstream: UpstreamOutput[]
  onChange: (v: unknown) => void
}) {
  return (
    <div className="mb-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="num" style={{ fontSize: 10.5, color: 'var(--text-1)', fontWeight: 600, letterSpacing: 0 }}>
          {field.key}
        </span>
        <span
          className="font-mono"
          style={{ fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-3)' }}
        >
          {field.kind === 'input-ref' ? 'wire' : field.kind}
        </span>
      </div>
      <ParamInput field={field} value={value} upstream={upstream} onChange={onChange} />
      {field.hint && (
        <p className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>{field.hint}</p>
      )}
    </div>
  )
}

function ParamInput({ field, value, upstream, onChange }: {
  field: FieldDescriptor
  value: unknown
  upstream: UpstreamOutput[]
  onChange: (v: unknown) => void
}) {
  if (field.kind === 'input-ref') {
    const current = typeof value === 'string' ? value : ''
    return (
      <div className="space-y-1.5">
        {upstream.length > 0 ? (
          <select
            value={upstream.some((u) => u.name === current) ? current : ''}
            onChange={(e) => onChange(e.target.value || null)}
            style={inputStyle}
          >
            <option value="">— upstream output —</option>
            {upstream.map((u) => (
              <option key={`${u.producerId}:${u.name}`} value={u.name}>
                {u.name} · {u.producerId}
              </option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          value={current}
          onChange={(e) => onChange(e.target.value)}
          placeholder="dataset name…"
          style={{ ...inputStyle, fontSize: 11 }}
        />
      </div>
    )
  }
  if (field.kind === 'boolean') {
    return (
      <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 11.5, color: 'var(--text-1)' }}>
        <input type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked)} style={{ width: 14, height: 14 }} />
        <span>{value === true ? 'true' : 'false'}</span>
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
    return (
      <select value={typeof value === 'string' ? value : ''} onChange={(e) => onChange(e.target.value || null)} style={inputStyle}>
        <option value="">— choose —</option>
        {field.enumValues.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>
    )
  }
  if (field.kind === 'stringArray') {
    const arr = Array.isArray(value) ? value : []
    return (
      <input
        type="text"
        value={arr.join(', ')}
        onChange={(e) => onChange(e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
        placeholder="comma-separated"
        style={inputStyle}
      />
    )
  }
  if (field.kind === 'textarea') {
    return (
      <textarea
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => onChange(e.target.value)}
        rows={Math.min(14, Math.max(5, String(value ?? '').split('\n').length))}
        spellCheck={false}
        style={{ ...inputStyle, resize: 'vertical', minHeight: 120, lineHeight: 1.5 }}
      />
    )
  }
  if (field.kind === 'output-name' || field.kind === 'string') {
    return (
      <input
        type="text"
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    )
  }
  // JSON fallback
  const text = value === undefined ? '' : JSON.stringify(value, null, 2)
  return (
    <textarea
      value={text}
      onChange={(e) => {
        const v = e.target.value.trim()
        if (v === '') { onChange(null); return }
        try { onChange(JSON.parse(v)) } catch { /* ignore until valid */ }
      }}
      rows={Math.min(8, Math.max(3, text.split('\n').length))}
      spellCheck={false}
      style={{ ...inputStyle, resize: 'vertical', minHeight: 60 }}
    />
  )
}

/* -------------------------------------------------------------------------- */
/* Main view                                                                  */
/* -------------------------------------------------------------------------- */
export default function ConfigView() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const selectedId = useWorkflowStore((s) => s.selectedNodeId)
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig)
  const renameNode = useWorkflowStore((s) => s.renameNode)
  const runLog = useWorkflowStore((s) => s.runLog)

  const node = useMemo(
    () => workflow?.nodes.find((n) => n.id === selectedId) ?? null,
    [workflow, selectedId],
  )

  const meta = useNodeRegistryStore((s) =>
    node ? (s.nodeUI[node.type as NodeType] ?? UNKNOWN_NODE_UI) : UNKNOWN_NODE_UI,
  )
  const contract = useNodeRegistryStore((s) =>
    node ? (s.nodeContracts[node.type as NodeType] ?? EMPTY_CONFIG_CONTRACT) : EMPTY_CONFIG_CONTRACT,
  )
  const typedSpec = useNodeRegistryStore((s) =>
    node ? s.nodeTyped[node.type as NodeType] : undefined,
  )

  if (!node) {
    return (
      <Shell icon={Settings2} title="Inspector" eyebrow="CONFIG" accent="var(--text-1)">
        <Empty>
          <Settings2 size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
          <div style={{ color: 'var(--text-1)', fontWeight: 500, marginBottom: 4 }}>No node selected</div>
          <div>Click a node on the canvas to edit its config.</div>
        </Empty>
      </Shell>
    )
  }
  const upstream = workflow ? computeUpstream(node, workflow.nodes, workflow.edges) : []
  const fields = typedSpec?.params.length
    ? typedSpec.params.map(fieldFromParam)
    : Object.entries(contract.configSchema).map(([k, v]) => classifyField(k, v))
  const cfg = (node.config ?? {}) as Record<string, unknown>
  const promptFields = fields.filter((f) => f.key === 'system_prompt' || f.key === 'prompt_template' || f.key === 'llm_prompt_template')
  const llmSettingFields = fields.filter((f) => ['use_llm', 'model', 'temperature', 'max_output_tokens'].includes(f.key))
  const specialFieldKeys = new Set([...promptFields, ...llmSettingFields].map((f) => f.key))
  const nonPromptFields = fields.filter((f) => !specialFieldKeys.has(f.key))
  const inputName = typeof cfg.input_name === 'string' ? cfg.input_name : null
  const outputName = typeof cfg.output_name === 'string' ? cfg.output_name : null
  const inputs = Object.entries(contract.inputs)
  const outputs = Object.entries(contract.outputs)

  const lastRun = [...runLog].reverse().find((e) => e.node_id === node.id)
  const accent = meta?.color ?? 'var(--text-1)'

  const subtitle = (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className="num rounded px-1.5"
        style={{
          fontSize: 10.5, color: 'var(--text-1)',
          background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
        }}
      >
        {node.id}
      </span>
      <span style={{ color: 'var(--text-3)' }}>·</span>
      <span className="font-mono" style={{ fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: accent }}>
        {node.type.replace(/_/g, ' ')}
      </span>
    </div>
  )

  return (
    <Shell
      icon={meta?.Icon ?? Settings2}
      title={node.label}
      eyebrow="CONFIG"
      accent={accent}
      subtitle={subtitle}
    >
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
        <SectionHeader>Description</SectionHeader>
        <p style={{ fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.55 }}>
          {contract.description || meta?.description || '—'}
        </p>
        <input
          type="text"
          value={node.label}
          onChange={(e) => renameNode(node.id, e.target.value)}
          placeholder="Label"
          className="mt-2"
          style={inputStyle}
        />
      </div>

      <Group title="Ports" count={inputs.length + outputs.length}>
        <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <ArrowLeftRight size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Inputs</span>
        </div>
        {inputs.length === 0
          ? <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>None</div>
          : inputs.map(([k, v]) => (
              <PortRow
                key={k}
                name={k}
                dir="in"
                hint={v}
                wireName={k.startsWith('datasets[') ? inputName : null}
                wireColor="var(--info)"
              />
            ))}
        <div className="flex items-center gap-1.5 mb-2 mt-3" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <ArrowLeftRight size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Outputs</span>
        </div>
        {outputs.length === 0
          ? <div style={{ fontSize: 11, color: 'var(--text-3)' }}>None</div>
          : outputs.map(([k, v]) => (
              <PortRow
                key={k}
                name={k}
                dir="out"
                hint={v}
                wireName={k.startsWith('datasets[') ? outputName : null}
                wireColor="var(--success)"
              />
            ))}
      </Group>

      {promptFields.length > 0 && (
        <Group title="Prompts" count={promptFields.length}>
          <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            Copilot writes these per-node prompt templates. Runtime values such as
            <span className="num" style={{ color: 'var(--text-1)' }}> {'{context.trader_id}'} </span>
            are filled when the node executes.
          </div>
          {promptFields.map((f) => (
            <ParamRow
              key={f.key}
              field={f}
              value={cfg[f.key]}
              upstream={upstream}
              onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
            />
          ))}
        </Group>
      )}

      {llmSettingFields.length > 0 && (
        <Group title="LLM Settings" count={llmSettingFields.length}>
          <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            Gemini runtime controls for this node. `temperature` controls response variability.
          </div>
          {llmSettingFields.map((f) => (
            <ParamRow
              key={f.key}
              field={f}
              value={cfg[f.key]}
              upstream={upstream}
              onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
            />
          ))}
        </Group>
      )}

      <Group title="Params" count={nonPromptFields.length}>
        {nonPromptFields.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No configurable fields.</div>
        ) : (
          <>
            <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
              <Sliders size={11} />
              <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Editable</span>
            </div>
            {nonPromptFields.map((f) => (
              <ParamRow
                key={f.key}
                field={f}
                value={cfg[f.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
              />
            ))}
          </>
        )}
      </Group>

      <Group title="Last Run" defaultOpen={!!lastRun}>
        <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <Eye size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Output</span>
        </div>
        {!lastRun ? (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Run the workflow to see live output.</div>
        ) : lastRun.error ? (
          <div
            className="p-2 rounded"
            style={{
              fontSize: 11, color: 'var(--danger)', lineHeight: 1.5,
              background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
            }}
          >
            {lastRun.error}
          </div>
        ) : lastRun.output ? (
          <pre
            className="num p-2 rounded overflow-x-auto"
            style={{
              fontSize: 10, color: 'var(--text-1)', maxHeight: 200,
              background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
            }}
          >
            {JSON.stringify(lastRun.output, null, 2)}
          </pre>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No output recorded.</div>
        )}
      </Group>

      {contract.constraints.length > 0 && (
        <Group title="Constraints" count={contract.constraints.length} defaultOpen={false}>
          <ul className="space-y-1" style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.5 }}>
            {contract.constraints.map((c, i) => <li key={i}>· {c}</li>)}
          </ul>
        </Group>
      )}
    </Shell>
  )
}
