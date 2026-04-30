# Node Contract Audit

This document audits each node as a product contract, not just as code.
For every node, the YAML spec, Python handler, fixed runtime inputs, fixed
runtime outputs, and data-source field expectations must agree.

The target UX is similar to n8n / sim.ai:

- show only the config fields relevant to the selected mode;
- prefer dropdowns, column pickers, chips, and checkboxes over raw JSON;
- let users select from real upstream dataset columns where possible;
- avoid forcing users to fill implementation details that can be inferred;
- keep the YAML contract precise enough for validation, docs, and Copilot.

## Audit Checklist For Each Node

For each node, capture:

- YAML identity: `type_id`, description, palette group, input ports, output ports, params, semantics, constraints.
- Python handler contract: exact config keys read, datasets read from `ctx.datasets`, scalar values read from `ctx.values`, sections/text/report fields written.
- YAML vs Python drift: missing params, unused params, params with different names, wrong required flags, wrong defaults, undocumented output shape.
- Data-source logic: whether column names should come from `backend/data_sources/metadata/*.yaml`, upstream derived columns, or fixed internal columns.
- UX logic: fields that should be dropdowns, mode-dependent panels, column multi-selects, chips, checkboxes, or hidden advanced controls.
- Validation gaps: things the validator can currently catch vs things users can misconfigure silently.
- Recommended contract: the smallest functional input/output/config surface that gives the user enough control.

## Node 1: `SECTION_SUMMARY`

Files reviewed:

- `backend/engine/nodes/section_summary.yaml`
- `backend/engine/nodes/section_summary.py`
- `backend/engine/prompt_context.py`
- `backend/engine/refs.py`
- `backend/engine/validator.py`
- `backend/data_sources/metadata/trades.yaml`
- `backend/data_sources/metadata/comms.yaml`
- `backend/data_sources/metadata/signals.yaml`

### Functional Purpose

`SECTION_SUMMARY` turns one upstream DataFrame into a report section stored in
`ctx.sections[section_name]`. It supports three distinct authoring styles:

- `templated`: compute simple stats from selected columns and inject `{stats}` into an LLM prompt.
- `fact_pack_llm`: compute named facts, inject them as JSON via `{facts}`, and retry once if required fact values are missing from the narrative.
- `event_narrative`: sort rows, render selected rows through an event template, inject `{events}` into an LLM prompt.

The node is generic: it can summarize trade rows, communications, signal output,
or enriched derived datasets. Because of that, the best UX depends heavily on
the selected `input_name` and its resolved upstream columns.

### Current YAML Contract

Inputs declared in YAML:

- `dataset`, type `dataframe`, described as any DataFrame referenced by `input_name`.
- `context`, type `object`, optional, described as `trader_id`, `currency_pair`, `disposition` consumed by prompt templates.

Output declared in YAML:

- `section`, type `object`, stored at `ctx.sections[{section_name}]`.
- Required keys are `name`, `stats`, `narrative`, `dataset`.

Params declared in YAML:

- `section_name`: required string.
- `input_name`: required `input_ref`.
- `mode`: enum, default `templated`, values `templated`, `fact_pack_llm`, `event_narrative`.
- `field_bindings`: array, default `[]`, used in `templated`.
- `facts`: array, default `[]`, used in `fact_pack_llm`.
- `required_facts`: `string_list`, default `[]`, used in `fact_pack_llm`.
- `sort_by`: string, default `""`, used in `event_narrative`.
- `event_template`: string, default `""`, used in `event_narrative`.
- `max_events`: integer, default `40`, used in `event_narrative`.
- `llm_prompt_template`: string textarea.
- `prompt_context`: object, default `{}`.

### Current Python Contract

Config keys read by Python:

- Common: `section_name`, `input_name`, `mode`, `llm_prompt_template`, `prompt_context`.
- `templated`: `field_bindings`.
- `fact_pack_llm`: `facts`, `required_facts`.
- `event_narrative`: `sort_by`, `event_template`, `max_events`.

Fixed runtime inputs read by Python:

- `ctx.datasets[input_name]` is the actual DataFrame input.
- `ctx.values["disposition"]`, `ctx.values["trader_id"]`, and `ctx.values["currency_pair"]` are exposed as prompt slots with fallback defaults.
- `prompt_context` can read arbitrary datasets and context values through the shared reference resolver.

Fixed runtime output written by Python:

- `ctx.sections[section_name] = {"name", "stats", "narrative", "dataset"}`.
- No `ctx.datasets`, `ctx.values`, `ctx.executive_summary`, or file output is produced.

Mode outputs:

- `templated` stats include `row_count`, configured aggregations, plus automatic `signal_hits` from `_signal_flag` and `comm_keyword_hits` from `_keyword_hit` when those columns exist.
- `fact_pack_llm` stats include `row_count` plus every configured fact by name.
- `event_narrative` stats include `row_count` and `event_count`.

### YAML vs Python Findings

Severity: High

- `facts[].agg = "row_count"` is implemented in Python but functionally broken for the natural no-column case. `_compute_fact()` first returns `None` when `column` is missing from `df.columns`, so `row_count` only works if the user also supplies any existing column. This is illogical for a dataset-level reducer.
- `facts[].column` is not validated against the resolved input dataset. `field_bindings[].field` has validator support, but `facts[].column`, `sort_by`, and placeholders inside `event_template` can silently fail or produce `None` / missing events.
- `prompt_context.vars` examples can imply expression support, but `resolve_vars()` only resolves whole refs like `{signals._signal_score.max}` or does string substitution. An expression like `abs({context.net_notional}) / {context.total_abs_notional}` becomes a string, not a computed number.

Severity: Medium

- YAML declares an input port named `dataset`, but Python binds the DataFrame through config key `input_name`. The description explains this, but the port itself has no `source_config_key: input_name`, so the typed port contract is less precise than the handler.
- YAML declares an optional `context` input port, but Python does not receive a separate context object from a wire. It reads the global `RunContext`. This is conceptually true but can confuse a node-builder UI because users may think they need to wire context.
- All mode-specific params are always visible in YAML. This gives a poor user experience: users in `templated` mode see `facts`, `required_facts`, `sort_by`, `event_template`, and `max_events`, even though those fields do nothing.
- `field_bindings` and `facts` are raw arrays without item-level schema. The UI cannot know that `field_bindings[].agg` should be a dropdown, that `facts[].name` should drive `required_facts`, or that `facts[].column` should be a column picker.
- `event_template` is a raw string even though it should be assembled from selected columns or helper chips. Users must guess exact column names and Python format syntax.

Severity: Low

- YAML constraint says `LLM model: claude-sonnet-4-6`, while Python calls `get_default_adapter()`. The actual model is adapter/config dependent, not guaranteed by this node.
- YAML description says `context` contains `trader_id`, `currency_pair`, and `disposition`, but Python also supports `{context.<key>}` references through `refs.py` and direct slots `{trader_id}`, `{currency_pair}`, `{disposition}`. The prompt surface is richer than the YAML says.
- `templated` mode automatically adds `_signal_flag` and `_keyword_hit` stats, but YAML does not document these implicit stats.

### Data-Source Field Logic

`SECTION_SUMMARY` should not have fixed required data-source columns because it
can summarize any upstream DataFrame. Instead, it should dynamically derive
available fields from `input_name`:

- For collector outputs, use the matching metadata registry source: `trades`, `market`, `comms`, `oracle`.
- For `SIGNAL_CALCULATOR` outputs, include standard signal columns from `signals.yaml`: `_signal_flag`, `_signal_score`, `_signal_reason`, `_signal_type`, `_signal_window`.
- For transformed/enriched outputs, include pass-through upstream columns plus derived columns from `FEATURE_ENGINE`, `SIGNAL_CALCULATOR`, and `DATA_HIGHLIGHTER`.
- For communications, surface `timestamp`, `user`, `display_post`, `event_type`, `_keyword_hit`, `_matched_keywords`.
- For execution/trade rows, surface concrete columns like `exec_id`, `order_id`, `trader_id`, `currency_pair`, `exec_time`, `side`, `exec_quantity`, `exec_price`, `venue`, `counterparty`, `notional_usd`, `signed_notional` when present.

The current validator already traces columns for `field_bindings`; the same
lineage logic should be reused for `facts[].column`, `sort_by`, and optionally
template placeholder checks.

### Recommended UX Contract

Common fields:

- `section_name`: required text, preferably auto-suggested from node label.
- `input_name`: required upstream dataset dropdown.
- `mode`: required dropdown.
- `llm_prompt_template`: textarea, with mode-specific default template.
- `prompt_context`: advanced section, collapsed by default.

When `mode = templated`, show:

- `field_bindings`: repeatable stat builder.
- Each row should have `field` as a column dropdown and `agg` as a dropdown.
- Supported aggs should be `count`, `sum`, `mean`, `nunique`, `max`, `min`.
- Add a convenience checkbox group for implicit stats when available:
  `include row count`, `include signal hits`, `include communication keyword hits`.
- Hide `facts`, `required_facts`, `sort_by`, `event_template`, `max_events`.

When `mode = fact_pack_llm`, show:

- `facts`: repeatable named fact builder.
- Each row should have `name`, `column`, and `agg`.
- `column` should be optional only for dataset-level aggs like `row_count`.
- `agg` should be a dropdown with `count`, `sum`, `mean`, `nunique`, `max`, `min`, `unique_values`, `row_count`.
- `count_where_*` should not require users to type a magic string. Model it as `agg = count_where`, plus a `value` field populated from unique values when feasible.
- `required_facts`: checkbox multi-select generated from `facts[].name`, with a `select all` option.
- Hide `field_bindings`, `sort_by`, `event_template`, `max_events`.

When `mode = event_narrative`, show:

- `sort_by`: column dropdown, biased toward time semantic columns.
- `max_events`: numeric limit.
- `event fields`: multi-select columns to include in the event line.
- `event_template`: advanced override, generated from selected event fields by default.
- Hide `field_bindings`, `facts`, `required_facts`.

Prompt template helpers:

- Insert chips for `{stats}`, `{facts}`, or `{events}` depending on mode.
- Insert common context chips: `{trader_id}`, `{currency_pair}`, `{disposition}`.
- Insert advanced ref chips: `{dataset.column.sum}`, `{dataset.@row_count}`, `{context.key}`.
- Warn that `prompt_context.vars` is ref/string substitution, not a general expression engine.

### Recommended YAML Contract Changes

The current YAML can remain valid, but it should become more expressive for UI
and validation:

- Add `source_config_key: input_name` to the `dataset` input port.
- Consider removing the `context` input port or marking it as an implicit runtime context, not a wireable port.
- Add mode-conditional UI metadata so only relevant params render for each mode.
- Add item schemas for `field_bindings` and `facts`.
- Add column-picker hints for `field_bindings[].field`, `facts[].column`, and `sort_by`.
- Add `required_facts` dependency on `facts[].name`.
- Add a truthful LLM constraint such as "Uses the default LLM adapter with temperature 0.2 and max_output_tokens 600."

### Recommended Python Changes

Fixes:

- Handle `row_count` before checking `column in df.columns`.
- Validate or warn on unknown `facts[].column`, `sort_by`, and `event_template` placeholders.
- Consider returning structured metadata in the section object such as `mode` and `input_name` if downstream report/debug views need it.

Product refinements:

- Make implicit stats configurable rather than always appended in `templated`.
- Treat `count_where_*` as a backward-compatible parser, but expose a structured `count_where` config shape to the UI.
- Provide mode-specific default prompt templates in YAML or a frontend manifest so users are not forced to write prompts from scratch.

### Proposed Minimal Contract

Inputs:

- One required DataFrame input resolved by `input_name`.
- No separate wireable context input; context should be documented as implicit runtime state.

Outputs:

- One section object stored at `ctx.sections[section_name]`.
- Required keys: `name`, `stats`, `narrative`, `dataset`.
- Optional useful keys: `mode`, `prompt_inputs`.

Config:

- Always required: `section_name`, `input_name`, `mode`.
- Always optional: `llm_prompt_template`, `prompt_context`.
- Mode-specific:
  - `templated`: `field_bindings`, implicit stat toggles.
  - `fact_pack_llm`: `facts`, `required_facts`.
  - `event_narrative`: `sort_by`, `event_fields` or `event_template`, `max_events`.

### Verdict

`SECTION_SUMMARY` is functionally powerful, but its contract is too raw for a
workflow-builder UX. The implementation and YAML broadly agree on major config
keys, but they are out of sync in important functional details: fact validation,
dataset-level row count, mode-specific visibility, implicit context, and typed
item schemas. This node should be treated as a priority cleanup because it is
the report narrative node users will configure repeatedly.

## Top-Down Rebuild View

This section looks at the system as if the node library were being rebuilt from
scratch for an n8n / sim.ai style workflow builder, using the existing FX FRO,
FISL, FI wash-trade, and chassis workflows as the product requirements.

### Workflow Use Cases Observed

The real workflows use the same chassis for multiple surveillance scenarios:

- FX front-running: alert context, optional time window, Solr order/execution collection, comms, market ticks, execution features, front-running signal, decision, row highlights, section summaries, executive summary, Excel report.
- FISL spoof/layering: alert context, time window, Solr order collection, group orders by venue / instance / book, nested `MAP`, feature engineering for order-book ladder, spoofing signal, decision rules, highlights, summaries, dynamic report tabs.
- FI wash trade: order and execution collection, comms keyword scan, feature derivation, wash-trade signal, decision, highlight, narrative, report.
- Chassis proofs: `TIME_WINDOW`, `GROUP_BY`, `MAP`, `EXTRACT_SCALAR`, and dynamic report tabs are core primitives, not scenario-specific conveniences.

The product principle should be: node definitions describe the user-facing
contract, while Python handlers implement only the runtime mechanics. Users
should configure business intent, not internal `ctx` plumbing.

### Desired Contract Model

Every node should have four explicitly separated contracts:

- YAML user contract: name, description, palette group, wireable inputs, wireable outputs, config params, enum values, item schemas, conditional visibility, column picker hints, validation hints.
- Python runtime contract: exact config keys read, exact `ctx.datasets` / `ctx.values` / `ctx.sections` reads, exact writes, exceptions, default behavior.
- Fixed variable inputs: implicit runtime keys that are not user-wired, such as `ctx.values.trader_id`, `ctx.values.disposition`, `ctx.alert_payload`, `ctx.sections`, or the standard signal columns.
- Fixed variable outputs: stable context or dataset fields written regardless of config, such as `_signal_flag`, `ctx.values.flag_count`, `ctx.report_path`, or `_highlight_colour`.

For UI, YAML needs more than `type`. It needs:

- `visible_if` for mode-specific fields.
- `item_schema` for array params.
- `source_config_key` on dataframe ports that are resolved by params like `input_name`.
- `column_picker` metadata for params that reference DataFrame columns.
- `ref_picker` metadata for params that accept `{dataset.column.agg}` or `{context.key}` references.
- `advanced: true` for dangerous or low-frequency fields such as Python scripts, raw expressions, and mock CSV paths.
- `dynamic_options_from` for values sourced from data-source metadata, upstream dataset columns, `facts[].name`, or `ctx.values` keys.

### Ideal Node Contracts

#### `ALERT_TRIGGER`

Current shape:

- YAML declares `alert_fields` and an output object `context_keys`.
- Python reads `ctx.alert_payload`, binds declared alert fields, also binds `extras.standard_alert_fields`, then writes `ctx.values.context_keys`.
- Fixed input is the workflow invocation payload.
- Fixed outputs are individual `ctx.values` keys plus `ctx.values.context_keys`.

Drift / concern:

- The YAML says `context_keys` is the output, but the real useful outputs are many dynamic context keys.
- `alert_fields` is raw JSON; the UI cannot guide field names, required flags, or payload examples.

Ideal rebuild:

- Keep this as the only entry node.
- YAML should model `alert_fields` as a repeatable schema: `name`, `type`, `required`, `description`, `default`.
- Standard fields should be visible as checkbox presets: `trader_id`, `book`, `alert_date`, `currency_pair`, `alert_id`, `entity`, `desk`, `event_time`.
- No dataset ports.
- Fixed Python output should be documented as `ctx.values[<field_name>]` for every resolved alert field and `ctx.values.context_keys`.
- UI should show this as “Alert Payload Schema”, not as arbitrary config JSON.

#### `TIME_WINDOW`

Current shape:

- YAML params match Python: `event_time_key`, `end_time_key`, literals, pre/post minutes, `output_name`.
- Python reads `ctx.values[event_time_key]` / `ctx.values[end_time_key]` or literals and writes `ctx.values[output_name]`.
- Fixed output object is `{start_time, end_time, buffer_minutes}`.

Drift / concern:

- YAML declares a `context` input port, but the node reads implicit `RunContext`.
- `output_name` is marked required even though Python defaults to `window`.
- Event/end keys are plain strings, not dropdowns from alert fields / context keys.

Ideal rebuild:

- Treat context as implicit runtime input, not a wireable port.
- Params should be `anchor_mode` enum: `context_key` or `literal`.
- Show `event_time_key` / `end_time_key` only in `context_key` mode; show literals only in `literal` mode.
- `event_time_key` and `end_time_key` should be context-key dropdowns.
- `pre_minutes` and `post_minutes` should be numeric controls with non-negative validation.
- Output port should state `store_at: ctx.values[{output_name}]`.

#### `EXECUTION_DATA_COLLECTOR`

Current shape:

- YAML declares Solr `source`, `query_template`, `output_name`, `window_key`, `trader_filter_key`, `loop_over_books`, `books`, `mock_csv_path`.
- Python reads these keys, resolves the query for audit, enforces `trade_version:1` for `hs_execution`, generates/loads rows, filters trader/window, loops books, writes `ctx.datasets[output_name]`, `ctx.values[{output_name}_count]`, and `ctx.values[_{output_name}_resolved_query]`.
- Fixed input is implicit context plus optional `ctx.values[window_key]`.
- Fixed output schema is source-dependent from `trades.yaml`.

Drift / concern:

- YAML output port is named `executions`, but the node collects orders, executions, trades, quotes, and combined shapes.
- `window_key` exists and is used, but YAML does not declare it as a context-value picker.
- `query_template` asks users to write Solr syntax directly; this is powerful but poor primary UX.
- `loop_over_books` and `books` should be conditionally visible.

Ideal rebuild:

- Rename display contract to `SOLR_DATA_COLLECTOR` or keep type ID but display as “Solr Data Collector”.
- `source` dropdown must come from `trades.yaml`.
- Primary UI should offer query builder controls: trader filter, book filter, instrument/currency filter, date/window filter. Keep raw `query_template` as advanced override.
- `window_key` should be optional dropdown of `TIME_WINDOW` outputs.
- `trader_filter_key` should be context-key dropdown.
- `books` should be chips visible only when `loop_over_books` is true.
- Output port should be generic `rows`, with `schema_by_source` from metadata.
- Fixed outputs should include dataset, count scalar, resolved query string, and provenance.

#### `COMMS_COLLECTOR`

Current shape:

- YAML declares `query_template`, `keywords`, `keyword_categories`, `emit_hits_only`, `output_name`, `mock_csv_path`.
- Python reads all except it does not actually resolve or store `query_template`; it uses mock/CSV data and keyword scans `display_post`.
- Fixed outputs are `ctx.datasets[output_name]`, `ctx.values[{output_name}_keyword_hits]`, and optionally `ctx.datasets[{output_name}_hits]`.
- Output columns always include `user`, `timestamp`, `display_post`, `event_type`, `_keyword_hit`, `_matched_keywords`; category mode adds `_matched_categories` and `_hit_<category>`.

Drift / concern:

- YAML does not declare optional sibling dataset output for `{output_name}_hits`.
- `_matched_categories` and `_hit_<category>` are dynamic but not represented in output schema.
- `query_template` is declared but currently not used for filtering in Python.

Ideal rebuild:

- Source should be explicit, even if currently only `oculus`.
- Primary UI should have trader/context filter, time/window picker, keyword chips, and category builder.
- `emit_hits_only` should show a preview of the generated sibling dataset name.
- Output ports should include `comms` and conditional `hits`.
- Dynamic category columns should be declared as generated columns in YAML metadata.
- Python should either use `query_template` consistently or mark it as audit-only / future connector config.

#### `MARKET_DATA_COLLECTOR`

Current shape:

- YAML declares `source`, `query_template`, `output_name`, `mock_csv_path`.
- Python reads `source`, `output_name`, `mock_csv_path`, but does not read `query_template`.
- Python comments say it honors `window_key`, but the handler does not currently call the shared window filter.
- Fixed outputs are tick DataFrame and `{output_name}_tick_count`.

Drift / concern:

- `window_key` is used by workflows and described in comments, but missing from YAML and Python.
- `query_template` is required in YAML but ignored by Python.

Ideal rebuild:

- Add `window_key` as optional dropdown of `TIME_WINDOW` outputs and implement filtering on `timestamp`.
- `source` dropdown from `market.yaml`.
- Replace primary raw `query_template` with `symbol_ref` / `instrument_ref` and optional raw query advanced override.
- Output schema should be sourced from `market.yaml`.
- Fixed outputs should include dataset, tick count, resolved query, and provenance.

#### `ORACLE_DATA_COLLECTOR`

Current shape:

- YAML declares `source`, optional `query_template`, `output_name`, `mock_csv_path`, and source-keyed output columns.
- Python reads these fields and generates rows from `oracle.yaml`.
- Python writes dataset, provenance, count, and resolved query.

Drift / concern:

- Python calls `ctx.inject_template(raw_query)`, but `RunContext` currently exposes `get()` and `set()`, not `inject_template()`. Other nodes use `resolve_template()`.
- YAML source schemas duplicate metadata that also lives in `oracle.yaml`.
- No `window_key` even though Oracle extracts may also need time filtering.

Ideal rebuild:

- Use `oracle.yaml` as the only source schema.
- `source` dropdown from `oracle.yaml`.
- Query builder should be table/source + filters; raw SQL template should be advanced.
- Add optional `window_key` and time-column mapping per source.
- Python should use `resolve_template(raw_query, ctx)`.
- Fixed outputs should match Solr collector: dataset, count, resolved query, provenance.

#### `FEATURE_ENGINE`

Current shape:

- YAML declares `input_name`, `output_name`, and raw `ops` array.
- Python supports `window_bucket`, `time_slice`, `groupby_agg`, `pivot`, `rolling`, `derive`, `apply_expr`, `rename`, and `lifecycle_event`.
- Python writes final `ctx.datasets[output_name]`; ops with `as` publish intermediate datasets.

Drift / concern:

- YAML says output is one `features` DataFrame, but Python can publish multiple intermediate datasets via `as`.
- `ops` is raw JSON and has no item-level schema, so users must know op-specific keys.
- Column fields inside ops are not validated through a common column lineage system.
- `apply_expr` is an eval surface and should not be a normal user-facing path.

Ideal rebuild:

- UI should be a pipeline builder: choose operation type, then render op-specific fields.
- Every column reference should be a column picker from the current working schema.
- `groupby_agg` should use multi-select group columns and reducer dropdowns.
- `pivot` should use index/columns/values pickers plus agg dropdown.
- `derive` should offer expression chips and validation; `apply_expr` should be advanced/admin-only.
- Output contract should include final dataset and zero-or-more named intermediate datasets from `ops[].as`.
- Python should return/publish provenance of derived columns so downstream column pickers can include them.

#### `SIGNAL_CALCULATOR`

Current shape:

- YAML declares `mode`, `signal_type`, `input_name`, `output_name`, `params`, `script_path`, `script_content`.
- Python supports built-ins `FRONT_RUNNING`, `WASH_TRADE`, `SPOOFING`, `LAYERING`, plus gated `upload_script`.
- Fixed output columns are `_signal_flag`, `_signal_score`, `_signal_reason`, `_signal_type`, `_signal_window`.
- Python writes `ctx.datasets[output_name]` and `ctx.values[{output_name}_flag_count]`.

Drift / concern:

- YAML exposes `upload_script` even though product guardrails say LLM-authored workflows must not use it unless explicitly enabled.
- Built-in `params` is raw object, not signal-type-specific form fields.
- Signal built-ins have implicit required columns that YAML does not declare per signal type.

Ideal rebuild:

- Default UI mode should only show built-in `configure`.
- `upload_script` should be hidden unless server capability says it is enabled.
- `signal_type` should drive conditional params:
  - `FRONT_RUNNING`: `window_minutes`, `price_move_threshold`; requires `exec_time`, `exec_price`.
  - `WASH_TRADE`: `window_minutes`, `ratio_threshold`; requires `side`, `exec_quantity`.
  - `SPOOFING`: `cancel_ratio_threshold`, `window`; requires `status`.
  - `LAYERING`: `min_layers`, `window`; requires `order_type`, `side`.
- Output schema should always advertise pass-through input columns plus the five signal columns.
- Fixed outputs should include flag count and maybe max/mean signal score for easier downstream decisions.

#### `DATA_HIGHLIGHTER`

Current shape:

- YAML declares `input_name`, `output_name`, and raw `rules`.
- Python reads dataset, initializes `_highlight_colour` and `_highlight_label`, evaluates each condition after ref substitution, and writes highlighted DataFrame.
- Fixed output columns are `_highlight_colour`, `_highlight_label`.

Drift / concern:

- YAML and Python mostly agree.
- Rules are raw expression objects; users need to know pandas eval syntax.
- Bad rules are skipped at runtime, but validation cannot reliably warn before execution.

Ideal rebuild:

- Keep expression mode as advanced.
- Primary UI should be a rule builder: column, operator, value/ref, colour, label.
- Provide presets for `_signal_flag`, `_keyword_hit`, `side`, `status`.
- Use column picker and ref picker for condition operands.
- Output name should default to `{input_name}_highlighted`.
- Fixed output schema should include the two highlight columns.

#### `DECISION_RULE`

Current shape:

- YAML declares `input_name`, thresholds, optional `rules`, `severity_map`, `output_branches`.
- Python reads `input_name`, computes flag count from `_signal_flag` or count scalar, stores `flag_count`, then either evaluates first matching rule or threshold ladder.
- Fixed outputs are `ctx.disposition`, `ctx.output_branch`, and context values `disposition`, `output_branch`, `severity`, `score`, `matched_rule`, `flag_count`.

Drift / concern:

- YAML says default `escalate_threshold` is `1`, Python defaults to `5`.
- YAML output port `severity` does not declare `store_at`, though Python stores it in `ctx.values.severity`.
- YAML has no explicit `mode`, but Python switches mode based on whether `rules` is non-empty.

Ideal rebuild:

- Add explicit `mode`: `threshold` or `rules`.
- Show threshold fields only in threshold mode; show rule builder only in rules mode.
- `rules[].when` should be a ref/comparison builder, not raw text by default.
- `severity_map` should be a simple disposition-to-severity selector.
- Fix YAML/Python default mismatch for `escalate_threshold`.
- Fixed outputs should be fully declared with `store_at`.

#### `GROUP_BY`

Current shape:

- YAML declares `input_name`, `group_by_column`, `output_prefix`, optional `keys_output_name`, `dropna`, `order`.
- Python reads these, writes one dataset per key as `{output_prefix}_{key}` and writes `ctx.values[keys_output_name] = {"values": keys}`.

Drift / concern:

- `input_name` is `string` in YAML but should be `input_ref`.
- `group_by_column` is plain string but should be a column picker.
- Output datasets are dynamic and only described conceptually.

Ideal rebuild:

- `input_name` should be `input_ref`.
- `group_by_column` should be a column picker.
- `output_prefix` should default to `{input_name}_by_{group_by_column}`.
- `keys_output_name` should default visibly to `{input_name}_{group_by_column}_keys`.
- Output contract should declare one object/list output of keys and a dynamic dataset family.
- Add key sanitization or a `key_slug_mode` because raw key values become dataset names.

#### `MAP`

Current shape:

- YAML declares `keys_key`, `iteration_ctx_key`, optional `dataset_prefix`, `iteration_dataset_alias`, `sub_workflow`, collections, `output_name`.
- Python reads a `{values: [...]}` object from `ctx.values[keys_key]`, forks child context per key, aliases grouped dataset when configured, executes nested workflow, collects configured values/datasets, and writes `ctx.values[output_name]`.
- Fixed dynamic outputs include collected top-level datasets named `{output_name}_{key}_{dataset_name}`.

Drift / concern:

- `keys_key` is a raw string, not a dropdown of `EXTRACT_LIST` / `GROUP_BY` outputs.
- `sub_workflow` is a raw object; this needs a nested visual editor.
- Dynamic dataset naming is central to reports but not strongly represented in YAML.

Ideal rebuild:

- `keys_key` should be a value-ref dropdown constrained to `{values:[...]}` objects.
- If `dataset_prefix` is set, `iteration_dataset_alias` should be required.
- `collect_values` should be multi-select from child workflow outputs.
- `collect_datasets` should be multi-select from child dataset outputs.
- UI should show the generated dynamic output naming scheme before run.
- Output contract should explicitly define aggregate object and dynamic dataset family.

#### `EXTRACT_LIST`

Current shape:

- YAML declares `input_name`, `column`, `output_name`, `order`, `dropna`.
- Python reads a DataFrame column and writes `ctx.values[output_name] = {"values": values}`.

Drift / concern:

- YAML and Python align.
- `column` is plain string, not column picker.

Ideal rebuild:

- `input_name` should be input dropdown.
- `column` should be column picker.
- `output_name` should default to `{input_name}_{column}_values`.
- Output object schema should be fixed: `{values: list}`.
- UI should show this as “Build Fan-Out Keys”.

#### `EXTRACT_SCALAR`

Current shape:

- YAML declares `input_name`, `column`, `reducer`, `output_name`, `fail_on_ambiguous`.
- Python reads a DataFrame column and writes one scalar to `ctx.values[output_name]`.

Drift / concern:

- YAML and Python align.
- `column` is plain string, not column picker.
- Reducer list lacks `row_count`; users must pick a column just to count rows.

Ideal rebuild:

- `input_name` should be input dropdown.
- `column` should be column picker, hidden/optional when reducer is `row_count`.
- Add `row_count`, `any`, and `all` if used in decision/report logic.
- Output name should default to `{input_name}_{column}_{reducer}`.

#### `SECTION_SUMMARY`

Ideal rebuild summary:

- Keep three modes but make them first-class conditional forms.
- Use column pickers for stat/fact/event fields.
- Use fact-name checkbox multiselect for `required_facts`.
- Add structured `count_where` instead of magic `count_where_value` strings.
- Treat context as implicit, not wireable.
- Validate `facts[].column`, `sort_by`, event placeholders, and prompt refs.
- Fix `row_count` fact behavior.

The detailed node audit above remains the canonical per-field review for this node.

#### `CONSOLIDATED_SUMMARY`

Current shape:

- YAML declares `llm_prompt_template` and `prompt_context`.
- Python reads all `ctx.sections`, `ctx.values.trader_id`, `currency_pair`, `disposition`, `flag_count`, and writes `ctx.executive_summary` plus `ctx.values.executive_summary`.

Drift / concern:

- YAML says sections are an input port, but Python reads global `ctx.sections`.
- Workflow examples include `use_section_facts`, but YAML/Python do not implement it.
- YAML LLM constraint hard-codes model name while Python uses default adapter.

Ideal rebuild:

- Treat sections and context as implicit runtime inputs.
- Add optional `section_order` and `include_sections` controls if report ordering matters.
- Either implement `use_section_facts` or remove it from workflows.
- Prompt helper chips should include `{section_text}`, `{trader_id}`, `{currency_pair}`, `{disposition}`, `{flag_count}`, `{severity}`.
- Fixed output should be `ctx.executive_summary` and `ctx.values.executive_summary`.

#### `REPORT_OUTPUT`

Current shape:

- YAML declares `output_path` and `tabs`.
- Python reads `output_path`, `tabs`, expands dynamic tabs from `expand_from`, writes cover, executive summary, section summaries, data tabs, then writes `ctx.report_path` and `ctx.values.report_path`.
- If `tabs` is empty, Python includes all datasets except `_highlighted` siblings.

Drift / concern:

- `summary_position` and `map_tab_sets` appear in older chassis workflows but are not in YAML/Python.
- YAML has `config_tags: [output_name]`, but this node has no `output_name`.
- Dynamic tab specs are raw objects; users must know `expand_from`, `as`, and dataset template syntax.

Ideal rebuild:

- Fix config tag to `output_path`.
- Model tabs as repeatable item schema with `tab_type`: `static`, `expand_from_ref`, `map_results`.
- Dataset should be a dropdown of upstream dataset outputs.
- `expand_from` should be a ref picker.
- Include-highlights should automatically offer the matching highlighted dataset.
- Add report sections toggles: cover, executive summary, section summaries, data tabs.
- Remove or implement legacy `summary_position` / `map_tab_sets`.

### Cross-Node Rebuild Priorities

Priority 1: Fix runtime/YAML drift that can break workflows.

- `ORACLE_DATA_COLLECTOR` should use `resolve_template()` instead of `ctx.inject_template()`.
- `MARKET_DATA_COLLECTOR` should either implement `window_key` or stop claiming it supports windows.
- `DECISION_RULE` YAML/Python threshold defaults should match.
- `SECTION_SUMMARY` should fix `row_count` facts and validate fact/event columns.
- `REPORT_OUTPUT` should remove or support legacy `map_tab_sets` and `summary_position`.

Priority 2: Make column and ref selection first-class.

- Add common metadata for `input_ref`, `column_picker`, `context_key_picker`, and `ref_picker`.
- Reuse validator lineage for every config field that references columns, not just `SECTION_SUMMARY.field_bindings`.
- Track derived columns from `FEATURE_ENGINE` and generated columns from `COMMS_COLLECTOR`, `SIGNAL_CALCULATOR`, and `DATA_HIGHLIGHTER`.

Priority 3: Replace raw arrays with item schemas.

- `FEATURE_ENGINE.ops`
- `DATA_HIGHLIGHTER.rules`
- `DECISION_RULE.rules`
- `SECTION_SUMMARY.field_bindings`
- `SECTION_SUMMARY.facts`
- `REPORT_OUTPUT.tabs`

Priority 4: Add mode-dependent UI.

- `SIGNAL_CALCULATOR.mode`
- `SIGNAL_CALCULATOR.signal_type`
- `SECTION_SUMMARY.mode`
- `DECISION_RULE.mode`
- `TIME_WINDOW.anchor_mode`
- `REPORT_OUTPUT.tab_type`
- `FEATURE_ENGINE.ops[].op`

Priority 5: Make implicit runtime context explicit in docs, not as fake wireable ports.

- `ctx.alert_payload`
- `ctx.values`
- `ctx.sections`
- `ctx.executive_summary`
- `ctx.report_path`
- dynamic dataset families from `GROUP_BY` and `MAP`

### Scratch-Rebuild Verdict

The current 17 nodes are the right high-level vocabulary. I would not add many
new nodes for FX FRO or FISL. The main rebuild should improve the node contract
language, not the node count:

- collectors should be metadata-driven source adapters;
- transform nodes should expose typed builders over raw JSON;
- signal and summary nodes should use mode-specific forms;
- report and map nodes should make dynamic outputs visible;
- validators should understand every column/ref-bearing config field.

That gives users the optimized builder experience: few enough nodes to learn,
but rich enough node definitions that they can configure workflows through
dropdowns, checkboxes, column pickers, and guided mode panels instead of hand
writing fragile JSON.
