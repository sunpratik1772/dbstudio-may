/**
 * AUTO-GENERATED — do not edit by hand.
 * Run `python backend/scripts/gen_artifacts.py` to regenerate.
 * Source: backend/engine/registry.py
 */
import type { LucideIcon } from 'lucide-react'
import {
  ArrowLeftRight,
  CandlestickChart,
  Clock,
  Crosshair,
  Database,
  FileSpreadsheet,
  FileStack,
  Gavel,
  Highlighter,
  ListFilter,
  MessageSquareText,
  NotebookText,
  Repeat,
  Signal,
  Siren,
  SlidersHorizontal,
  Split,
} from 'lucide-react'

export type NodeType =
  | 'ACTION_VALIDATOR'
  | 'AGGREGATOR_NODE'
  | 'ALERT_TRIGGER'
  | 'COMMS_COLLECTOR'
  | 'CONSOLIDATED_SUMMARY'
  | 'DATA_HIGHLIGHTER'
  | 'DATA_REDUCER'
  | 'DECISION_RULE'
  | 'ERROR_HANDLER'
  | 'EXECUTION_DATA_COLLECTOR'
  | 'EXTRACT_LIST'
  | 'EXTRACT_SCALAR'
  | 'FEATURE_ENGINE'
  | 'GROUP_BY'
  | 'GUARDRAIL'
  | 'LLM_ACTION'
  | 'LLM_CONTEXTUALIZER'
  | 'LLM_CRITIC'
  | 'LLM_EVALUATOR'
  | 'LLM_PLANNER'
  | 'LLM_SYNTHESIZER'
  | 'LOOP_CONTROLLER'
  | 'MAP'
  | 'MARKET_DATA_COLLECTOR'
  | 'ORACLE_DATA_COLLECTOR'
  | 'PLAN_VALIDATOR'
  | 'REPORT_OUTPUT'
  | 'SECTION_SUMMARY'
  | 'SIGNAL_CALCULATOR'
  | 'STATE_MANAGER'
  | 'TIME_WINDOW'
  | 'TOOL_EXECUTOR'

export interface NodeUIMeta {
  color: string
  Icon: LucideIcon
  description: string
  /** Config keys whose values are rendered as chips on the node card. */
  configTags: readonly string[]
  /** Palette group id — must match PaletteSection.id */
  paletteGroup: string
  /** Sort key within the palette group (lower first). */
  paletteOrder: number
  /** Short card title; when omitted, UI title-cases type_id. */
  displayName?: string
}

export interface PaletteSection {
  id: string
  label: string
  order: number
  color: string
}

export const PALETTE_SECTIONS: readonly PaletteSection[] = [
  {
    "id": "trigger",
    "label": "Trigger",
    "order": 0,
    "color": "#F5A623"
  },
  {
    "id": "integrations",
    "label": "Integrations",
    "order": 10,
    "color": "#00E5FF"
  },
  {
    "id": "transform",
    "label": "Transform",
    "order": 20,
    "color": "#A78BFA"
  },
  {
    "id": "agent",
    "label": "Agent Layer",
    "order": 25,
    "color": "#7C3AED"
  },
  {
    "id": "signal",
    "label": "Signal",
    "order": 30,
    "color": "#F472B6"
  },
  {
    "id": "rule",
    "label": "Rule",
    "order": 40,
    "color": "#FBBF24"
  },
  {
    "id": "narrative",
    "label": "Narrative",
    "order": 50,
    "color": "#F472B6"
  },
  {
    "id": "output",
    "label": "Output",
    "order": 60,
    "color": "#10B981"
  }
] as const

export const NODE_UI: Record<NodeType, NodeUIMeta> = {
  ACTION_VALIDATOR: {
    color: '#7C3AED',
    Icon: Gavel,
    description: "Validate LLM-selected tool and args before execution",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 40,
    displayName: "Action Validator",
  },
  AGGREGATOR_NODE: {
    color: '#7C3AED',
    Icon: FileStack,
    description: "Merge selected values and optionally concatenate datasets",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 130,
    displayName: "Aggregator Node",
  },
  ALERT_TRIGGER: {
    color: '#7C3AED',
    Icon: Siren,
    description: "Entry point \u2014 binds alert payload to context",
    configTags: [] as const,
    paletteGroup: "trigger",
    paletteOrder: 0,
  },
  COMMS_COLLECTOR: {
    color: '#059669',
    Icon: MessageSquareText,
    description: "Query Oculus comms with keyword scanning",
    configTags: ['output_name'] as const,
    paletteGroup: "integrations",
    paletteOrder: 10,
    displayName: "Oculus",
  },
  CONSOLIDATED_SUMMARY: {
    color: '#B45309',
    Icon: FileStack,
    description: "LLM executive summary across all sections",
    configTags: [] as const,
    paletteGroup: "narrative",
    paletteOrder: 51,
  },
  DATA_HIGHLIGHTER: {
    color: '#9333EA',
    Icon: Highlighter,
    description: "Apply colour rules to dataset rows",
    configTags: ['output_name'] as const,
    paletteGroup: "transform",
    paletteOrder: 21,
  },
  DATA_REDUCER: {
    color: '#7C3AED',
    Icon: ListFilter,
    description: "Reduce a dataset to a bounded preview and summary for downstream LLM nodes",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 140,
    displayName: "Data Reducer",
  },
  DECISION_RULE: {
    color: '#D97706',
    Icon: Gavel,
    description: "Evaluate flag_count or rules \u2192 ESCALATE/REVIEW/DISMISS + severity",
    configTags: [] as const,
    paletteGroup: "rule",
    paletteOrder: 40,
  },
  ERROR_HANDLER: {
    color: '#7C3AED',
    Icon: Gavel,
    description: "Classify failures and select retry, fallback, abort, or continue strategy",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 150,
    displayName: "Error Handler",
  },
  EXECUTION_DATA_COLLECTOR: {
    color: '#2563EB',
    Icon: ArrowLeftRight,
    description: "Query Solr for client orders, executions, trades, and quotes",
    configTags: ['source', 'output_name'] as const,
    paletteGroup: "integrations",
    paletteOrder: 11,
    displayName: "Solr Data Collector",
  },
  EXTRACT_LIST: {
    color: '#8B5CF6',
    Icon: ListFilter,
    description: "Emit the unique values of a column as an ordered list \u2014 cascade primitive for fan-out keys.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 24,
  },
  EXTRACT_SCALAR: {
    color: '#8B5CF6',
    Icon: Crosshair,
    description: "Reduce a column of an upstream DataFrame to a single scalar (first, unique_single, max, min, count, sum, mean).",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 25,
  },
  FEATURE_ENGINE: {
    color: '#0EA5E9',
    Icon: SlidersHorizontal,
    description: "Compose feature transforms (window, slice, pivot, agg, rolling, derive)",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 20,
  },
  GROUP_BY: {
    color: '#7C3AED',
    Icon: Split,
    description: "Split a dataset by column value into one DataFrame per group",
    configTags: ['input_name', 'group_by_column'] as const,
    paletteGroup: "transform",
    paletteOrder: 22,
  },
  GUARDRAIL: {
    color: '#7C3AED',
    Icon: Siren,
    description: "Apply deterministic safety checks to action/result state",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 50,
    displayName: "Guardrail",
  },
  LLM_ACTION: {
    color: '#7C3AED',
    Icon: Crosshair,
    description: "llm.action \u2014 choose the next tool call using critic feedback and retry context",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 30,
    displayName: "llm.action",
  },
  LLM_CONTEXTUALIZER: {
    color: '#7C3AED',
    Icon: MessageSquareText,
    description: "llm.contextualizer \u2014 combine query and retrieved docs into enriched context",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 120,
    displayName: "llm.contextualizer",
  },
  LLM_CRITIC: {
    color: '#7C3AED',
    Icon: Gavel,
    description: "llm.critic \u2014 validate the latest action result and emit actionable feedback",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 70,
    displayName: "llm.critic",
  },
  LLM_EVALUATOR: {
    color: '#7C3AED',
    Icon: Crosshair,
    description: "llm.evaluator \u2014 decide whether the current workflow goal is satisfied",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 90,
    displayName: "llm.evaluator",
  },
  LLM_PLANNER: {
    color: '#7C3AED',
    Icon: NotebookText,
    description: "llm.planner \u2014 create a step plan from goal and context",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 10,
    displayName: "llm.planner",
  },
  LLM_SYNTHESIZER: {
    color: '#7C3AED',
    Icon: NotebookText,
    description: "llm.synthesizer \u2014 produce final output and optional JSON/text artifact",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 110,
    displayName: "llm.synthesizer",
  },
  LOOP_CONTROLLER: {
    color: '#7C3AED',
    Icon: Repeat,
    description: "Compute retry-loop continuation from iteration, done, and confidence state",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 100,
    displayName: "Loop Controller",
  },
  MAP: {
    color: '#DB2777',
    Icon: Repeat,
    description: "Fan out a sub-workflow over a list of keys; aggregate results",
    configTags: ['keys_key', 'output_name'] as const,
    paletteGroup: "transform",
    paletteOrder: 23,
  },
  MARKET_DATA_COLLECTOR: {
    color: '#0891B2',
    Icon: CandlestickChart,
    description: "Query EBS/Mercury tick data, normalise timestamps",
    configTags: ['source', 'output_name'] as const,
    paletteGroup: "integrations",
    paletteOrder: 12,
    displayName: "Mercury",
  },
  ORACLE_DATA_COLLECTOR: {
    color: '#7C3AED',
    Icon: Database,
    description: "Query Oracle surveillance warehouse order/execution extracts",
    configTags: ['source', 'output_name'] as const,
    paletteGroup: "integrations",
    paletteOrder: 13,
  },
  PLAN_VALIDATOR: {
    color: '#7C3AED',
    Icon: Gavel,
    description: "Validate generated plan structure, dependencies, and tool names",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 20,
    displayName: "Plan Validator",
  },
  REPORT_OUTPUT: {
    color: '#047857',
    Icon: FileSpreadsheet,
    description: "Generate Excel report with tabs & highlights",
    configTags: ['output_name'] as const,
    paletteGroup: "output",
    paletteOrder: 60,
  },
  SECTION_SUMMARY: {
    color: '#DB2777',
    Icon: NotebookText,
    description: "Aggregate stats + LLM narrative section",
    configTags: [] as const,
    paletteGroup: "narrative",
    paletteOrder: 50,
  },
  SIGNAL_CALCULATOR: {
    color: '#DC2626',
    Icon: Signal,
    description: "Compute signals \u2014 always outputs 5 columns",
    configTags: ['signal_type', 'output_name'] as const,
    paletteGroup: "signal",
    paletteOrder: 30,
  },
  STATE_MANAGER: {
    color: '#7C3AED',
    Icon: FileStack,
    description: "Track retry history and iteration state",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 80,
    displayName: "State Manager",
  },
  TIME_WINDOW: {
    color: '#F59E0B',
    Icon: Clock,
    description: "Expand an event time into a [start_time, end_time] window for downstream filtering.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 19,
  },
  TOOL_EXECUTOR: {
    color: '#7C3AED',
    Icon: SlidersHorizontal,
    description: "Bridge an LLM action into deterministic built-in or registered node execution",
    configTags: ['output_name'] as const,
    paletteGroup: "agent",
    paletteOrder: 60,
    displayName: "Tool Executor",
  },
}

export const NODE_TYPES: readonly NodeType[] = [
  'ACTION_VALIDATOR',
  'AGGREGATOR_NODE',
  'ALERT_TRIGGER',
  'COMMS_COLLECTOR',
  'CONSOLIDATED_SUMMARY',
  'DATA_HIGHLIGHTER',
  'DATA_REDUCER',
  'DECISION_RULE',
  'ERROR_HANDLER',
  'EXECUTION_DATA_COLLECTOR',
  'EXTRACT_LIST',
  'EXTRACT_SCALAR',
  'FEATURE_ENGINE',
  'GROUP_BY',
  'GUARDRAIL',
  'LLM_ACTION',
  'LLM_CONTEXTUALIZER',
  'LLM_CRITIC',
  'LLM_EVALUATOR',
  'LLM_PLANNER',
  'LLM_SYNTHESIZER',
  'LOOP_CONTROLLER',
  'MAP',
  'MARKET_DATA_COLLECTOR',
  'ORACLE_DATA_COLLECTOR',
  'PLAN_VALIDATOR',
  'REPORT_OUTPUT',
  'SECTION_SUMMARY',
  'SIGNAL_CALCULATOR',
  'STATE_MANAGER',
  'TIME_WINDOW',
  'TOOL_EXECUTOR',
] as const

/** Schema + constraints for a node type, surfaced in the Config inspector. */
export interface NodeContract {
  description: string
  inputs: Record<string, string>
  outputs: Record<string, string>
  configSchema: Record<string, string>
  constraints: readonly string[]
}

export const NODE_CONTRACTS: Record<NodeType, NodeContract> = {
  ACTION_VALIDATOR: {
    description: "Validate LLM-selected tool and args before execution",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  AGGREGATOR_NODE: {
    description: "Merge selected values and optionally concatenate datasets",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  ALERT_TRIGGER: {
    description: "Entry point \u2014 binds alert payload to context",
    inputs: {
          "alert_payload": "JSON object passed at workflow invocation time."
    },
    outputs: {
          "context_keys": "One context key per declared alert_field, e.g. trader_id, book, alert_date, currency_pair, alert_id."
    },
    configSchema: {
          "alert_fields": "Map of field_name \u2192 type (string|date|number). Non-listed payload keys in extras.standard_alert_fields are still bound when present in the alert."
    },
    constraints: ["Must be the first node (id=n01).", "No dataset inputs or outputs."] as const,
  },
  COMMS_COLLECTOR: {
    description: "Query Oculus comms with keyword scanning",
    inputs: {
          "context": "Context keys referenced in query_template as {context.xxx}."
    },
    outputs: {
          "comms": "DataFrame with columns: user, timestamp, display_post, event_type, _keyword_hit, _matched_keywords. Stored under ctx.datasets[output_name].",
          "keyword_hit_count": "Total keyword hit count (int). Stored as {output_name}_keyword_hits."
    },
    configSchema: {
          "query_template": "Oculus query with {context.xxx} placeholders.",
          "keywords": "Terms to scan in display_post.",
          "keyword_categories": "Optional {category: [kw1, kw2, ...]} map. When present, each row gains a _matched_categories list plus one _hit_<cat> boolean column. Combined with plain `keywords` (both are scanned).",
          "emit_hits_only": "Also publish ctx.datasets[f\"{output_name}_hits\"] containing only rows with at least one keyword match. Lets downstream SECTION_SUMMARY narrate just the suspicious subset.",
          "output_name": "Dataset name in ctx.datasets.",
          "mock_csv_path": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing."
    },
    constraints: ["Always adds _keyword_hit (boolean) and _matched_keywords (list[str]) columns.", "Scans display_post field only."] as const,
  },
  CONSOLIDATED_SUMMARY: {
    description: "LLM executive summary across all sections",
    inputs: {
          "sections": "All section objects produced by upstream SECTION_SUMMARY nodes (context.sections)."
    },
    outputs: {
          "executive_summary": "Multi-paragraph executive summary. Stored as context.executive_summary."
    },
    configSchema: {
          "llm_prompt_template": "Custom prompt with {section_text}, {trader_id}, {currency_pair}, {disposition}, {flag_count} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset|mixed) {dataset}. Cross-dataset refs like {executions.notional.sum} resolve inline. Falls back to the built-in template when empty.",
          "system_prompt": "System instruction for the executive-summary LLM. Rendered with {section_text}, alert context, prompt_context vars, and context refs.",
          "prompt_context": "Optional structured slot block: {mode: template|dataset|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. Same shape as SECTION_SUMMARY.prompt_context.",
          "model": "Optional LLM model override.",
          "temperature": "LLM temperature.",
          "max_output_tokens": "Maximum response tokens."
    },
    constraints: ["Default max_output_tokens: 1000.", "Must run after all SECTION_SUMMARY nodes."] as const,
  },
  DATA_HIGHLIGHTER: {
    description: "Apply colour rules to dataset rows",
    inputs: {
          "dataset": "Any DataFrame referenced by input_name."
    },
    outputs: {
          "highlighted": "Input DataFrame + _highlight_colour (hex) + _highlight_label (str). Stored under ctx.datasets[output_name]."
    },
    configSchema: {
          "input_name": "Source dataset.",
          "output_name": "Highlighted dataset name (convention: input_name + '_highlighted').",
          "rules": "Array of {condition, colour, label}. `condition` is a pandas.DataFrame.eval expression evaluated against the target dataset's rows. The condition may include `{ref}` placeholders that resolve to SCALAR values via the cross-dataset ref grammar BEFORE pandas eval \u2014 e.g. `notional > {context.peak_threshold}`, `bucket == {ladder.peak_bucket.first}`. `colour` is hex #RRGGBB."
    },
    constraints: ["Conditions are evaluated with pandas DataFrame.eval after `{ref}` resolution.", "Rules are applied in order \u2014 last matching rule wins.", "Rows with no matching rule get colour #FFFFFF and empty label.", "Buggy rules (unresolved refs, syntax errors, missing columns) are skipped with a warning. The run continues."] as const,
  },
  DATA_REDUCER: {
    description: "Reduce a dataset to a bounded preview and summary for downstream LLM nodes",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "reduced_data": "DataFrame stored in ctx.datasets[output_name]"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  DECISION_RULE: {
    description: "Evaluate flag_count or rules \u2192 ESCALATE/REVIEW/DISMISS + severity",
    inputs: {
          "dataset": "Signal DataFrame with _signal_flag column.",
          "flag_count": "Flag count from SIGNAL_CALCULATOR (read from ctx.values[{input_name}_flag_count] if the dataset isn't available)."
    },
    outputs: {
          "disposition": "'ESCALATE' | 'REVIEW' | 'DISMISS'. Stored as context.disposition.",
          "severity": "'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'. Stored as context.severity.",
          "score": "Normalised severity score in [0, 1]. Stored as context.score.",
          "flag_count": "Total signal hits (int). Stored as context.flag_count.",
          "output_branch": "Branch name to route to. Stored as context.output_branch.",
          "matched_rule": "Name of the rule that fired (rule mode only; empty in threshold mode). Stored as context.matched_rule."
    },
    configSchema: {
          "input_name": "Signal dataset name.",
          "escalate_threshold": "flag_count >= this \u2192 ESCALATE (threshold mode).",
          "review_threshold": "flag_count >= this \u2192 REVIEW (threshold mode).",
          "rules": "Optional rules list, evaluated top-to-bottom; first match wins. Each rule: {name, when, severity?, disposition?}. `when` accepts `{ref}` (truthy test) or `{ref} OP literal` where OP \u2208 {>=,<=,==,!=,>,<}. Refs use the cross-dataset grammar \u2014 e.g. `{executions._signal_flag.sum} >= 10`, `{ladder.symmetry.max} > 0.85`, `{context.book_count} > 1`.",
          "severity_map": "Override severity per disposition. Defaults: {ESCALATE: HIGH, REVIEW: MEDIUM, DISMISS: LOW}.",
          "output_branches": "Map of disposition \u2192 branch_name string."
    },
    constraints: ["Threshold mode (default) requires escalate_threshold >= review_threshold.", "Rule mode short-circuits: first matching rule sets disposition + severity."] as const,
  },
  ERROR_HANDLER: {
    description: "Classify failures and select retry, fallback, abort, or continue strategy",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  EXECUTION_DATA_COLLECTOR: {
    description: "Query Solr for client orders, executions, trades, and quotes",
    inputs: {
          "context": "Context keys referenced in query_template as {context.xxx}",
          "window": "Optional TIME_WINDOW output (start_time, end_time) \u2014 filters rows to the window when window_key is set."
    },
    outputs: {
          "executions": "Order/execution rows. Stored in ctx.datasets under the configured output_name.",
          "row_count": "Integer row count. Stored in ctx.values as {output_name}_count."
    },
    configSchema: {
          "source": "Which Solr collection to query. Values are derived from data_sources/metadata/trades.yaml at runtime.",
          "query_template": "Solr query; use {context.xxx} placeholders for alert fields.",
          "output_name": "Dataset name in ctx.datasets.",
          "window_key": "ctx.values key holding the window dict. Used when a TIME_WINDOW node is wired upstream.",
          "trader_filter_key": "ctx.values key whose value filters trader_id when present. Empty = no trader filter.",
          "loop_over_books": "Repeat the query for each book in the books list.",
          "books": "Book names when loop_over_books=true.",
          "mock_csv_path": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing. CSV columns are not re-checked against the lists below; synthetic rows are."
    },
    constraints: ["When source reads versioned trades/fills, trade_version:1 MUST be hard-coded in query_template \u2014 never from context.", "Output DataFrame will always include trade_version=1 for hs_execution, hs_trades, and hs_orders_and_executions synthetic reads."] as const,
  },
  EXTRACT_LIST: {
    description: "Emit the unique values of a column as an ordered list \u2014 cascade primitive for fan-out keys.",
    inputs: {
          "dataset": "Source DataFrame (by input_name)."
    },
    outputs: {
          "values": "{values: [...]} \u2014 published under ctx.values[output_name]."
    },
    configSchema: {
          "input_name": "Dataset name in ctx.datasets.",
          "column": "Column to enumerate.",
          "output_name": "ctx.values key to publish {values: [...]} under.",
          "order": "sort: ascending, desc: descending, first_seen: original order.",
          "dropna": "Exclude NaN values."
    },
    constraints: ["Typical use: EXTRACT_LIST(executions, 'book') \u2192 fan-out keys for GROUP_BY_BOOK or MAP."] as const,
  },
  EXTRACT_SCALAR: {
    description: "Reduce a column of an upstream DataFrame to a single scalar (first, unique_single, max, min, count, sum, mean).",
    inputs: {
          "dataset": "Source DataFrame (by input_name)."
    },
    outputs: {
          "value": "Published under ctx.values[output_name]."
    },
    configSchema: {
          "input_name": "Dataset name in ctx.datasets.",
          "column": "Column to reduce.",
          "reducer": "How to collapse the column to a single value.",
          "output_name": "ctx.values key to publish the scalar under.",
          "fail_on_ambiguous": "When reducer=unique_single, raise if the column has more than one distinct value (default false \u2014 take the first)."
    },
    constraints: ["Typical use: EXTRACT_SCALAR(orders, 'trader_id', unique_single) \u2192 feeds a downstream collector's trader_filter_key."] as const,
  },
  FEATURE_ENGINE: {
    description: "Compose feature transforms (window, slice, pivot, agg, rolling, derive)",
    inputs: {
          "dataset": "Source DataFrame referenced by input_name."
    },
    outputs: {
          "features": "Final working DataFrame after all chained ops, published as ctx.datasets[output_name]. Ops with an `as` field also publish intermediate datasets under that name."
    },
    configSchema: {
          "input_name": "Source dataset name.",
          "output_name": "Target dataset name (defaults to input_name).",
          "ops": "Ordered list of operations applied to the working DataFrame. Each op is {op: <name>, ...op-specific keys, as?: <publish_name>}. Supported ops:\n\u2022 window_bucket {time_col, interval_ms, out_col}\n  Floor a timestamp into integer buckets of size interval_ms.\n\n\u2022 time_slice {time_col, out_col, on_miss?, windows: [{name,start,end}]}\n  Label rows with a phase string based on which window they fall in.\n  start/end accept {context.x} or any ref grammar; missing rows get on_miss.\n\n\u2022 groupby_agg {by, aggs: {col: agg, ...}}\n  Standard pandas groupby + agg, returns a flat reset_index frame.\n\n\u2022 pivot {index, columns, values, aggfunc?}\n  DataFrame.pivot_table; column names cast to str; fill_value=0.\n\n\u2022 rolling {window, col, agg, out_col?}\n  Rolling window aggregation (mean/sum/min/max/std/...) with\n  min_periods=1.\n\n\u2022 derive {out_col, expr}\n  Vectorised DataFrame.eval expression (no Python branching).\n\n\u2022 apply_expr {out_col, expr}\n  Per-row Python expression evaluated with the row as locals.\n  Slower; use only when `derive` cannot express the logic.\n\n\u2022 rename {mapping: {old_name: new_name, ...}}\n  Rename columns in place.\n\n\u2022 lifecycle_event {group_by, sort_by?, status_col?, out_col?}\n  Within each group_by partition, label rows with the\n  '<prev_status> \u2192 <status>' transition that produced them.\n  Used for order-lifecycle narratives."
    },
    constraints: ["Ops execute in declared order; mid-pipeline `as` publishes intermediate datasets without consuming them.", "apply_expr runs Python eval row-by-row \u2014 keep expressions small and side-effect-free."] as const,
  },
  GROUP_BY: {
    description: "Split a dataset by column value into one DataFrame per group",
    inputs: {
          "dataset": "Upstream dataset to partition."
    },
    outputs: {
          "keys": "{values: [...]} list of distinct group keys. Stored in ctx.values under keys_output_name (default '{input_name}_keys').",
          "groups": "Each group slice is published as ctx.datasets[f\"{output_prefix}_{key}\"]. Conceptual bucket \u2014 runtime stores one dataset per key."
    },
    configSchema: {
          "input_name": "Name of the dataset to partition.",
          "group_by_column": "Column whose distinct values define group boundaries.",
          "output_prefix": "Prefix for per-group dataset names. For key='BOOK_A' and prefix 'orders_by_book', the slice is published as ctx.datasets['orders_by_book_BOOK_A'].",
          "keys_output_name": "ctx.values key for the {values: [...]} list. Defaults to '{input_name}_keys' when blank.",
          "dropna": "Drop rows where the group_by_column is null before partitioning.",
          "order": "Key order: first_seen, sort (ascending), desc."
    },
    constraints: ["Output dataset names contain the raw key value \u2014 keep keys filesystem-safe."] as const,
  },
  GUARDRAIL: {
    description: "Apply deterministic safety checks to action/result state",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  LLM_ACTION: {
    description: "llm.action \u2014 choose the next tool call using critic feedback and retry context",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "plan_key": "string \u2014 ctx.values key for plan",
          "validation_key": "string \u2014 ctx.values key for critic feedback",
          "retry_context_key": "string \u2014 ctx.values key for retry history",
          "args": "object \u2014 static tool args merged into action",
          "tool": "string \u2014 fallback tool"
    },
    constraints: [] as const,
  },
  LLM_CONTEXTUALIZER: {
    description: "llm.contextualizer \u2014 combine query and retrieved docs into enriched context",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "query": "string \u2014 query text",
          "retrieved_docs": "array \u2014 documents to contextualize",
          "docs_key": "string \u2014 ctx.values key containing retrieved docs"
    },
    constraints: [] as const,
  },
  LLM_CRITIC: {
    description: "llm.critic \u2014 validate the latest action result and emit actionable feedback",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "action_key": "string \u2014 ctx.values key for last action",
          "result_key": "string \u2014 ctx.values key for last result",
          "expected_schema": "object \u2014 expected result/schema hints"
    },
    constraints: [] as const,
  },
  LLM_EVALUATOR: {
    description: "llm.evaluator \u2014 decide whether the current workflow goal is satisfied",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "validation_key": "string \u2014 ctx.values key for critic validation",
          "result_key": "string \u2014 ctx.values key for result to evaluate"
    },
    constraints: [] as const,
  },
  LLM_PLANNER: {
    description: "llm.planner \u2014 create a step plan from goal and context",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "goal": "string \u2014 user goal",
          "plan": "array \u2014 optional deterministic plan override"
    },
    constraints: [] as const,
  },
  LLM_SYNTHESIZER: {
    description: "llm.synthesizer \u2014 produce final output and optional JSON/text artifact",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "use_llm": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback",
          "system_prompt": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders",
          "prompt_template": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots",
          "prompt_context": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar",
          "model": "string \u2014 optional model override",
          "temperature": "number \u2014 model temperature",
          "max_output_tokens": "integer \u2014 output token cap",
          "output_name": "string \u2014 ctx.values key to write",
          "output_path": "string \u2014 optional artifact path",
          "result_key": "string \u2014 ctx.values key to summarize",
          "final_output": "object \u2014 optional deterministic final output override"
    },
    constraints: [] as const,
  },
  LOOP_CONTROLLER: {
    description: "Compute retry-loop continuation from iteration, done, and confidence state",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  MAP: {
    description: "Fan out a sub-workflow over a list of keys; aggregate results",
    inputs: {
          "keys": "{values: [...]} list \u2014 typically from EXTRACT_LIST or GROUP_BY."
    },
    outputs: {
          "results": "{results: {<key>: {<collected_name>: value, ...}}} \u2014 stored in ctx.values[output_name]. Per-iteration datasets listed in collect_datasets are ALSO published at the top level as ctx.datasets[f\"{output_name}_{key}_{dataset_name}\"] so downstream nodes can address them directly."
    },
    configSchema: {
          "keys_key": "ctx.values key holding the {values: [...]} list to iterate.",
          "iteration_ctx_key": "ctx.values key where the current iteration's key is written for each sub-workflow run. Lets sub-workflow collectors template queries against the current group.",
          "dataset_prefix": "Optional prefix used by an upstream GROUP_BY. When set, the per-iteration dataset ctx.datasets[f\"{dataset_prefix}_{key}\"] is aliased into the child ctx under iteration_dataset_alias.",
          "iteration_dataset_alias": "Alias name for the per-iteration dataset inside the child ctx. No-op when dataset_prefix is blank.",
          "sub_workflow": "Nested DAG: {nodes: [...], edges: [...]}. Runs once per key.",
          "collect_values": "ctx.values keys to harvest from each iteration into results[key].",
          "collect_datasets": "ctx.datasets names to harvest from each iteration. They become both results[key][name] and ctx.datasets[f\"{output_name}_{key}_{name}\"].",
          "output_name": "ctx.values key for the aggregated {results: {...}} dict."
    },
    constraints: ["sub_workflow is executed in topological order per iteration; child ctx is a shallow copy of parent.", "Iteration-local writes do NOT leak back to the parent ctx except via collect_values / collect_datasets."] as const,
  },
  MARKET_DATA_COLLECTOR: {
    description: "Query EBS/Mercury tick data, normalise timestamps",
    inputs: {
          "context": "Context keys referenced in query_template as {context.xxx}."
    },
    outputs: {
          "ticks": "DataFrame with columns: timestamp (ISO str), symbol (str), bid, ask, mid, spread_pips, bid_size, ask_size, venue_name, seq_no. Stored under ctx.datasets[output_name].",
          "tick_count": "Tick count (int). Stored as {output_name}_tick_count."
    },
    configSchema: {
          "source": "Which tick feed to query.",
          "query_template": "Query with {context.xxx} placeholders.",
          "output_name": "Dataset name in ctx.datasets.",
          "mock_csv_path": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing."
    },
    constraints: ["Normalises raw_timestamp (nanosecond int) \u2192 ISO-8601 string.", "Normalises byte-string fields (raw_symbol, venue) \u2192 plain str."] as const,
  },
  ORACLE_DATA_COLLECTOR: {
    description: "Query Oracle surveillance warehouse order/execution extracts",
    inputs: {
          "context": "Context keys referenced in query_template as {context.xxx}"
    },
    outputs: {
          "rows": "Oracle extract rows. Stored in ctx.datasets under the configured output_name.",
          "row_count": "Integer row count. Stored in ctx.values as {output_name}_count."
    },
    configSchema: {
          "source": "Which Oracle extract to query.",
          "query_template": "Oracle SQL template; use {context.xxx} placeholders for alert fields.",
          "output_name": "Dataset name in ctx.datasets.",
          "mock_csv_path": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator."
    },
    constraints: [] as const,
  },
  PLAN_VALIDATOR: {
    description: "Validate generated plan structure, dependencies, and tool names",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  REPORT_OUTPUT: {
    description: "Generate Excel report with tabs & highlights",
    inputs: {
          "datasets": "All DataFrames to include as tabs (ctx.datasets).",
          "sections": "Section narratives for the Section Summaries sheet.",
          "executive_summary": "Executive summary text.",
          "context": "disposition, trader_id, currency_pair etc. used on the cover page."
    },
    outputs: {
          "report_path": "Absolute path to the written .xlsx file. Stored as context.report_path."
    },
    configSchema: {
          "output_path": "File path for the Excel output (e.g. 'output/report.xlsx').",
          "tabs": "Array of tab specs. Each tab is one of:\n\u2022 Static tab \u2014 {name, dataset, include_highlights?}.\n  Renders the named dataset under the given sheet name.\n\n\u2022 Expanded tab \u2014 {expand_from, as?, name, dataset, include_highlights?}.\n  `expand_from` is a single `{ref}` resolving to a list, dict,\n  Series, or MAP-result. One tab is emitted per item, with the\n  item bound under `as` (default `item`) and substituted into both\n  `name` and `dataset` templates via `.format_map`. Examples:\n\n    expand_from: \"{context.book_list}\"\n    as: book\n    name: \"Executions \u00b7 {book}\"\n    dataset: \"executions_{book}\"\n\n    expand_from: \"{per_book.results}\"   # MAP result dict\n    as: key\n    name: \"Per-book {key}\"\n    dataset: \"per_book_{key}_executions\"\n\nWhen `tabs` is empty, all context.datasets are included as auto-named tabs."
    },
    constraints: ["Tab names truncated to 31 characters (Excel limit).", "Datetime columns converted to strings automatically.", "List/dict cell values stringified automatically.", "If include_highlights=true, uses dataset_name + '_highlighted' if it exists.", "Must be the final node in the workflow."] as const,
  },
  SECTION_SUMMARY: {
    description: "Aggregate stats + LLM narrative section",
    inputs: {
          "dataset": "Any DataFrame referenced by input_name.",
          "context": "trader_id, currency_pair, disposition consumed by the prompt template."
    },
    outputs: {
          "section": "{name, stats, narrative, dataset}. Stored under context.sections[section_name]."
    },
    configSchema: {
          "section_name": "Unique section identifier.",
          "input_name": "Source dataset.",
          "mode": "templated     \u2014 legacy stats-in-prompt flow. fact_pack_llm \u2014 pre-compute named facts, pass as JSON, verify each\n                required fact appears in narrative (retry once).\nevent_narrative \u2014 format one line per row into a chronological list,\n                  then stitch with an LLM.",
          "field_bindings": "Array of {field: string, agg: 'count'|'sum'|'mean'|'nunique'|'max'|'min'}. Used in templated mode.",
          "facts": "Array of {name, column, agg} for fact_pack_llm mode. Example: [{name: 'buy_count', column: 'side', agg: 'count_where_buy'}].",
          "required_facts": "Fact names whose values MUST appear verbatim in the generated narrative. A retry is triggered once if any are missing.",
          "sort_by": "Column used to order rows for event_narrative mode.",
          "event_template": "Python format string used to render each event row in event_narrative mode. Row columns are passed as keyword args. Example: '{timestamp}  {side} {quantity} @ {limit_price}'.",
          "max_events": "Cap events passed to the LLM in event_narrative mode.",
          "llm_prompt_template": "Prompt with {stats}, {facts}, {events}, {section}, {disposition}, {trader_id}, {currency_pair} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset|mixed) {dataset}. In templated mode, {stats} renders a text block and {stats.<field>_<agg>} can reference a computed field_binding stat. Cross-dataset refs like {executions.notional.sum} resolve inline.",
          "system_prompt": "System instruction for the section narrative LLM. Rendered with the same prompt_context vars and context refs as llm_prompt_template.",
          "prompt_context": "Optional structured slot block: {mode: template|dataset|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. vars resolve cross-dataset refs into named slots; the serialized dataset (csv/json/markdown) is exposed as {dataset}.",
          "model": "Optional LLM model override.",
          "temperature": "LLM temperature.",
          "max_output_tokens": "Maximum response tokens."
    },
    constraints: ["Default max_output_tokens: 600.", "fact_pack_llm retries at most once when required facts are missing from the narrative."] as const,
  },
  SIGNAL_CALCULATOR: {
    description: "Compute signals \u2014 always outputs 5 columns",
    inputs: {
          "dataset": "Trade/execution DataFrame (typically after NORMALISE_ENRICH)."
    },
    outputs: {
          "signals": "Input DataFrame + exactly 5 signal columns: _signal_flag (bool), _signal_score (float in [0, 1] \u2014 same scale as DECISION_RULE.score), _signal_reason (str), _signal_type (str), _signal_window (str).",
          "flag_count": "Number of rows where _signal_flag == True. Stored as {output_name}_flag_count."
    },
    configSchema: {
          "mode": "How the signal is computed.",
          "signal_type": "Built-in signal family (configure mode only).",
          "input_name": "Source dataset name (an upstream output_name).",
          "output_name": "Output dataset name.",
          "params": "Signal-specific parameters (overrides built-in defaults).",
          "script_path": "Path to custom Python script (upload_script mode).",
          "script_content": "Inline Python snippet operating on local variable `df` (upload_script mode)."
    },
    constraints: ["ALWAYS outputs exactly these 5 columns: _signal_flag, _signal_score, _signal_reason, _signal_type, _signal_window.", "Missing signal columns are auto-filled with defaults (False, 0.0, '', '', '').", "Custom scripts must operate on local variable 'df' and leave result in 'df'."] as const,
  },
  STATE_MANAGER: {
    description: "Track retry history and iteration state",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "output_name": "string \u2014 ctx.values key to write"
    },
    constraints: [] as const,
  },
  TIME_WINDOW: {
    description: "Expand an event time into a [start_time, end_time] window for downstream filtering.",
    inputs: {
          "context": "Context keys referenced in event_time_key / end_time_key."
    },
    outputs: {
          "window": "{start_time, end_time, buffer_minutes}. Published under ctx.values[output_name]."
    },
    configSchema: {
          "event_time_key": "ctx.values key holding the anchor time (e.g. 'fr_start' from the alert). Required unless start_time_literal is set.",
          "end_time_key": "ctx.values key holding the end anchor (e.g. 'fr_end'). If empty, end = start.",
          "start_time_literal": "Literal ISO start time. Used when the window anchor isn't in ctx.values.",
          "end_time_literal": "Literal ISO end time.",
          "pre_minutes": "Subtract this many minutes from the start anchor.",
          "post_minutes": "Add this many minutes to the end anchor.",
          "output_name": "ctx.values key under which to publish the window dict (default 'window')."
    },
    constraints: ["Output dict keys: start_time (ISO str), end_time (ISO str), buffer_minutes {pre, post}.", "If the event time cannot be resolved, publishes an empty dict \u2014 downstream collectors treat that as no-filter."] as const,
  },
  TOOL_EXECUTOR: {
    description: "Bridge an LLM action into deterministic built-in or registered node execution",
    inputs: {
          "state": "object from RunContext"
    },
    outputs: {
          "output": "object stored in ctx.values"
    },
    configSchema: {
          "action_key": "string \u2014 ctx.values action key",
          "tool": "string \u2014 optional static tool override",
          "args": "object \u2014 static args merged into action args",
          "output_name": "string \u2014 defaults to last_result"
    },
    constraints: [] as const,
  },
}

/** Typed port — what flows along an edge. */
export interface NodePortSpec {
  name: string
  type: 'dataframe' | 'scalar' | 'object' | 'text'
  description: string
  optional: boolean
  required_columns?: readonly string[]
  required_keys?: readonly string[]
  source_config_key?: string
  store_at?: string
}

/** Typed config param with UI hint. */
export interface NodeParamSpec {
  name: string
  type:
    | 'string'
    | 'integer'
    | 'number'
    | 'boolean'
    | 'enum'
    | 'string_list'
    | 'object'
    | 'array'
    | 'input_ref'
    | 'code'
  description: string
  required: boolean
  widget:
    | 'text'
    | 'textarea'
    | 'number'
    | 'checkbox'
    | 'select'
    | 'chips'
    | 'json'
    | 'input_ref'
    | 'code'
  default?: unknown
  enum?: readonly string[]
}

export interface NodeTypedSpec {
  inputPorts: readonly NodePortSpec[]
  outputPorts: readonly NodePortSpec[]
  params: readonly NodeParamSpec[]
}

export const NODE_TYPED: Record<NodeType, NodeTypedSpec> = {
  ACTION_VALIDATOR: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  AGGREGATOR_NODE: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  ALERT_TRIGGER: {
    inputPorts: [{"name": "alert_payload", "type": "object", "description": "JSON object passed at workflow invocation time.", "optional": false}] as const,
    outputPorts: [{"name": "context_keys", "type": "object", "description": "One context key per declared alert_field, e.g. trader_id, book, alert_date, currency_pair, alert_id.", "optional": false, "store_at": "ctx.values[context_keys]"}] as const,
    params: [{"name": "alert_fields", "type": "object", "description": "Map of field_name \u2192 type (string|date|number). Non-listed payload keys in extras.standard_alert_fields are still bound when present in the alert.", "required": false, "widget": "json", "default": {}}] as const,
  },
  COMMS_COLLECTOR: {
    inputPorts: [{"name": "context", "type": "object", "description": "Context keys referenced in query_template as {context.xxx}.", "optional": true}] as const,
    outputPorts: [{"name": "comms", "type": "dataframe", "description": "DataFrame with columns: user, timestamp, display_post, event_type, _keyword_hit, _matched_keywords. Stored under ctx.datasets[output_name].", "optional": false, "required_columns": ["user", "timestamp", "display_post", "event_type", "_keyword_hit", "_matched_keywords"], "store_at": "ctx.datasets[{output_name}]"}, {"name": "keyword_hit_count", "type": "scalar", "description": "Total keyword hit count (int). Stored as {output_name}_keyword_hits.", "optional": true, "store_at": "ctx.values[{output_name}_keyword_hits]"}] as const,
    params: [{"name": "query_template", "type": "string", "description": "Oculus query with {context.xxx} placeholders.", "required": true, "widget": "textarea"}, {"name": "keywords", "type": "string_list", "description": "Terms to scan in display_post.", "required": false, "widget": "chips", "default": []}, {"name": "keyword_categories", "type": "object", "description": "Optional {category: [kw1, kw2, ...]} map. When present, each row gains a _matched_categories list plus one _hit_<cat> boolean column. Combined with plain `keywords` (both are scanned).", "required": false, "widget": "json", "default": {}}, {"name": "emit_hits_only", "type": "boolean", "description": "Also publish ctx.datasets[f\"{output_name}_hits\"] containing only rows with at least one keyword match. Lets downstream SECTION_SUMMARY narrate just the suspicious subset.", "required": false, "widget": "checkbox", "default": false}, {"name": "output_name", "type": "string", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "text", "default": "comms"}, {"name": "mock_csv_path", "type": "string", "description": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing.", "required": false, "widget": "text", "default": ""}] as const,
  },
  CONSOLIDATED_SUMMARY: {
    inputPorts: [{"name": "sections", "type": "object", "description": "All section objects produced by upstream SECTION_SUMMARY nodes (context.sections).", "optional": false}] as const,
    outputPorts: [{"name": "executive_summary", "type": "text", "description": "Multi-paragraph executive summary. Stored as context.executive_summary.", "optional": false, "store_at": "ctx.executive_summary"}] as const,
    params: [{"name": "llm_prompt_template", "type": "string", "description": "Custom prompt with {section_text}, {trader_id}, {currency_pair}, {disposition}, {flag_count} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset|mixed) {dataset}. Cross-dataset refs like {executions.notional.sum} resolve inline. Falls back to the built-in template when empty.", "required": false, "widget": "textarea"}, {"name": "system_prompt", "type": "string", "description": "System instruction for the executive-summary LLM. Rendered with {section_text}, alert context, prompt_context vars, and context refs.", "required": false, "widget": "textarea"}, {"name": "prompt_context", "type": "object", "description": "Optional structured slot block: {mode: template|dataset|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. Same shape as SECTION_SUMMARY.prompt_context.", "required": false, "widget": "json", "default": {}}, {"name": "model", "type": "string", "description": "Optional LLM model override.", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "LLM temperature.", "required": false, "widget": "number", "default": 0.2}, {"name": "max_output_tokens", "type": "integer", "description": "Maximum response tokens.", "required": false, "widget": "number", "default": 1000}] as const,
  },
  DATA_HIGHLIGHTER: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Any DataFrame referenced by input_name.", "optional": false}] as const,
    outputPorts: [{"name": "highlighted", "type": "dataframe", "description": "Input DataFrame + _highlight_colour (hex) + _highlight_label (str). Stored under ctx.datasets[output_name].", "optional": false, "required_columns": ["_highlight_colour", "_highlight_label"], "store_at": "ctx.datasets[{output_name}]"}] as const,
    params: [{"name": "input_name", "type": "input_ref", "description": "Source dataset.", "required": true, "widget": "input_ref"}, {"name": "output_name", "type": "string", "description": "Highlighted dataset name (convention: input_name + '_highlighted').", "required": true, "widget": "text"}, {"name": "rules", "type": "array", "description": "Array of {condition, colour, label}. `condition` is a pandas.DataFrame.eval expression evaluated against the target dataset's rows. The condition may include `{ref}` placeholders that resolve to SCALAR values via the cross-dataset ref grammar BEFORE pandas eval \u2014 e.g. `notional > {context.peak_threshold}`, `bucket == {ladder.peak_bucket.first}`. `colour` is hex #RRGGBB.", "required": false, "widget": "json", "default": []}] as const,
  },
  DATA_REDUCER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "reduced_data", "type": "dataframe", "description": "DataFrame stored in ctx.datasets[output_name]", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  DECISION_RULE: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Signal DataFrame with _signal_flag column.", "optional": false, "required_columns": ["_signal_flag"]}, {"name": "flag_count", "type": "scalar", "description": "Flag count from SIGNAL_CALCULATOR (read from ctx.values[{input_name}_flag_count] if the dataset isn't available).", "optional": true}] as const,
    outputPorts: [{"name": "disposition", "type": "text", "description": "'ESCALATE' | 'REVIEW' | 'DISMISS'. Stored as context.disposition.", "optional": false, "store_at": "ctx.disposition"}, {"name": "severity", "type": "text", "description": "'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'. Stored as context.severity.", "optional": false}, {"name": "score", "type": "scalar", "description": "Normalised severity score in [0, 1]. Stored as context.score.", "optional": false}, {"name": "flag_count", "type": "scalar", "description": "Total signal hits (int). Stored as context.flag_count.", "optional": false, "store_at": "ctx.values[flag_count]"}, {"name": "output_branch", "type": "text", "description": "Branch name to route to. Stored as context.output_branch.", "optional": false, "store_at": "ctx.output_branch"}, {"name": "matched_rule", "type": "text", "description": "Name of the rule that fired (rule mode only; empty in threshold mode). Stored as context.matched_rule.", "optional": false}] as const,
    params: [{"name": "input_name", "type": "input_ref", "description": "Signal dataset name.", "required": true, "widget": "input_ref"}, {"name": "escalate_threshold", "type": "integer", "description": "flag_count >= this \u2192 ESCALATE (threshold mode).", "required": false, "widget": "number", "default": 1}, {"name": "review_threshold", "type": "integer", "description": "flag_count >= this \u2192 REVIEW (threshold mode).", "required": false, "widget": "number", "default": 1}, {"name": "rules", "type": "array", "description": "Optional rules list, evaluated top-to-bottom; first match wins. Each rule: {name, when, severity?, disposition?}. `when` accepts `{ref}` (truthy test) or `{ref} OP literal` where OP \u2208 {>=,<=,==,!=,>,<}. Refs use the cross-dataset grammar \u2014 e.g. `{executions._signal_flag.sum} >= 10`, `{ladder.symmetry.max} > 0.85`, `{context.book_count} > 1`.", "required": false, "widget": "json", "default": []}, {"name": "severity_map", "type": "object", "description": "Override severity per disposition. Defaults: {ESCALATE: HIGH, REVIEW: MEDIUM, DISMISS: LOW}.", "required": false, "widget": "json", "default": {}}, {"name": "output_branches", "type": "object", "description": "Map of disposition \u2192 branch_name string.", "required": false, "widget": "json", "default": {}}] as const,
  },
  ERROR_HANDLER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  EXECUTION_DATA_COLLECTOR: {
    inputPorts: [{"name": "context", "type": "object", "description": "Context keys referenced in query_template as {context.xxx}", "optional": true}, {"name": "window", "type": "object", "description": "Optional TIME_WINDOW output (start_time, end_time) \u2014 filters rows to the window when window_key is set.", "optional": true}] as const,
    outputPorts: [{"name": "executions", "type": "dataframe", "description": "Order/execution rows. Stored in ctx.datasets under the configured output_name.", "optional": false, "store_at": "ctx.datasets[{output_name}]"}, {"name": "row_count", "type": "scalar", "description": "Integer row count. Stored in ctx.values as {output_name}_count.", "optional": true, "store_at": "ctx.values[{output_name}_count]"}] as const,
    params: [{"name": "source", "type": "enum", "description": "Which Solr collection to query. Values are derived from data_sources/metadata/trades.yaml at runtime.", "required": true, "widget": "select", "default": "hs_client_order", "enum": ["hs_client_order", "hs_execution", "hs_trades", "hs_orders_and_executions", "hs_quotes"]}, {"name": "query_template", "type": "string", "description": "Solr query; use {context.xxx} placeholders for alert fields.", "required": true, "widget": "textarea"}, {"name": "output_name", "type": "string", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "text", "default": "execution_data"}, {"name": "window_key", "type": "string", "description": "ctx.values key holding the window dict. Used when a TIME_WINDOW node is wired upstream.", "required": false, "widget": "text", "default": "window"}, {"name": "trader_filter_key", "type": "string", "description": "ctx.values key whose value filters trader_id when present. Empty = no trader filter.", "required": false, "widget": "text", "default": "trader_id"}, {"name": "loop_over_books", "type": "boolean", "description": "Repeat the query for each book in the books list.", "required": false, "widget": "checkbox", "default": false}, {"name": "books", "type": "string_list", "description": "Book names when loop_over_books=true.", "required": false, "widget": "chips", "default": []}, {"name": "mock_csv_path", "type": "string", "description": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing. CSV columns are not re-checked against the lists below; synthetic rows are.", "required": false, "widget": "text", "default": ""}] as const,
  },
  EXTRACT_LIST: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Source DataFrame (by input_name).", "optional": false}] as const,
    outputPorts: [{"name": "values", "type": "object", "description": "{values: [...]} \u2014 published under ctx.values[output_name].", "optional": false}] as const,
    params: [{"name": "input_name", "type": "input_ref", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "input_ref"}, {"name": "column", "type": "string", "description": "Column to enumerate.", "required": true, "widget": "text"}, {"name": "output_name", "type": "string", "description": "ctx.values key to publish {values: [...]} under.", "required": true, "widget": "text"}, {"name": "order", "type": "enum", "description": "sort: ascending, desc: descending, first_seen: original order.", "required": false, "widget": "select", "default": "first_seen", "enum": ["sort", "desc", "first_seen"]}, {"name": "dropna", "type": "boolean", "description": "Exclude NaN values.", "required": false, "widget": "checkbox", "default": true}] as const,
  },
  EXTRACT_SCALAR: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Source DataFrame (by input_name).", "optional": false}] as const,
    outputPorts: [{"name": "value", "type": "scalar", "description": "Published under ctx.values[output_name].", "optional": true}] as const,
    params: [{"name": "input_name", "type": "input_ref", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "input_ref"}, {"name": "column", "type": "string", "description": "Column to reduce.", "required": true, "widget": "text"}, {"name": "reducer", "type": "enum", "description": "How to collapse the column to a single value.", "required": true, "widget": "select", "default": "unique_single", "enum": ["first", "unique_single", "max", "min", "count", "sum", "mean"]}, {"name": "output_name", "type": "string", "description": "ctx.values key to publish the scalar under.", "required": true, "widget": "text"}, {"name": "fail_on_ambiguous", "type": "boolean", "description": "When reducer=unique_single, raise if the column has more than one distinct value (default false \u2014 take the first).", "required": false, "widget": "checkbox", "default": false}] as const,
  },
  FEATURE_ENGINE: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Source DataFrame referenced by input_name.", "optional": false}] as const,
    outputPorts: [{"name": "features", "type": "dataframe", "description": "Final working DataFrame after all chained ops, published as ctx.datasets[output_name]. Ops with an `as` field also publish intermediate datasets under that name.", "optional": false}] as const,
    params: [{"name": "input_name", "type": "input_ref", "description": "Source dataset name.", "required": true, "widget": "input_ref"}, {"name": "output_name", "type": "string", "description": "Target dataset name (defaults to input_name).", "required": false, "widget": "text"}, {"name": "ops", "type": "array", "description": "Ordered list of operations applied to the working DataFrame. Each op is {op: <name>, ...op-specific keys, as?: <publish_name>}. Supported ops:\n\u2022 window_bucket {time_col, interval_ms, out_col}\n  Floor a timestamp into integer buckets of size interval_ms.\n\n\u2022 time_slice {time_col, out_col, on_miss?, windows: [{name,start,end}]}\n  Label rows with a phase string based on which window they fall in.\n  start/end accept {context.x} or any ref grammar; missing rows get on_miss.\n\n\u2022 groupby_agg {by, aggs: {col: agg, ...}}\n  Standard pandas groupby + agg, returns a flat reset_index frame.\n\n\u2022 pivot {index, columns, values, aggfunc?}\n  DataFrame.pivot_table; column names cast to str; fill_value=0.\n\n\u2022 rolling {window, col, agg, out_col?}\n  Rolling window aggregation (mean/sum/min/max/std/...) with\n  min_periods=1.\n\n\u2022 derive {out_col, expr}\n  Vectorised DataFrame.eval expression (no Python branching).\n\n\u2022 apply_expr {out_col, expr}\n  Per-row Python expression evaluated with the row as locals.\n  Slower; use only when `derive` cannot express the logic.\n\n\u2022 rename {mapping: {old_name: new_name, ...}}\n  Rename columns in place.\n\n\u2022 lifecycle_event {group_by, sort_by?, status_col?, out_col?}\n  Within each group_by partition, label rows with the\n  '<prev_status> \u2192 <status>' transition that produced them.\n  Used for order-lifecycle narratives.", "required": true, "widget": "json", "default": []}] as const,
  },
  GROUP_BY: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Upstream dataset to partition.", "optional": false}] as const,
    outputPorts: [{"name": "keys", "type": "object", "description": "{values: [...]} list of distinct group keys. Stored in ctx.values under keys_output_name (default '{input_name}_keys').", "optional": false}, {"name": "groups", "type": "object", "description": "Each group slice is published as ctx.datasets[f\"{output_prefix}_{key}\"]. Conceptual bucket \u2014 runtime stores one dataset per key.", "optional": false}] as const,
    params: [{"name": "input_name", "type": "string", "description": "Name of the dataset to partition.", "required": true, "widget": "text"}, {"name": "group_by_column", "type": "string", "description": "Column whose distinct values define group boundaries.", "required": true, "widget": "text"}, {"name": "output_prefix", "type": "string", "description": "Prefix for per-group dataset names. For key='BOOK_A' and prefix 'orders_by_book', the slice is published as ctx.datasets['orders_by_book_BOOK_A'].", "required": true, "widget": "text"}, {"name": "keys_output_name", "type": "string", "description": "ctx.values key for the {values: [...]} list. Defaults to '{input_name}_keys' when blank.", "required": false, "widget": "text", "default": ""}, {"name": "dropna", "type": "boolean", "description": "Drop rows where the group_by_column is null before partitioning.", "required": false, "widget": "checkbox", "default": true}, {"name": "order", "type": "enum", "description": "Key order: first_seen, sort (ascending), desc.", "required": false, "widget": "select", "default": "first_seen", "enum": ["first_seen", "sort", "desc"]}] as const,
  },
  GUARDRAIL: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  LLM_ACTION: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "plan_key", "type": "string", "description": "string \u2014 ctx.values key for plan", "required": false, "widget": "text"}, {"name": "validation_key", "type": "string", "description": "string \u2014 ctx.values key for critic feedback", "required": false, "widget": "text"}, {"name": "retry_context_key", "type": "string", "description": "string \u2014 ctx.values key for retry history", "required": false, "widget": "text"}, {"name": "args", "type": "object", "description": "object \u2014 static tool args merged into action", "required": false, "widget": "json"}, {"name": "tool", "type": "string", "description": "string \u2014 fallback tool", "required": false, "widget": "text"}] as const,
  },
  LLM_CONTEXTUALIZER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "query", "type": "string", "description": "string \u2014 query text", "required": false, "widget": "text"}, {"name": "retrieved_docs", "type": "string", "description": "array \u2014 documents to contextualize", "required": false, "widget": "text"}, {"name": "docs_key", "type": "string", "description": "string \u2014 ctx.values key containing retrieved docs", "required": false, "widget": "text"}] as const,
  },
  LLM_CRITIC: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "action_key", "type": "string", "description": "string \u2014 ctx.values key for last action", "required": false, "widget": "text"}, {"name": "result_key", "type": "string", "description": "string \u2014 ctx.values key for last result", "required": false, "widget": "text"}, {"name": "expected_schema", "type": "object", "description": "object \u2014 expected result/schema hints", "required": false, "widget": "json"}] as const,
  },
  LLM_EVALUATOR: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "validation_key", "type": "string", "description": "string \u2014 ctx.values key for critic validation", "required": false, "widget": "text"}, {"name": "result_key", "type": "string", "description": "string \u2014 ctx.values key for result to evaluate", "required": false, "widget": "text"}] as const,
  },
  LLM_PLANNER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "goal", "type": "string", "description": "string \u2014 user goal", "required": false, "widget": "text"}, {"name": "plan", "type": "string", "description": "array \u2014 optional deterministic plan override", "required": false, "widget": "text"}] as const,
  },
  LLM_SYNTHESIZER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "use_llm", "type": "boolean", "description": "boolean \u2014 call configured LLM when true; otherwise use deterministic fallback", "required": false, "widget": "checkbox"}, {"name": "system_prompt", "type": "string", "description": "string \u2014 system instruction for this LLM role; rendered with prompt_context and state placeholders", "required": false, "widget": "text"}, {"name": "prompt_template", "type": "string", "description": "string \u2014 user prompt template; can reference {goal}, {state}, {datasets}, {alert_payload}, prompt_context vars, and node-specific slots", "required": false, "widget": "text"}, {"name": "prompt_context", "type": "object", "description": "object \u2014 optional structured slots: {mode, vars, dataset} using the shared prompt_context grammar", "required": false, "widget": "json"}, {"name": "model", "type": "string", "description": "string \u2014 optional model override", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "number \u2014 model temperature", "required": false, "widget": "number"}, {"name": "max_output_tokens", "type": "integer", "description": "integer \u2014 output token cap", "required": false, "widget": "number"}, {"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}, {"name": "output_path", "type": "string", "description": "string \u2014 optional artifact path", "required": false, "widget": "text"}, {"name": "result_key", "type": "string", "description": "string \u2014 ctx.values key to summarize", "required": false, "widget": "text"}, {"name": "final_output", "type": "object", "description": "object \u2014 optional deterministic final output override", "required": false, "widget": "json"}] as const,
  },
  LOOP_CONTROLLER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  MAP: {
    inputPorts: [{"name": "keys", "type": "object", "description": "{values: [...]} list \u2014 typically from EXTRACT_LIST or GROUP_BY.", "optional": true}] as const,
    outputPorts: [{"name": "results", "type": "object", "description": "{results: {<key>: {<collected_name>: value, ...}}} \u2014 stored in ctx.values[output_name]. Per-iteration datasets listed in collect_datasets are ALSO published at the top level as ctx.datasets[f\"{output_name}_{key}_{dataset_name}\"] so downstream nodes can address them directly.", "optional": false}] as const,
    params: [{"name": "keys_key", "type": "string", "description": "ctx.values key holding the {values: [...]} list to iterate.", "required": true, "widget": "text"}, {"name": "iteration_ctx_key", "type": "string", "description": "ctx.values key where the current iteration's key is written for each sub-workflow run. Lets sub-workflow collectors template queries against the current group.", "required": true, "widget": "text"}, {"name": "dataset_prefix", "type": "string", "description": "Optional prefix used by an upstream GROUP_BY. When set, the per-iteration dataset ctx.datasets[f\"{dataset_prefix}_{key}\"] is aliased into the child ctx under iteration_dataset_alias.", "required": false, "widget": "text", "default": ""}, {"name": "iteration_dataset_alias", "type": "string", "description": "Alias name for the per-iteration dataset inside the child ctx. No-op when dataset_prefix is blank.", "required": false, "widget": "text", "default": ""}, {"name": "sub_workflow", "type": "object", "description": "Nested DAG: {nodes: [...], edges: [...]}. Runs once per key.", "required": true, "widget": "json"}, {"name": "collect_values", "type": "string_list", "description": "ctx.values keys to harvest from each iteration into results[key].", "required": false, "widget": "chips", "default": []}, {"name": "collect_datasets", "type": "string_list", "description": "ctx.datasets names to harvest from each iteration. They become both results[key][name] and ctx.datasets[f\"{output_name}_{key}_{name}\"].", "required": false, "widget": "chips", "default": []}, {"name": "output_name", "type": "string", "description": "ctx.values key for the aggregated {results: {...}} dict.", "required": true, "widget": "text", "default": "map_results"}] as const,
  },
  MARKET_DATA_COLLECTOR: {
    inputPorts: [{"name": "context", "type": "object", "description": "Context keys referenced in query_template as {context.xxx}.", "optional": true}] as const,
    outputPorts: [{"name": "ticks", "type": "dataframe", "description": "DataFrame with columns: timestamp (ISO str), symbol (str), bid, ask, mid, spread_pips, bid_size, ask_size, venue_name, seq_no. Stored under ctx.datasets[output_name].", "optional": false, "required_columns": ["timestamp", "symbol", "bid", "ask", "mid", "spread_pips", "bid_size", "ask_size", "venue_name", "seq_no"], "store_at": "ctx.datasets[{output_name}]"}, {"name": "tick_count", "type": "scalar", "description": "Tick count (int). Stored as {output_name}_tick_count.", "optional": true, "store_at": "ctx.values[{output_name}_tick_count]"}] as const,
    params: [{"name": "source", "type": "enum", "description": "Which tick feed to query.", "required": true, "widget": "select", "default": "EBS", "enum": ["EBS", "Mercury"]}, {"name": "query_template", "type": "string", "description": "Query with {context.xxx} placeholders.", "required": true, "widget": "textarea"}, {"name": "output_name", "type": "string", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "text", "default": "market_data"}, {"name": "mock_csv_path", "type": "string", "description": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing.", "required": false, "widget": "text", "default": ""}] as const,
  },
  ORACLE_DATA_COLLECTOR: {
    inputPorts: [{"name": "context", "type": "object", "description": "Context keys referenced in query_template as {context.xxx}", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "Oracle extract rows. Stored in ctx.datasets under the configured output_name.", "optional": false, "store_at": "ctx.datasets[{output_name}]"}, {"name": "row_count", "type": "scalar", "description": "Integer row count. Stored in ctx.values as {output_name}_count.", "optional": true, "store_at": "ctx.values[{output_name}_count]"}] as const,
    params: [{"name": "source", "type": "enum", "description": "Which Oracle extract to query.", "required": true, "widget": "select", "default": "oracle_orders", "enum": ["oracle_orders", "oracle_executions"]}, {"name": "query_template", "type": "string", "description": "Oracle SQL template; use {context.xxx} placeholders for alert fields.", "required": false, "widget": "textarea", "default": ""}, {"name": "output_name", "type": "string", "description": "Dataset name in ctx.datasets.", "required": true, "widget": "text", "default": "oracle_data"}, {"name": "mock_csv_path", "type": "string", "description": "Demo-mode override: path to a CSV used verbatim instead of the synthetic generator.", "required": false, "widget": "text", "default": ""}] as const,
  },
  PLAN_VALIDATOR: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  REPORT_OUTPUT: {
    inputPorts: [{"name": "datasets", "type": "object", "description": "All DataFrames to include as tabs (ctx.datasets).", "optional": false}, {"name": "sections", "type": "object", "description": "Section narratives for the Section Summaries sheet.", "optional": true}, {"name": "executive_summary", "type": "text", "description": "Executive summary text.", "optional": true}, {"name": "context", "type": "object", "description": "disposition, trader_id, currency_pair etc. used on the cover page.", "optional": true}] as const,
    outputPorts: [{"name": "report_path", "type": "text", "description": "Absolute path to the written .xlsx file. Stored as context.report_path.", "optional": false, "store_at": "ctx.report_path"}] as const,
    params: [{"name": "output_path", "type": "string", "description": "File path for the Excel output (e.g. 'output/report.xlsx').", "required": true, "widget": "text"}, {"name": "tabs", "type": "array", "description": "Array of tab specs. Each tab is one of:\n\u2022 Static tab \u2014 {name, dataset, include_highlights?}.\n  Renders the named dataset under the given sheet name.\n\n\u2022 Expanded tab \u2014 {expand_from, as?, name, dataset, include_highlights?}.\n  `expand_from` is a single `{ref}` resolving to a list, dict,\n  Series, or MAP-result. One tab is emitted per item, with the\n  item bound under `as` (default `item`) and substituted into both\n  `name` and `dataset` templates via `.format_map`. Examples:\n\n    expand_from: \"{context.book_list}\"\n    as: book\n    name: \"Executions \u00b7 {book}\"\n    dataset: \"executions_{book}\"\n\n    expand_from: \"{per_book.results}\"   # MAP result dict\n    as: key\n    name: \"Per-book {key}\"\n    dataset: \"per_book_{key}_executions\"\n\nWhen `tabs` is empty, all context.datasets are included as auto-named tabs.", "required": false, "widget": "json", "default": []}] as const,
  },
  SECTION_SUMMARY: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Any DataFrame referenced by input_name.", "optional": false}, {"name": "context", "type": "object", "description": "trader_id, currency_pair, disposition consumed by the prompt template.", "optional": true}] as const,
    outputPorts: [{"name": "section", "type": "object", "description": "{name, stats, narrative, dataset}. Stored under context.sections[section_name].", "optional": false, "required_keys": ["name", "stats", "narrative", "dataset"], "store_at": "ctx.sections[{section_name}]"}] as const,
    params: [{"name": "section_name", "type": "string", "description": "Unique section identifier.", "required": true, "widget": "text"}, {"name": "input_name", "type": "input_ref", "description": "Source dataset.", "required": true, "widget": "input_ref"}, {"name": "mode", "type": "enum", "description": "templated     \u2014 legacy stats-in-prompt flow. fact_pack_llm \u2014 pre-compute named facts, pass as JSON, verify each\n                required fact appears in narrative (retry once).\nevent_narrative \u2014 format one line per row into a chronological list,\n                  then stitch with an LLM.", "required": false, "widget": "select", "default": "templated", "enum": ["templated", "fact_pack_llm", "event_narrative"]}, {"name": "field_bindings", "type": "array", "description": "Array of {field: string, agg: 'count'|'sum'|'mean'|'nunique'|'max'|'min'}. Used in templated mode.", "required": false, "widget": "json", "default": []}, {"name": "facts", "type": "array", "description": "Array of {name, column, agg} for fact_pack_llm mode. Example: [{name: 'buy_count', column: 'side', agg: 'count_where_buy'}].", "required": false, "widget": "json", "default": []}, {"name": "required_facts", "type": "string_list", "description": "Fact names whose values MUST appear verbatim in the generated narrative. A retry is triggered once if any are missing.", "required": false, "widget": "chips", "default": []}, {"name": "sort_by", "type": "string", "description": "Column used to order rows for event_narrative mode.", "required": false, "widget": "text", "default": ""}, {"name": "event_template", "type": "string", "description": "Python format string used to render each event row in event_narrative mode. Row columns are passed as keyword args. Example: '{timestamp}  {side} {quantity} @ {limit_price}'.", "required": false, "widget": "text", "default": ""}, {"name": "max_events", "type": "integer", "description": "Cap events passed to the LLM in event_narrative mode.", "required": false, "widget": "number", "default": 40}, {"name": "llm_prompt_template", "type": "string", "description": "Prompt with {stats}, {facts}, {events}, {section}, {disposition}, {trader_id}, {currency_pair} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset|mixed) {dataset}. In templated mode, {stats} renders a text block and {stats.<field>_<agg>} can reference a computed field_binding stat. Cross-dataset refs like {executions.notional.sum} resolve inline.", "required": false, "widget": "textarea"}, {"name": "system_prompt", "type": "string", "description": "System instruction for the section narrative LLM. Rendered with the same prompt_context vars and context refs as llm_prompt_template.", "required": false, "widget": "textarea"}, {"name": "prompt_context", "type": "object", "description": "Optional structured slot block: {mode: template|dataset|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. vars resolve cross-dataset refs into named slots; the serialized dataset (csv/json/markdown) is exposed as {dataset}.", "required": false, "widget": "json", "default": {}}, {"name": "model", "type": "string", "description": "Optional LLM model override.", "required": false, "widget": "text"}, {"name": "temperature", "type": "number", "description": "LLM temperature.", "required": false, "widget": "number", "default": 0.2}, {"name": "max_output_tokens", "type": "integer", "description": "Maximum response tokens.", "required": false, "widget": "number", "default": 600}] as const,
  },
  SIGNAL_CALCULATOR: {
    inputPorts: [{"name": "dataset", "type": "dataframe", "description": "Trade/execution DataFrame (typically after NORMALISE_ENRICH).", "optional": false}] as const,
    outputPorts: [{"name": "signals", "type": "dataframe", "description": "Input DataFrame + exactly 5 signal columns: _signal_flag (bool), _signal_score (float in [0, 1] \u2014 same scale as DECISION_RULE.score), _signal_reason (str), _signal_type (str), _signal_window (str).", "optional": false, "required_columns": ["_signal_flag", "_signal_score", "_signal_reason", "_signal_type", "_signal_window"]}, {"name": "flag_count", "type": "scalar", "description": "Number of rows where _signal_flag == True. Stored as {output_name}_flag_count.", "optional": true}] as const,
    params: [{"name": "mode", "type": "enum", "description": "How the signal is computed.", "required": true, "widget": "select", "default": "configure", "enum": ["configure", "upload_script"]}, {"name": "signal_type", "type": "enum", "description": "Built-in signal family (configure mode only).", "required": false, "widget": "select", "enum": ["FRONT_RUNNING", "WASH_TRADE", "SPOOFING", "LAYERING"]}, {"name": "input_name", "type": "input_ref", "description": "Source dataset name (an upstream output_name).", "required": true, "widget": "input_ref"}, {"name": "output_name", "type": "string", "description": "Output dataset name.", "required": true, "widget": "text"}, {"name": "params", "type": "object", "description": "Signal-specific parameters (overrides built-in defaults).", "required": false, "widget": "json", "default": {}}, {"name": "script_path", "type": "string", "description": "Path to custom Python script (upload_script mode).", "required": false, "widget": "text"}, {"name": "script_content", "type": "code", "description": "Inline Python snippet operating on local variable `df` (upload_script mode).", "required": false, "widget": "code"}] as const,
  },
  STATE_MANAGER: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "output_name", "type": "string", "description": "string \u2014 ctx.values key to write", "required": false, "widget": "text"}] as const,
  },
  TIME_WINDOW: {
    inputPorts: [{"name": "context", "type": "object", "description": "Context keys referenced in event_time_key / end_time_key.", "optional": true}] as const,
    outputPorts: [{"name": "window", "type": "object", "description": "{start_time, end_time, buffer_minutes}. Published under ctx.values[output_name].", "optional": false}] as const,
    params: [{"name": "event_time_key", "type": "string", "description": "ctx.values key holding the anchor time (e.g. 'fr_start' from the alert). Required unless start_time_literal is set.", "required": false, "widget": "text", "default": ""}, {"name": "end_time_key", "type": "string", "description": "ctx.values key holding the end anchor (e.g. 'fr_end'). If empty, end = start.", "required": false, "widget": "text", "default": ""}, {"name": "start_time_literal", "type": "string", "description": "Literal ISO start time. Used when the window anchor isn't in ctx.values.", "required": false, "widget": "text", "default": ""}, {"name": "end_time_literal", "type": "string", "description": "Literal ISO end time.", "required": false, "widget": "text", "default": ""}, {"name": "pre_minutes", "type": "integer", "description": "Subtract this many minutes from the start anchor.", "required": false, "widget": "number", "default": 0}, {"name": "post_minutes", "type": "integer", "description": "Add this many minutes to the end anchor.", "required": false, "widget": "number", "default": 0}, {"name": "output_name", "type": "string", "description": "ctx.values key under which to publish the window dict (default 'window').", "required": true, "widget": "text", "default": "window"}] as const,
  },
  TOOL_EXECUTOR: {
    inputPorts: [{"name": "state", "type": "text", "description": "object from RunContext", "optional": false}] as const,
    outputPorts: [{"name": "output", "type": "object", "description": "object stored in ctx.values", "optional": false}] as const,
    params: [{"name": "action_key", "type": "string", "description": "string \u2014 ctx.values action key", "required": false, "widget": "text"}, {"name": "tool", "type": "string", "description": "string \u2014 optional static tool override", "required": false, "widget": "text"}, {"name": "args", "type": "object", "description": "object \u2014 static args merged into action args", "required": false, "widget": "json"}, {"name": "output_name", "type": "string", "description": "string \u2014 defaults to last_result", "required": false, "widget": "text"}] as const,
  },
}
