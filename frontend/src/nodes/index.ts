/**
 * Frontend node registry — the only place outside of `generated.ts` that
 * the app imports when it needs node metadata.
 *
 * If you're wondering where the icons/colors/types come from:
 *   backend/engine/registry.py  ── (run gen_artifacts.py) ──▶  generated.ts
 */
import { HelpCircle } from 'lucide-react'
import {
  NODE_UI,
  NODE_TYPES,
  NODE_CONTRACTS,
  NODE_TYPED,
  type NodeType,
  type NodeUIMeta,
  type NodeContract,
  type NodeTypedSpec,
  type NodeParamSpec,
  type NodePortSpec,
} from './generated'

export { NODE_UI, NODE_TYPES, NODE_CONTRACTS, NODE_TYPED }
export type { NodeType, NodeUIMeta, NodeContract, NodeTypedSpec, NodeParamSpec, NodePortSpec }

/** Structured ports + params from backend YAML (``gen_artifacts``). Returns null for unknown types. */
export function getNodeTypedSpec(type: string): NodeTypedSpec | null {
  return (NODE_TYPED as Record<string, NodeTypedSpec>)[type] ?? null
}

/** Legacy alias — existing components still import `NodeMeta` and `NODE_META`. */
export type NodeMeta = NodeUIMeta
export const NODE_META: Record<NodeType, NodeUIMeta> = NODE_UI

/** Safe lookup that never throws — returns a neutral placeholder instead. */
export function getNodeMeta(type: string): NodeUIMeta {
  return (NODE_UI as Record<string, NodeUIMeta>)[type] ?? {
    color: '#6B7280',
    Icon: HelpCircle,
    description: '',
    configTags: [],
  }
}

const EMPTY_CONTRACT: NodeContract = {
  description: '',
  inputs: {},
  outputs: {},
  configSchema: {},
  constraints: [],
}

/** Full generated contract (copilot / tools). Prefer NODE_TYPED + NODE_UI in the app shell. */
export function getNodeContract(type: string): NodeContract {
  return (NODE_CONTRACTS as Record<string, NodeContract>)[type] ?? EMPTY_CONTRACT
}

/** Constraint bullets from the backend contract — the only part of `NodeContract` the canvas needs. */
export function getNodeConstraints(type: string): readonly string[] {
  return getNodeContract(type).constraints
}
