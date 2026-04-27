# Node Detail

Generated from the live backend `NodeSpec` registry (`engine.registry.studio_manifest`).
This file documents every node: what it does, inputs, outputs, static UI metadata, and config parameters.

## Node Index

| Node | Display | Section | Use |
| --- | --- | --- | --- |
| `ALERT_TRIGGER` | Alert Trigger | `trigger` | Entry point — binds alert payload to context |
| `COMMS_COLLECTOR` | Oculus | `integrations` | Query Oculus comms with keyword scanning |
| `CONSOLIDATED_SUMMARY` | Consolidated Summary | `narrative` | LLM executive summary across all sections |
| `DATA_HIGHLIGHTER` | Data Highlighter | `transform` | Apply colour rules to dataset rows |
| `DECISION_RULE` | Decision Rule | `rule` | Evaluate flag_count or rules → ESCALATE/REVIEW/DISMISS + severity |
| `EXECUTION_DATA_COLLECTOR` | Solr Data Collector | `integrations` | Query Solr for client orders, executions, trades, and quotes |
| `EXTRACT_LIST` | Extract List | `transform` | Emit the unique values of a column as an ordered list — cascade primitive for fan-out keys. |
| `EXTRACT_SCALAR` | Extract Scalar | `transform` | Reduce a column of an upstream DataFrame to a single scalar (first, unique_single, max, min, count, sum, mean). |
| `FEATURE_ENGINE` | Feature Engine | `transform` | Compose feature transforms (window, slice, pivot, agg, rolling, derive) |
| `GROUP_BY` | Group By | `transform` | Split a dataset by column value into one DataFrame per group |
| `MAP` | Map | `transform` | Fan out a sub-workflow over a list of keys; aggregate results |
| `MARKET_DATA_COLLECTOR` | Mercury | `integrations` | Query EBS/Mercury tick data, normalise timestamps |
| `ORACLE_DATA_COLLECTOR` | Oracle Data Collector | `integrations` | Query Oracle surveillance warehouse order/execution extracts |
| `REPORT_OUTPUT` | Report Output | `output` | Generate Excel report with tabs & highlights |
| `SECTION_SUMMARY` | Section Summary | `narrative` | Aggregate stats + LLM narrative section |
| `SIGNAL_CALCULATOR` | Signal Calculator | `signal` | Compute signals — always outputs 5 columns |
| `TIME_WINDOW` | Time Window | `transform` | Expand an event time into a [start_time, end_time] window for downstream filtering. |

## `ALERT_TRIGGER` — Alert Trigger

**Use:** Entry point — binds alert payload to context

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `ALERT_TRIGGER` |
| Display name | Alert Trigger |
| UI section | `trigger` |
| Palette order | `0` |
| Color | `#7C3AED` |
| Icon | `Siren` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `alert_payload` | `object` | yes | JSON object passed at workflow invocation time. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `context_keys` | `object` | no | `ctx.values[context_keys]` | One context key per declared alert_field, e.g. trader_id, book, alert_date, currency_pair, alert_id. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `alert_fields` | `object` | no | `json` | `{}` |  | Map of field_name → type (string\|date\|number). Non-listed payload keys in extras.standard_alert_fields are still bound when present in the alert. |

**Constraints**

- Must be the first node (id=n01).
- No dataset inputs or outputs.

## `COMMS_COLLECTOR` — Oculus

**Use:** Query Oculus comms with keyword scanning

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `COMMS_COLLECTOR` |
| Display name | Oculus |
| UI section | `integrations` |
| Palette order | `10` |
| Color | `#059669` |
| Icon | `MessageSquareText` |
| Config tags | `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `context` | `object` | no | Context keys referenced in query_template as {context.xxx}. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `comms` | `dataframe` | no | `ctx.datasets[{output_name}]` | DataFrame with columns: user, timestamp, display_post, event_type, _keyword_hit, _matched_keywords. Stored under ctx.datasets[output_name]. | columns: `user`, `timestamp`, `display_post`, `event_type`, `_keyword_hit`, `_matched_keywords` |
| `keyword_hit_count` | `scalar` | yes | `ctx.values[{output_name}_keyword_hits]` | Total keyword hit count (int). Stored as {output_name}_keyword_hits. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `query_template` | `string` | yes | `textarea` |  |  | Oculus query with {context.xxx} placeholders. |
| `keywords` | `string_list` | no | `chips` | `[]` |  | Terms to scan in display_post. |
| `keyword_categories` | `object` | no | `json` | `{}` |  | Optional {category: [kw1, kw2, ...]} map. When present, each row gains a _matched_categories list plus one _hit_<cat> boolean column. Combined with plain `keywords` (both are scanned). |
| `emit_hits_only` | `boolean` | no | `checkbox` | `False` |  | Also publish ctx.datasets[f"{output_name}_hits"] containing only rows with at least one keyword match. Lets downstream SECTION_SUMMARY narrate just the suspicious subset. |
| `output_name` | `string` | yes | `text` | `comms` |  | Dataset name in ctx.datasets. |
| `mock_csv_path` | `string` | no | `text` | `""` |  | Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing. |

**Constraints**

- Always adds _keyword_hit (boolean) and _matched_keywords (list[str]) columns.
- Scans display_post field only.

## `CONSOLIDATED_SUMMARY` — Consolidated Summary

**Use:** LLM executive summary across all sections

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `CONSOLIDATED_SUMMARY` |
| Display name | Consolidated Summary |
| UI section | `narrative` |
| Palette order | `51` |
| Color | `#B45309` |
| Icon | `FileStack` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `sections` | `object` | yes | All section objects produced by upstream SECTION_SUMMARY nodes (context.sections). |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `executive_summary` | `text` | no | `ctx.executive_summary` | Multi-paragraph executive summary. Stored as context.executive_summary. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `llm_prompt_template` | `string` | no | `textarea` |  |  | Custom prompt with {section_text}, {trader_id}, {currency_pair}, {disposition}, {flag_count} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset\|mixed) {dataset}. Cross-dataset refs like {executions.notional.sum} resolve inline. Falls back to the built-in template when empty. |
| `prompt_context` | `object` | no | `json` | `{}` |  | Optional structured slot block: {mode: template\|dataset\|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. Same shape as SECTION_SUMMARY.prompt_context. |

**Constraints**

- LLM model: claude-sonnet-4-6, max_tokens: 1000.
- Must run after all SECTION_SUMMARY nodes.

## `DATA_HIGHLIGHTER` — Data Highlighter

**Use:** Apply colour rules to dataset rows

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `DATA_HIGHLIGHTER` |
| Display name | Data Highlighter |
| UI section | `transform` |
| Palette order | `21` |
| Color | `#9333EA` |
| Icon | `Highlighter` |
| Config tags | `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Any DataFrame referenced by input_name. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `highlighted` | `dataframe` | no | `ctx.datasets[{output_name}]` | Input DataFrame + _highlight_colour (hex) + _highlight_label (str). Stored under ctx.datasets[output_name]. | columns: `_highlight_colour`, `_highlight_label` |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Source dataset. |
| `output_name` | `string` | yes | `text` |  |  | Highlighted dataset name (convention: input_name + '_highlighted'). |
| `rules` | `array` | no | `json` | `[]` |  | Array of {condition, colour, label}. `condition` is a pandas.DataFrame.eval expression evaluated against the target dataset's rows. The condition may include `{ref}` placeholders that resolve to SCALAR values via the cross-dataset ref grammar BEFORE pandas eval — e.g. `notional > {context.peak_threshold}`, `bucket == {ladder.peak_bucket.first}`. `colour` is hex #RRGGBB. |

**Constraints**

- Conditions are evaluated with pandas DataFrame.eval after `{ref}` resolution.
- Rules are applied in order — last matching rule wins.
- Rows with no matching rule get colour #FFFFFF and empty label.
- Buggy rules (unresolved refs, syntax errors, missing columns) are skipped with a warning. The run continues.

## `DECISION_RULE` — Decision Rule

**Use:** Evaluate flag_count or rules → ESCALATE/REVIEW/DISMISS + severity

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `DECISION_RULE` |
| Display name | Decision Rule |
| UI section | `rule` |
| Palette order | `40` |
| Color | `#D97706` |
| Icon | `Gavel` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Signal DataFrame with _signal_flag column. | columns: `_signal_flag` |
| `flag_count` | `scalar` | no | Flag count from SIGNAL_CALCULATOR (read from ctx.values[{input_name}_flag_count] if the dataset isn't available). |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `disposition` | `text` | no | `ctx.disposition` | 'ESCALATE' \| 'REVIEW' \| 'DISMISS'. Stored as context.disposition. |  |
| `severity` | `text` | no | `` | 'CRITICAL' \| 'HIGH' \| 'MEDIUM' \| 'LOW'. Stored as context.severity. |  |
| `score` | `scalar` | no | `` | Normalised severity score in [0, 1]. Stored as context.score. |  |
| `flag_count` | `scalar` | no | `ctx.values[flag_count]` | Total signal hits (int). Stored as context.flag_count. |  |
| `output_branch` | `text` | no | `ctx.output_branch` | Branch name to route to. Stored as context.output_branch. |  |
| `matched_rule` | `text` | no | `` | Name of the rule that fired (rule mode only; empty in threshold mode). Stored as context.matched_rule. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Signal dataset name. |
| `escalate_threshold` | `integer` | no | `number` | `1` |  | flag_count >= this → ESCALATE (threshold mode). |
| `review_threshold` | `integer` | no | `number` | `1` |  | flag_count >= this → REVIEW (threshold mode). |
| `rules` | `array` | no | `json` | `[]` |  | Optional rules list, evaluated top-to-bottom; first match wins. Each rule: {name, when, severity?, disposition?}. `when` accepts `{ref}` (truthy test) or `{ref} OP literal` where OP ∈ {>=,<=,==,!=,>,<}. Refs use the cross-dataset grammar — e.g. `{executions._signal_flag.sum} >= 10`, `{ladder.symmetry.max} > 0.85`, `{context.book_count} > 1`. |
| `severity_map` | `object` | no | `json` | `{}` |  | Override severity per disposition. Defaults: {ESCALATE: HIGH, REVIEW: MEDIUM, DISMISS: LOW}. |
| `output_branches` | `object` | no | `json` | `{}` |  | Map of disposition → branch_name string. |

**Constraints**

- Threshold mode (default) requires escalate_threshold >= review_threshold.
- Rule mode short-circuits: first matching rule sets disposition + severity.

## `EXECUTION_DATA_COLLECTOR` — Solr Data Collector

**Use:** Query Solr for client orders, executions, trades, and quotes

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `EXECUTION_DATA_COLLECTOR` |
| Display name | Solr Data Collector |
| UI section | `integrations` |
| Palette order | `11` |
| Color | `#2563EB` |
| Icon | `ArrowLeftRight` |
| Config tags | `source`, `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `context` | `object` | no | Context keys referenced in query_template as {context.xxx} |  |
| `window` | `object` | no | Optional TIME_WINDOW output (start_time, end_time) — filters rows to the window when window_key is set. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `executions` | `dataframe` | no | `ctx.datasets[{output_name}]` | Order/execution rows. Stored in ctx.datasets under the configured output_name. |  |
| `row_count` | `scalar` | yes | `ctx.values[{output_name}_count]` | Integer row count. Stored in ctx.values as {output_name}_count. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `enum` | yes | `select` | `hs_client_order` | `hs_client_order`, `hs_execution`, `hs_trades`, `hs_orders_and_executions`, `hs_quotes` | Which Solr collection to query. Values are derived from data_sources/metadata/trades.yaml at runtime. |
| `query_template` | `string` | yes | `textarea` |  |  | Solr query; use {context.xxx} placeholders for alert fields. |
| `output_name` | `string` | yes | `text` | `execution_data` |  | Dataset name in ctx.datasets. |
| `window_key` | `string` | no | `text` | `window` |  | ctx.values key holding the window dict. Used when a TIME_WINDOW node is wired upstream. |
| `trader_filter_key` | `string` | no | `text` | `trader_id` |  | ctx.values key whose value filters trader_id when present. Empty = no trader filter. |
| `loop_over_books` | `boolean` | no | `checkbox` | `False` |  | Repeat the query for each book in the books list. |
| `books` | `string_list` | no | `chips` | `[]` |  | Book names when loop_over_books=true. |
| `mock_csv_path` | `string` | no | `text` | `""` |  | Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing. CSV columns are not re-checked against the lists below; synthetic rows are. |

**Constraints**

- When source reads versioned trades/fills, trade_version:1 MUST be hard-coded in query_template — never from context.
- Output DataFrame will always include trade_version=1 for hs_execution, hs_trades, and hs_orders_and_executions synthetic reads.

## `EXTRACT_LIST` — Extract List

**Use:** Emit the unique values of a column as an ordered list — cascade primitive for fan-out keys.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `EXTRACT_LIST` |
| Display name | Extract List |
| UI section | `transform` |
| Palette order | `24` |
| Color | `#8B5CF6` |
| Icon | `ListFilter` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Source DataFrame (by input_name). |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `values` | `object` | no | `` | {values: [...]} — published under ctx.values[output_name]. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Dataset name in ctx.datasets. |
| `column` | `string` | yes | `text` |  |  | Column to enumerate. |
| `output_name` | `string` | yes | `text` |  |  | ctx.values key to publish {values: [...]} under. |
| `order` | `enum` | no | `select` | `first_seen` | `sort`, `desc`, `first_seen` | sort: ascending, desc: descending, first_seen: original order. |
| `dropna` | `boolean` | no | `checkbox` | `True` |  | Exclude NaN values. |

**Constraints**

- Typical use: EXTRACT_LIST(executions, 'book') → fan-out keys for GROUP_BY_BOOK or MAP.

## `EXTRACT_SCALAR` — Extract Scalar

**Use:** Reduce a column of an upstream DataFrame to a single scalar (first, unique_single, max, min, count, sum, mean).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `EXTRACT_SCALAR` |
| Display name | Extract Scalar |
| UI section | `transform` |
| Palette order | `25` |
| Color | `#8B5CF6` |
| Icon | `Crosshair` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Source DataFrame (by input_name). |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `value` | `scalar` | yes | `` | Published under ctx.values[output_name]. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Dataset name in ctx.datasets. |
| `column` | `string` | yes | `text` |  |  | Column to reduce. |
| `reducer` | `enum` | yes | `select` | `unique_single` | `first`, `unique_single`, `max`, `min`, `count`, `sum`, `mean` | How to collapse the column to a single value. |
| `output_name` | `string` | yes | `text` |  |  | ctx.values key to publish the scalar under. |
| `fail_on_ambiguous` | `boolean` | no | `checkbox` | `False` |  | When reducer=unique_single, raise if the column has more than one distinct value (default false — take the first). |

**Constraints**

- Typical use: EXTRACT_SCALAR(orders, 'trader_id', unique_single) → feeds a downstream collector's trader_filter_key.

## `FEATURE_ENGINE` — Feature Engine

**Use:** Compose feature transforms (window, slice, pivot, agg, rolling, derive)

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `FEATURE_ENGINE` |
| Display name | Feature Engine |
| UI section | `transform` |
| Palette order | `20` |
| Color | `#0EA5E9` |
| Icon | `SlidersHorizontal` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Source DataFrame referenced by input_name. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `features` | `dataframe` | no | `` | Final working DataFrame after all chained ops, published as ctx.datasets[output_name]. Ops with an `as` field also publish intermediate datasets under that name. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Source dataset name. |
| `output_name` | `string` | no | `text` |  |  | Target dataset name (defaults to input_name). |
| `ops` | `array` | yes | `json` | `[]` |  | Ordered list of operations applied to the working DataFrame. Each op is {op: <name>, ...op-specific keys, as?: <publish_name>}. Supported ops:<br>• window_bucket {time_col, interval_ms, out_col}<br>  Floor a timestamp into integer buckets of size interval_ms.<br><br>• time_slice {time_col, out_col, on_miss?, windows: [{name,start,end}]}<br>  Label rows with a phase string based on which window they fall in.<br>  start/end accept {context.x} or any ref grammar; missing rows get on_miss.<br><br>• groupby_agg {by, aggs: {col: agg, ...}}<br>  Standard pandas groupby + agg, returns a flat reset_index frame.<br><br>• pivot {index, columns, values, aggfunc?}<br>  DataFrame.pivot_table; column names cast to str; fill_value=0.<br><br>• rolling {window, col, agg, out_col?}<br>  Rolling window aggregation (mean/sum/min/max/std/...) with<br>  min_periods=1.<br><br>• derive {out_col, expr}<br>  Vectorised DataFrame.eval expression (no Python branching).<br><br>• apply_expr {out_col, expr}<br>  Per-row Python expression evaluated with the row as locals.<br>  Slower; use only when `derive` cannot express the logic.<br><br>• rename {mapping: {old_name: new_name, ...}}<br>  Rename columns in place.<br><br>• lifecycle_event {group_by, sort_by?, status_col?, out_col?}<br>  Within each group_by partition, label rows with the<br>  '<prev_status> → <status>' transition that produced them.<br>  Used for order-lifecycle narratives. |

**Constraints**

- Ops execute in declared order; mid-pipeline `as` publishes intermediate datasets without consuming them.
- apply_expr runs Python eval row-by-row — keep expressions small and side-effect-free.

## `GROUP_BY` — Group By

**Use:** Split a dataset by column value into one DataFrame per group

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `GROUP_BY` |
| Display name | Group By |
| UI section | `transform` |
| Palette order | `22` |
| Color | `#7C3AED` |
| Icon | `Split` |
| Config tags | `input_name`, `group_by_column` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Upstream dataset to partition. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `keys` | `object` | no | `` | {values: [...]} list of distinct group keys. Stored in ctx.values under keys_output_name (default '{input_name}_keys'). |  |
| `groups` | `object` | no | `` | Each group slice is published as ctx.datasets[f"{output_prefix}_{key}"]. Conceptual bucket — runtime stores one dataset per key. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `input_name` | `string` | yes | `text` |  |  | Name of the dataset to partition. |
| `group_by_column` | `string` | yes | `text` |  |  | Column whose distinct values define group boundaries. |
| `output_prefix` | `string` | yes | `text` |  |  | Prefix for per-group dataset names. For key='BOOK_A' and prefix 'orders_by_book', the slice is published as ctx.datasets['orders_by_book_BOOK_A']. |
| `keys_output_name` | `string` | no | `text` | `""` |  | ctx.values key for the {values: [...]} list. Defaults to '{input_name}_keys' when blank. |
| `dropna` | `boolean` | no | `checkbox` | `True` |  | Drop rows where the group_by_column is null before partitioning. |
| `order` | `enum` | no | `select` | `first_seen` | `first_seen`, `sort`, `desc` | Key order: first_seen, sort (ascending), desc. |

**Constraints**

- Output dataset names contain the raw key value — keep keys filesystem-safe.

## `MAP` — Map

**Use:** Fan out a sub-workflow over a list of keys; aggregate results

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `MAP` |
| Display name | Map |
| UI section | `transform` |
| Palette order | `23` |
| Color | `#DB2777` |
| Icon | `Repeat` |
| Config tags | `keys_key`, `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `keys` | `object` | no | {values: [...]} list — typically from EXTRACT_LIST or GROUP_BY. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `results` | `object` | no | `` | {results: {<key>: {<collected_name>: value, ...}}} — stored in ctx.values[output_name]. Per-iteration datasets listed in collect_datasets are ALSO published at the top level as ctx.datasets[f"{output_name}_{key}_{dataset_name}"] so downstream nodes can address them directly. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `keys_key` | `string` | yes | `text` |  |  | ctx.values key holding the {values: [...]} list to iterate. |
| `iteration_ctx_key` | `string` | yes | `text` |  |  | ctx.values key where the current iteration's key is written for each sub-workflow run. Lets sub-workflow collectors template queries against the current group. |
| `dataset_prefix` | `string` | no | `text` | `""` |  | Optional prefix used by an upstream GROUP_BY. When set, the per-iteration dataset ctx.datasets[f"{dataset_prefix}_{key}"] is aliased into the child ctx under iteration_dataset_alias. |
| `iteration_dataset_alias` | `string` | no | `text` | `""` |  | Alias name for the per-iteration dataset inside the child ctx. No-op when dataset_prefix is blank. |
| `sub_workflow` | `object` | yes | `json` |  |  | Nested DAG: {nodes: [...], edges: [...]}. Runs once per key. |
| `collect_values` | `string_list` | no | `chips` | `[]` |  | ctx.values keys to harvest from each iteration into results[key]. |
| `collect_datasets` | `string_list` | no | `chips` | `[]` |  | ctx.datasets names to harvest from each iteration. They become both results[key][name] and ctx.datasets[f"{output_name}_{key}_{name}"]. |
| `output_name` | `string` | yes | `text` | `map_results` |  | ctx.values key for the aggregated {results: {...}} dict. |

**Constraints**

- sub_workflow is executed in topological order per iteration; child ctx is a shallow copy of parent.
- Iteration-local writes do NOT leak back to the parent ctx except via collect_values / collect_datasets.

## `MARKET_DATA_COLLECTOR` — Mercury

**Use:** Query EBS/Mercury tick data, normalise timestamps

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `MARKET_DATA_COLLECTOR` |
| Display name | Mercury |
| UI section | `integrations` |
| Palette order | `12` |
| Color | `#0891B2` |
| Icon | `CandlestickChart` |
| Config tags | `source`, `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `context` | `object` | no | Context keys referenced in query_template as {context.xxx}. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `ticks` | `dataframe` | no | `ctx.datasets[{output_name}]` | DataFrame with columns: timestamp (ISO str), symbol (str), bid, ask, mid, spread_pips, bid_size, ask_size, venue_name, seq_no. Stored under ctx.datasets[output_name]. | columns: `timestamp`, `symbol`, `bid`, `ask`, `mid`, `spread_pips`, `bid_size`, `ask_size`, `venue_name`, `seq_no` |
| `tick_count` | `scalar` | yes | `ctx.values[{output_name}_tick_count]` | Tick count (int). Stored as {output_name}_tick_count. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `enum` | yes | `select` | `EBS` | `EBS`, `Mercury` | Which tick feed to query. |
| `query_template` | `string` | yes | `textarea` |  |  | Query with {context.xxx} placeholders. |
| `output_name` | `string` | yes | `text` | `market_data` |  | Dataset name in ctx.datasets. |
| `mock_csv_path` | `string` | no | `text` | `""` |  | Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. Ignored if the file is missing. |

**Constraints**

- Normalises raw_timestamp (nanosecond int) → ISO-8601 string.
- Normalises byte-string fields (raw_symbol, venue) → plain str.

## `ORACLE_DATA_COLLECTOR` — Oracle Data Collector

**Use:** Query Oracle surveillance warehouse order/execution extracts

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `ORACLE_DATA_COLLECTOR` |
| Display name | Oracle Data Collector |
| UI section | `integrations` |
| Palette order | `13` |
| Color | `#7C3AED` |
| Icon | `Database` |
| Config tags | `source`, `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `context` | `object` | no | Context keys referenced in query_template as {context.xxx} |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `ctx.datasets[{output_name}]` | Oracle extract rows. Stored in ctx.datasets under the configured output_name. |  |
| `row_count` | `scalar` | yes | `ctx.values[{output_name}_count]` | Integer row count. Stored in ctx.values as {output_name}_count. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `enum` | yes | `select` | `oracle_orders` | `oracle_orders`, `oracle_executions` | Which Oracle extract to query. |
| `query_template` | `string` | no | `textarea` | `""` |  | Oracle SQL template; use {context.xxx} placeholders for alert fields. |
| `output_name` | `string` | yes | `text` | `oracle_data` |  | Dataset name in ctx.datasets. |
| `mock_csv_path` | `string` | no | `text` | `""` |  | Demo-mode override: path to a CSV used verbatim instead of the synthetic generator. |

## `REPORT_OUTPUT` — Report Output

**Use:** Generate Excel report with tabs & highlights

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `REPORT_OUTPUT` |
| Display name | Report Output |
| UI section | `output` |
| Palette order | `60` |
| Color | `#047857` |
| Icon | `FileSpreadsheet` |
| Config tags | `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `datasets` | `object` | yes | All DataFrames to include as tabs (ctx.datasets). |  |
| `sections` | `object` | no | Section narratives for the Section Summaries sheet. |  |
| `executive_summary` | `text` | no | Executive summary text. |  |
| `context` | `object` | no | disposition, trader_id, currency_pair etc. used on the cover page. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `report_path` | `text` | no | `ctx.report_path` | Absolute path to the written .xlsx file. Stored as context.report_path. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `output_path` | `string` | yes | `text` |  |  | File path for the Excel output (e.g. 'output/report.xlsx'). |
| `tabs` | `array` | no | `json` | `[]` |  | Array of tab specs. Each tab is one of:<br>• Static tab — {name, dataset, include_highlights?}.<br>  Renders the named dataset under the given sheet name.<br><br>• Expanded tab — {expand_from, as?, name, dataset, include_highlights?}.<br>  `expand_from` is a single `{ref}` resolving to a list, dict,<br>  Series, or MAP-result. One tab is emitted per item, with the<br>  item bound under `as` (default `item`) and substituted into both<br>  `name` and `dataset` templates via `.format_map`. Examples:<br><br>    expand_from: "{context.book_list}"<br>    as: book<br>    name: "Executions · {book}"<br>    dataset: "executions_{book}"<br><br>    expand_from: "{per_book.results}"   # MAP result dict<br>    as: key<br>    name: "Per-book {key}"<br>    dataset: "per_book_{key}_executions"<br><br>When `tabs` is empty, all context.datasets are included as auto-named tabs. |

**Constraints**

- Tab names truncated to 31 characters (Excel limit).
- Datetime columns converted to strings automatically.
- List/dict cell values stringified automatically.
- If include_highlights=true, uses dataset_name + '_highlighted' if it exists.
- Must be the final node in the workflow.

## `SECTION_SUMMARY` — Section Summary

**Use:** Aggregate stats + LLM narrative section

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `SECTION_SUMMARY` |
| Display name | Section Summary |
| UI section | `narrative` |
| Palette order | `50` |
| Color | `#DB2777` |
| Icon | `NotebookText` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Any DataFrame referenced by input_name. |  |
| `context` | `object` | no | trader_id, currency_pair, disposition consumed by the prompt template. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `section` | `object` | no | `ctx.sections[{section_name}]` | {name, stats, narrative, dataset}. Stored under context.sections[section_name]. | keys: `name`, `stats`, `narrative`, `dataset` |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `section_name` | `string` | yes | `text` |  |  | Unique section identifier. |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Source dataset. |
| `mode` | `enum` | no | `select` | `templated` | `templated`, `fact_pack_llm`, `event_narrative` | templated     — legacy stats-in-prompt flow. fact_pack_llm — pre-compute named facts, pass as JSON, verify each<br>                required fact appears in narrative (retry once).<br>event_narrative — format one line per row into a chronological list,<br>                  then stitch with an LLM. |
| `field_bindings` | `array` | no | `json` | `[]` |  | Array of {field: string, agg: 'count'\|'sum'\|'mean'\|'nunique'\|'max'\|'min'}. Used in templated mode. |
| `facts` | `array` | no | `json` | `[]` |  | Array of {name, column, agg} for fact_pack_llm mode. Example: [{name: 'buy_count', column: 'side', agg: 'count_where_buy'}]. |
| `required_facts` | `string_list` | no | `chips` | `[]` |  | Fact names whose values MUST appear verbatim in the generated narrative. A retry is triggered once if any are missing. |
| `sort_by` | `string` | no | `text` | `""` |  | Column used to order rows for event_narrative mode. |
| `event_template` | `string` | no | `text` | `""` |  | Python format string used to render each event row in event_narrative mode. Row columns are passed as keyword args. Example: '{timestamp}  {side} {quantity} @ {limit_price}'. |
| `max_events` | `integer` | no | `number` | `40` |  | Cap events passed to the LLM in event_narrative mode. |
| `llm_prompt_template` | `string` | no | `textarea` |  |  | Prompt with {stats}, {facts}, {events}, {section}, {disposition}, {trader_id}, {currency_pair} placeholders, plus any vars defined under prompt_context.vars and (when mode=dataset\|mixed) {dataset}. Cross-dataset refs like {executions.notional.sum} resolve inline. |
| `prompt_context` | `object` | no | `json` | `{}` |  | Optional structured slot block: {mode: template\|dataset\|mixed, vars: {name: ref_expr, ...}, dataset: {ref, format, max_rows, columns}}. vars resolve cross-dataset refs into named slots; the serialized dataset (csv/json/markdown) is exposed as {dataset}. |

**Constraints**

- LLM model: claude-sonnet-4-6, max_tokens: 600.
- fact_pack_llm retries at most once when required facts are missing from the narrative.

## `SIGNAL_CALCULATOR` — Signal Calculator

**Use:** Compute signals — always outputs 5 columns

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `SIGNAL_CALCULATOR` |
| Display name | Signal Calculator |
| UI section | `signal` |
| Palette order | `30` |
| Color | `#DC2626` |
| Icon | `Signal` |
| Config tags | `signal_type`, `output_name` |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `dataset` | `dataframe` | yes | Trade/execution DataFrame (typically after NORMALISE_ENRICH). |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `signals` | `dataframe` | no | `` | Input DataFrame + exactly 5 signal columns: _signal_flag (bool), _signal_score (float in [0, 1] — same scale as DECISION_RULE.score), _signal_reason (str), _signal_type (str), _signal_window (str). | columns: `_signal_flag`, `_signal_score`, `_signal_reason`, `_signal_type`, `_signal_window` |
| `flag_count` | `scalar` | yes | `` | Number of rows where _signal_flag == True. Stored as {output_name}_flag_count. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `mode` | `enum` | yes | `select` | `configure` | `configure`, `upload_script` | How the signal is computed. |
| `signal_type` | `enum` | no | `select` |  | `FRONT_RUNNING`, `WASH_TRADE`, `SPOOFING`, `LAYERING` | Built-in signal family (configure mode only). |
| `input_name` | `input_ref` | yes | `input_ref` |  |  | Source dataset name (an upstream output_name). |
| `output_name` | `string` | yes | `text` |  |  | Output dataset name. |
| `params` | `object` | no | `json` | `{}` |  | Signal-specific parameters (overrides built-in defaults). |
| `script_path` | `string` | no | `text` |  |  | Path to custom Python script (upload_script mode). |
| `script_content` | `code` | no | `code` |  |  | Inline Python snippet operating on local variable `df` (upload_script mode). |

**Constraints**

- ALWAYS outputs exactly these 5 columns: _signal_flag, _signal_score, _signal_reason, _signal_type, _signal_window.
- Missing signal columns are auto-filled with defaults (False, 0.0, '', '', '').
- Custom scripts must operate on local variable 'df' and leave result in 'df'.

## `TIME_WINDOW` — Time Window

**Use:** Expand an event time into a [start_time, end_time] window for downstream filtering.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `TIME_WINDOW` |
| Display name | Time Window |
| UI section | `transform` |
| Palette order | `19` |
| Color | `#F59E0B` |
| Icon | `Clock` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `context` | `object` | no | Context keys referenced in event_time_key / end_time_key. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `window` | `object` | no | `` | {start_time, end_time, buffer_minutes}. Published under ctx.values[output_name]. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `event_time_key` | `string` | no | `text` | `""` |  | ctx.values key holding the anchor time (e.g. 'fr_start' from the alert). Required unless start_time_literal is set. |
| `end_time_key` | `string` | no | `text` | `""` |  | ctx.values key holding the end anchor (e.g. 'fr_end'). If empty, end = start. |
| `start_time_literal` | `string` | no | `text` | `""` |  | Literal ISO start time. Used when the window anchor isn't in ctx.values. |
| `end_time_literal` | `string` | no | `text` | `""` |  | Literal ISO end time. |
| `pre_minutes` | `integer` | no | `number` | `0` |  | Subtract this many minutes from the start anchor. |
| `post_minutes` | `integer` | no | `number` | `0` |  | Add this many minutes to the end anchor. |
| `output_name` | `string` | yes | `text` | `window` |  | ctx.values key under which to publish the window dict (default 'window'). |

**Constraints**

- Output dict keys: start_time (ISO str), end_time (ISO str), buffer_minutes {pre, post}.
- If the event time cannot be resolved, publishes an empty dict — downstream collectors treat that as no-filter.
