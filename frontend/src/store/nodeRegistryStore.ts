/**
 * Live node catalogue for Studio.
 *
 * This store owns the palette list, node colors/icons, contracts, and typed
 * params used by config forms. Cold start is seeded from `nodes/generated.ts`
 * so the UI can render before the backend responds. `refreshFromBackend()`
 * then replaces the whole registry from `GET /node-manifest`, normalizing the
 * backend's snake_case NodeSpec payload into the camelCase shape components use.
 *
 * If the refresh fails, we keep the last successful registry (or generated
 * fallback) and expose `error`; the app stays usable with stale specs.
 */
import { create } from 'zustand'
import type { LucideIcon } from 'lucide-react'
import {
  NODE_CONTRACTS,
  NODE_TYPED,
  NODE_TYPES,
  NODE_UI,
  PALETTE_SECTIONS,
  type NodeContract,
  type NodeTypedSpec,
  type NodeUIMeta,
  type PaletteSection,
} from '../nodes/generated'
import { resolveLucideIcon } from '../nodes/lucideIconMap'

const BASE = '/api'

interface NodeManifestNode {
  type_id: string
  description: string
  color: string
  icon: string
  config_tags?: string[]
  palette_group: string
  palette_order: number
  display_name?: string
  input_ports?: NodeTypedSpec['inputPorts']
  output_ports?: NodeTypedSpec['outputPorts']
  params?: NodeTypedSpec['params']
  contract: {
    description: string
    inputs: Record<string, string>
    outputs: Record<string, string>
    config_schema: Record<string, string>
    constraints: string[]
  }
}

interface NodeManifestPayload {
  version: number
  palette_sections: PaletteSection[]
  nodes: NodeManifestNode[]
}

export const UNKNOWN_NODE_UI: NodeUIMeta = {
  color: '#6B7280',
  Icon: resolveLucideIcon(undefined),
  description: '',
  configTags: [],
  paletteGroup: 'unknown',
  paletteOrder: 9999,
}

type RegistryRecord<T> = Record<string, T>

function staticNodeUI(): RegistryRecord<NodeUIMeta> {
  return { ...(NODE_UI as RegistryRecord<NodeUIMeta>) }
}

function staticNodeContracts(): RegistryRecord<NodeContract> {
  return { ...(NODE_CONTRACTS as RegistryRecord<NodeContract>) }
}

function staticNodeTyped(): RegistryRecord<NodeTypedSpec> {
  return { ...(NODE_TYPED as RegistryRecord<NodeTypedSpec>) }
}

function normalizeContract(raw: NodeManifestNode['contract']): NodeContract {
  return {
    description: raw.description,
    inputs: raw.inputs ?? {},
    outputs: raw.outputs ?? {},
    configSchema: raw.config_schema ?? {},
    constraints: raw.constraints ?? [],
  }
}

function normalizeTyped(n: NodeManifestNode): NodeTypedSpec {
  return {
    inputPorts: n.input_ports ?? [],
    outputPorts: n.output_ports ?? [],
    params: n.params ?? [],
  }
}

function normalizeUI(n: NodeManifestNode): NodeUIMeta {
  return {
    color: n.color,
    Icon: resolveLucideIcon(n.icon) as LucideIcon,
    description: n.description,
    configTags: n.config_tags ?? [],
    paletteGroup: n.palette_group,
    paletteOrder: n.palette_order,
    displayName: n.display_name,
  }
}

async function fetchNodeManifest(): Promise<NodeManifestPayload> {
  const res = await fetch(`${BASE}/node-manifest`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : `Node manifest failed (${res.status})`)
  }
  return res.json()
}

interface NodeRegistryState {
  nodeTypes: string[]
  nodeUI: RegistryRecord<NodeUIMeta>
  nodeContracts: RegistryRecord<NodeContract>
  nodeTyped: RegistryRecord<NodeTypedSpec>
  paletteSections: PaletteSection[]
  loading: boolean
  error: string | null
  lastLoadedAt: number | null
  refreshFromBackend: () => Promise<void>
}

export const useNodeRegistryStore = create<NodeRegistryState>((set) => ({
  nodeTypes: [...NODE_TYPES],
  nodeUI: staticNodeUI(),
  nodeContracts: staticNodeContracts(),
  nodeTyped: staticNodeTyped(),
  paletteSections: [...PALETTE_SECTIONS],
  loading: false,
  error: null,
  lastLoadedAt: null,
  refreshFromBackend: async () => {
    set({ loading: true, error: null })
    try {
      const manifest = await fetchNodeManifest()
      const nodeUI: RegistryRecord<NodeUIMeta> = {}
      const nodeContracts: RegistryRecord<NodeContract> = {}
      const nodeTyped: RegistryRecord<NodeTypedSpec> = {}
      const nodeTypes: string[] = []

      for (const n of manifest.nodes) {
        nodeTypes.push(n.type_id)
        nodeUI[n.type_id] = normalizeUI(n)
        nodeContracts[n.type_id] = normalizeContract(n.contract)
        nodeTyped[n.type_id] = normalizeTyped(n)
      }

      set({
        nodeTypes,
        nodeUI,
        nodeContracts,
        nodeTyped,
        paletteSections: manifest.palette_sections,
        loading: false,
        error: null,
        lastLoadedAt: Date.now(),
      })
    } catch (e) {
      set({ loading: false, error: (e as Error).message })
    }
  },
}))
