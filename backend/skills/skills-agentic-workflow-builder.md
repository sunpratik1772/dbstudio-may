# Skill: Agentic Workflow Builder

## Purpose
Use this skill on every workflow-generation or workflow-edit request. It explains how to compose dbSherpa's deterministic data nodes with the agent-layer nodes.

The core rule is:

```text
LLM nodes decide, critique, evaluate, or synthesize.
Helper/data nodes validate, execute, transform, aggregate, guard, and write artifacts.
```

Do not let an LLM node directly replace a collector, signal, report, or validator when a deterministic node exists.

## Required Agentic Pattern
For high-value agentic workflows, prefer this shape:

```text
ALERT_TRIGGER
→ deterministic data collection / transforms
→ LLM_PLANNER
→ PLAN_VALIDATOR
→ LLM_ACTION
→ ACTION_VALIDATOR
→ GUARDRAIL when safety/compliance matters
→ TOOL_EXECUTOR
→ DATA_REDUCER when the next LLM needs bounded rows
→ LLM_CRITIC
→ STATE_MANAGER
→ LLM_EVALUATOR
→ LOOP_CONTROLLER
→ LLM_SYNTHESIZER
→ REPORT_OUTPUT when an Excel report is required
```

Because the engine is a DAG runner, do not create graph cycles. Express retry readiness through `STATE_MANAGER`, `LLM_CRITIC`, `LLM_EVALUATOR`, and `LOOP_CONTROLLER` state. If a true repeated sub-analysis is needed across keys, use `GROUP_BY` + `MAP`.

## LLM Node Usage

### `LLM_PLANNER`
Use for intent-to-plan conversion inside a runtime workflow.

Config guidance:
- Set `goal` from the user/request or alert context.
- Set `system_prompt` to the planner role and domain constraints.
- Set `prompt_template` to include `{goal}`, `{state}`, `{datasets}`, `{alert_payload}`, and any `prompt_context` vars.
- Output should be a JSON object with `goal` and `steps`.
- Each step should include `step_id`, `action`, `tool`, `inputs`, and `dependencies`.

Use only real tools:
- Built-ins: `aggregation`, `data_quality_checks`, `multi_source_join`, `transform`, `emit_artifact`, `passthrough`
- Registered node types by name when executed through `TOOL_EXECUTOR`.

### `PLAN_VALIDATOR`
Use immediately after `LLM_PLANNER`.

It checks:
- plan steps are objects
- dependency names exist
- tools are known

Set `block_on_invalid: true` when a bad plan should stop execution.

### `LLM_ACTION`
Use to turn one plan step plus feedback into exactly one tool call.

Config guidance:
- Read plan from `plan_key` (default `plan`).
- Read critic feedback from `validation_key` (default `validation`).
- Read retry history from `retry_context_key`.
- Output JSON must include `tool`, `args`, `reasoning`, and `confidence`.

The action must consume critic feedback. Do not repeat the same failed args after the critic suggests a fix.

### `ACTION_VALIDATOR`
Use before `TOOL_EXECUTOR`.

It prevents nonsense calls:
- unknown tools
- invalid args shape
- `input_name` that does not exist in `ctx.datasets`

Set `block_on_invalid: true` for production-grade workflows.

### `GUARDRAIL`
Use before `TOOL_EXECUTOR` for workflows involving customer, counterparty, PII, full scans, or compliance.

Common rules:
- `no_sensitive_data`
- `no_full_scan`

Group by segment/book/venue/counterparty category rather than raw PII fields.

### `TOOL_EXECUTOR`
Use as the ReAct bridge. It maps an action to deterministic execution.

Prefer built-in tools for simple agentic tests:
- `aggregation`: compute grouped metrics from an existing dataset.
- `data_quality_checks`: duplicates/null checks. Use `input_name` for the dataset name (`dataset_name` is tolerated at runtime but `input_name` is preferred).
- `multi_source_join`: join/concat datasets.
- `transform`: apply simple numeric transformations.
- `emit_artifact`: write a JSON/text artifact.

Use registered node types for real surveillance nodes only when the config exactly matches the node contract.

### `DATA_REDUCER`
Use before LLM critique/synthesis when a dataset may be large.

It produces a bounded preview dataset and summary so prompts stay small.

### `LLM_CRITIC`
Use after tool execution.

Output JSON must include:

```json
{
  "valid": true,
  "issues": [],
  "suggestions": [],
  "confidence": 0.95
}
```

If invalid, suggestions must be actionable enough for `LLM_ACTION` to change the next tool args.

For direct evidence review (for example after several `TOOL_EXECUTOR` quality checks), configure the critic with:
- `prompt_template` or `llm_prompt_template`
- `system_prompt`
- `result_key` if it should critique a specific upstream result
- `output_name`

Do not rely on `last_action` unless the workflow actually has an upstream `LLM_ACTION`. For direct evidence completeness critiques, reference concrete data counts with refs like `{client_orders.@row_count}`, `{executions.@row_count}`, `{market_data.@row_count}`, and `{comms.@row_count}` rather than invented context keys like `{client_orders_count}` unless a previous node explicitly wrote that value.

### `STATE_MANAGER`
Use after `LLM_CRITIC`.

It records:
- previous actions
- previous results
- validation feedback
- iteration count

This is the memory that makes retry feedback-driven rather than a naive repeat.

### `LLM_EVALUATOR`
Use after `STATE_MANAGER`.

It decides whether the workflow goal is satisfied. Return:

```json
{
  "done": true,
  "missing": [],
  "confidence": 0.91
}
```

Be strict: if evidence is thin, missing, or not validated, `done` should be false.

### `LOOP_CONTROLLER`
Use after `LLM_EVALUATOR`.

It records whether the loop should continue based on:
- `max_iterations`
- evaluator `done`
- validation confidence

Do not add a backward edge from `LOOP_CONTROLLER` to `LLM_ACTION`; the engine validates workflows as DAGs.

### `LLM_SYNTHESIZER`
Use near the end to create a JSON/text artifact payload from validated results.

Config guidance:
- Set `system_prompt` for final artifact style.
- Set `output_path` when you need a written artifact.
- Use `REPORT_OUTPUT` instead when the deliverable must be the standard Excel report.

### `LLM_CONTEXTUALIZER`
Use when retrieved docs, prior workflow state, or policy text must be compressed before planning.

## Existing Surveillance Nodes Still Matter

Do not replace these with generic LLM nodes:

- `EXECUTION_DATA_COLLECTOR`: collect orders/executions from `hs_client_order`, `hs_execution`, etc.
- `MARKET_DATA_COLLECTOR`: collect EBS/Mercury ticks.
- `COMMS_COLLECTOR`: collect Oculus messages and keyword hits.
- `ORACLE_DATA_COLLECTOR`: collect warehouse/reference rows.
- `FEATURE_ENGINE`: deterministic feature transforms.
- `SIGNAL_CALCULATOR`: built-in `FRONT_RUNNING`, `WASH_TRADE`, `SPOOFING`, `LAYERING` signal columns.
- `DECISION_RULE`: deterministic disposition.
- `SECTION_SUMMARY`: compute stats/facts/events and write `ctx.sections`.
- `CONSOLIDATED_SUMMARY`: produce `ctx.executive_summary` from all sections.
- `REPORT_OUTPUT`: create the standard Excel artifact.

`SECTION_SUMMARY` and `CONSOLIDATED_SUMMARY` are domain report nodes, not generic LLM wrappers. Keep them for surveillance reports because they compute facts, preserve section structure, and feed `REPORT_OUTPUT`.

## Data Source Rules

Use only exact columns from the live `Data Source Column Schemas` block in the system prompt. That block is generated from `DataSourceRegistry`; do not copy column lists into this skill.

Semantic tags are hints only. In workflow config, prompt refs, field bindings, and conditions, write physical column names.

Hard rule: every `hs_execution` query must include `trade_version:1`.

## Recommended High-Value Patterns

### FX Front-Running Evidence Agent
Use:
`TIME_WINDOW`, `EXECUTION_DATA_COLLECTOR`, `MARKET_DATA_COLLECTOR`, `COMMS_COLLECTOR`, `SIGNAL_CALCULATOR(FRONT_RUNNING)`, agent-layer nodes, `SECTION_SUMMARY`, `CONSOLIDATED_SUMMARY`, `REPORT_OUTPUT`.

### Fixed-Income Wash Trade Agent
Use:
orders + executions + comms, `FEATURE_ENGINE` for `signed_notional`, `SIGNAL_CALCULATOR(WASH_TRADE)`, critic/evaluator loop, report nodes.

### Spoofing / Layering Triage Agent
Use:
orders, `GROUP_BY` by `venue`/`book`, `MAP` for per-group analysis, `SIGNAL_CALCULATOR(SPOOFING|LAYERING)`, critic/evaluator loop, report nodes.

### Cross-Source Evidence Completeness Agent
Use:
all collectors, `data_quality_checks` through `TOOL_EXECUTOR`, `LLM_CRITIC`, `LLM_EVALUATOR`, `LLM_SYNTHESIZER`, and optional `REPORT_OUTPUT`.

Recommended wiring:
- Collect `client_orders`, `executions`, `market_data`, and `comms`.
- Run `DATA_REDUCER` on large datasets before LLM nodes.
- Run one `TOOL_EXECUTOR` quality check per dataset using `args.input_name`.
- Critique the combined evidence with `LLM_CRITIC` using row-count refs (`{client_orders.@row_count}` etc.) and DQ result refs (`{context.client_orders_dq_results}` etc.).
- Set `LLM_EVALUATOR.validation_key` to the critic output name.
- Set `LLM_SYNTHESIZER.prompt_template` to include the critic and evaluator outputs.

## Maintenance Rule
Whenever a node is added/removed/renamed, a node config changes, or a data source schema changes:

1. Update this skill if workflow composition guidance, data-source usage rules, or node usage rules changed.
2. Update `backend/data_sources/metadata/*.yaml` for data-source column changes; the Copilot prompt reads columns from the registry, not from this skill.
3. Run `python backend/scripts/gen_artifacts.py`.
4. Commit the regenerated artifacts: `backend/contracts/node_contracts.json`, `backend/engine/node_type_ids.py`, `frontend/src/nodes/generated.ts`, and `node_detail.md`.

## Node Inventory Checklist
This skill intentionally names every registered node type so tests can catch drift when nodes are added, removed, or renamed:

`ACTION_VALIDATOR`, `AGGREGATOR_NODE`, `ALERT_TRIGGER`, `COMMS_COLLECTOR`, `CONSOLIDATED_SUMMARY`, `DATA_HIGHLIGHTER`, `DATA_REDUCER`, `DECISION_RULE`, `ERROR_HANDLER`, `EXECUTION_DATA_COLLECTOR`, `EXTRACT_LIST`, `EXTRACT_SCALAR`, `FEATURE_ENGINE`, `GROUP_BY`, `GUARDRAIL`, `LLM_ACTION`, `LLM_CONTEXTUALIZER`, `LLM_CRITIC`, `LLM_EVALUATOR`, `LLM_PLANNER`, `LLM_SYNTHESIZER`, `LOOP_CONTROLLER`, `MAP`, `MARKET_DATA_COLLECTOR`, `ORACLE_DATA_COLLECTOR`, `PLAN_VALIDATOR`, `REPORT_OUTPUT`, `SECTION_SUMMARY`, `SIGNAL_CALCULATOR`, `STATE_MANAGER`, `TIME_WINDOW`, `TOOL_EXECUTOR`.

## Data Source Inventory Checklist
This skill intentionally names every logical and concrete data source so tests can catch drift when source metadata changes:

- Logical sources: `trades`, `market`, `comms`, `oracle`, `signals`
- Concrete trade sources: `hs_client_order`, `hs_execution`, `hs_trades`, `hs_orders_and_executions`, `hs_quotes`
- Concrete market sources: `EBS`, `Mercury`
- Concrete comms sources: `oculus`
- Concrete oracle sources: `oracle_orders`, `oracle_executions`
- Signal source: `SIGNAL_CALCULATOR`
