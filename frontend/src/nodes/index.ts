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
  type NodeType,
  type NodeUIMeta,
  type NodeContract,
} from './generated'

export { NODE_UI, NODE_TYPES, NODE_CONTRACTS }
export type { NodeType, NodeUIMeta, NodeContract }

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

/** Safe contract lookup — returns an empty contract for unknown node types. */
export function getNodeContract(type: string): NodeContract {
  return (NODE_CONTRACTS as Record<string, NodeContract>)[type] ?? EMPTY_CONTRACT
}
