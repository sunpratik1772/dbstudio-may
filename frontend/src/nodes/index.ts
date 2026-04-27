/**
 * Frontend node registry — the only place outside of `generated.ts` that
 * the app imports when it needs node metadata.
 *
 * Runtime source of truth:
 *   backend/engine/registry.py  ── GET /node-manifest ──▶ nodeRegistryStore
 *
 * `generated.ts` is only the cold-start fallback before the backend refresh
 * returns, or when the backend is unavailable.
 */
import {
  NODE_UI,
  NODE_TYPES,
  NODE_CONTRACTS,
  PALETTE_SECTIONS,
  type NodeUIMeta,
  type NodeContract,
  type PaletteSection,
  type NodeTypedSpec,
} from './generated'
import { UNKNOWN_NODE_UI, useNodeRegistryStore } from '../store/nodeRegistryStore'

export { NODE_UI, NODE_TYPES, NODE_CONTRACTS, PALETTE_SECTIONS }
export { UNKNOWN_NODE_UI, useNodeRegistryStore }
export type NodeType = string
export type { NodeUIMeta, NodeContract, PaletteSection, NodeTypedSpec }

/** Legacy alias — existing components still import `NodeMeta` and `NODE_META`. */
export type NodeMeta = NodeUIMeta
export const NODE_META: Record<string, NodeUIMeta> = NODE_UI

function _titleCaseFromType(type: string): string {
  return type
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Human-facing label — `ui.display_name` from NodeSpec when set, else title-cased type_id. */
export function getNodeDisplayName(type: string): string {
  const meta = useNodeRegistryStore.getState().nodeUI[type]
  if (meta?.displayName) return meta.displayName
  return _titleCaseFromType(type)
}

/** Safe lookup that never throws — returns a neutral placeholder instead. */
export function getNodeMeta(type: string): NodeUIMeta {
  return useNodeRegistryStore.getState().nodeUI[type] ?? UNKNOWN_NODE_UI
}

const EMPTY_CONTRACT: NodeContract = {
  description: '',
  inputs: {},
  outputs: {},
  configSchema: {},
  constraints: [],
}

/** Safe contract lookup — returns an empty contract for unknown node types. */
export function getNodeContract(type: string): NodeContract {
  return useNodeRegistryStore.getState().nodeContracts[type] ?? EMPTY_CONTRACT
}
