# Node Contract Audit V2: Mode Combinations

This document extends `NODE_CONTRACT_AUDIT.md`.

The first audit answers: "What does each node currently declare and implement?"
This V2 answers: "If we were designing the builder top-down, which combinations
should be modes inside one node, and which combinations deserve separate nodes?"

The design goal is to avoid node explosion while still giving users rich,
guided controls. A node should have modes when the business intent is the same
but the execution shape varies. A separate node should exist when the business
intent is different.

## Product Rule

Use one node with modes when:

- the user thinks of it as one action;
- the input and output family are the same;
- only the internal strategy changes;
- the UI can hide irrelevant fields cleanly.

Use separate nodes when:

- the output type is fundamentally different for downstream wiring;
- the operation belongs in a different workflow stage;
- the node would need too many unrelated config branches;
- security or infrastructure controls differ materially.

## Core Mode-Driven Nodes

The two most important combinational nodes are:

- `SECTION_SUMMARY`: creates report-ready narrative sections from one dataset.
- `REPORT_OUTPUT`: emits the final artifact in Excel, CSV, PDF, or similar formats.

These should remain one node each, but their YAML contracts need explicit
mode-dependent UI and validation.

## `SECTION_SUMMARY`: Ideal Mode Design

### Functional Purpose

One node should own "turn this dataset into a report section". It should not be
split into `LLM_SUMMARY`, `TEMPLATE_SUMMARY`, `EVENT_SUMMARY`, etc. The user
experience should be:

1. Pick a dataset.
2. Pick a summary mode.
3. Configure only the fields relevant to that mode.
4. Produce one section object for downstream consolidated summary / report.

### Recommended Modes

#### `templated_stats`

Purpose: deterministic stats plus optional templated prose.

Best for:

- fast summaries;
- low-risk report sections;
- known metrics like counts, sums, min/max, unique counts;
- situations where the user wants exact deterministic output.

User-facing controls:

- `input_name`: dataset dropdown.
- `section_name`: text, auto-suggest from node label.
- `stats`: repeatable rows of `{label, column, reducer}`.
- `include_row_count`: checkbox.
- `include_signal_hits`: checkbox, shown only when `_signal_flag` exists.
- `include_keyword_hits`: checkbox, shown only when `_keyword_hit` exists.
- `template`: textarea with chips for `{stats}`, `{trader_id}`, `{disposition}`.
- `render_mode`: enum `stats_only`, `template_only`, `stats_plus_template`.

Python runtime:

- Reads `ctx.datasets[input_name]`.
- Reads optional context keys such as `trader_id`, `currency_pair`, `disposition`.
- Computes stats locally.
- Does not require LLM.
- Writes `ctx.sections[section_name]`.

Fixed output:

- `ctx.sections[section_name] = {name, mode, stats, narrative, dataset}`.

#### `fact_pack_llm`

Purpose: compute exact facts, send them to an LLM, and force the narrative to
reference required facts.

Best for:

- analyst-style prose;
- summaries where facts must remain grounded;
- surveillance narratives that need wording but should cite exact numbers.

User-facing controls:

- `facts`: repeatable fact builder.
- Each fact: `{name, label, column, reducer, value?}`.
- `reducer`: dropdown, not free text.
- `count_where` should be structured as `{column, operator, value}`, not magic strings like `count_where_buy`.
- `required_facts`: checkbox multi-select generated from `facts[].name`.
- `select_all_required_facts`: checkbox.
- `llm_prompt_template`: textarea with `{facts}` chip.
- `strictness`: enum `none`, `retry_missing_facts`, `fail_if_missing`.

Python runtime:

- Reads `ctx.datasets[input_name]`.
- Computes fact pack.
- Calls LLM only after deterministic fact computation.
- Verifies required facts if strictness requires it.
- Writes section object.

Fixed output:

- `stats` should include row count and fact values.
- `narrative` should include LLM text.
- Optional `verification` should include missing facts and retry count.

#### `event_narrative`

Purpose: turn rows into chronological/event prose.

Best for:

- communications summaries;
- order lifecycle narratives;
- spoofing/layering timelines;
- "what happened when" sections.

User-facing controls:

- `sort_by`: column dropdown, biased toward time semantic columns.
- `max_events`: number.
- `event_fields`: column multi-select.
- `event_template`: advanced override, generated from `event_fields`.
- `llm_prompt_template`: textarea with `{events}` chip.
- `empty_behavior`: enum `write_no_events`, `skip_section`, `write_template`.

Python runtime:

- Reads rows from `ctx.datasets[input_name]`.
- Sorts by selected column.
- Formats rows using generated or explicit template.
- Sends event block to LLM.
- Writes section object.

Fixed output:

- `stats.row_count`.
- `stats.event_count`.
- `narrative`.

#### `dataset_llm`

Purpose: pass a controlled slice of the dataset to the LLM.

Best for:

- small datasets;
- ad hoc evidence tables;
- when templated stats are not enough.

User-facing controls:

- `columns`: multi-select.
- `max_rows`: number.
- `format`: enum `markdown`, `csv`, `json`.
- `llm_prompt_template`: textarea with `{dataset}` chip.

Python runtime:

- Uses `prompt_context.dataset` behavior directly.
- Must cap rows and columns.
- Writes section object.

Fixed output:

- `stats.row_count`.
- `stats.rows_sent_to_llm`.
- `stats.columns_sent_to_llm`.

### `SECTION_SUMMARY` Ideal YAML Shape

YAML should support conditional params:

```yaml
params:
  - name: mode
    type: enum
    enum: [templated_stats, fact_pack_llm, event_narrative, dataset_llm]
    default: templated_stats

  - name: stats
    type: array
    visible_if: {mode: templated_stats}
    item_schema:
      label: {type: string}
      column: {type: column_ref, source: input_name}
      reducer: {type: enum, enum: [count, sum, mean, min, max, nunique]}

  - name: facts
    type: array
    visible_if: {mode: fact_pack_llm}
    item_schema:
      name: {type: string}
      label: {type: string}
      column: {type: column_ref, source: input_name, required_if_not: {reducer: row_count}}
      reducer: {type: enum, enum: [row_count, count, sum, mean, min, max, nunique, unique_values, count_where]}
      value: {type: string, visible_if: {reducer: count_where}}

  - name: required_facts
    type: string_list
    visible_if: {mode: fact_pack_llm}
    options_from: facts[].name

  - name: event_fields
    type: string_list
    visible_if: {mode: event_narrative}
    options_from: columns(input_name)

  - name: output_section
    type: object
    advanced: true
```

The current `field_bindings` can remain as a backward-compatible alias for
`stats`, but new workflows should use `stats`.

## `CONSOLIDATED_SUMMARY`: Ideal Mode Design

This should also remain one node. It answers: "combine sections into one
executive summary."

Recommended modes:

- `llm_stitch`: current behavior, LLM summarizes all sections.
- `template_stitch`: deterministic template over selected sections.
- `none`: skip executive summary but still let `REPORT_OUTPUT` render sections.

User-facing controls:

- `include_sections`: checkbox multi-select from upstream section names.
- `section_order`: drag/drop list.
- `mode`: enum.
- `llm_prompt_template`: visible only for `llm_stitch`.
- `template`: visible only for `template_stitch`.

Fixed input:

- `ctx.sections`.
- `ctx.values.disposition`, `severity`, `flag_count`, alert fields.

Fixed output:

- `ctx.executive_summary`.
- `ctx.values.executive_summary`.

## `REPORT_OUTPUT`: Ideal Format Design

### Functional Purpose

One node should own "emit the final report artifact". It should not be only an
Excel node. The user should pick an output format, and the UI should expose only
the layout options that make sense for that format.

Recommended type ID:

- Keep `REPORT_OUTPUT` as the stable type ID.
- Display name can be "Report Output".
- Do not create separate `EXCEL_OUTPUT`, `CSV_OUTPUT`, `PDF_OUTPUT` unless the
runtime infrastructure becomes completely different.

### Recommended Output Formats

#### `excel`

Purpose: analyst workbook with many tabs.

Supports:

- cover sheet;
- executive summary sheet;
- section summaries sheet;
- multiple data tabs;
- dynamic tabs from `MAP` results;
- row highlights;
- formulas / formatting later.

User-facing controls:

- `output_path`.
- `format = excel`.
- `include_cover`: checkbox.
- `include_executive_summary`: checkbox.
- `include_section_summaries`: checkbox.
- `tabs`: repeatable tab builder.
- `auto_include_all_datasets`: checkbox.

Tab builder:

- `tab_type`: `static_dataset`, `dynamic_from_ref`, `map_result`.
- `name`: text template.
- `dataset`: dataset dropdown or template.
- `include_highlights`: checkbox.
- `columns`: optional multi-select.
- `sort_by`: optional column dropdown.

Python runtime:

- Reads `ctx.datasets`, `ctx.sections`, `ctx.executive_summary`, context values.
- Writes `.xlsx`.
- Writes `ctx.report_path` and `ctx.values.report_path`.

Fixed output:

- `report_path`.
- Optional `report_metadata = {format, page_count/sheet_count, tab_count}`.

#### `csv`

Purpose: export one dataset as a flat file.

Important product rule:

- CSV is single-table. It should not pretend to support multiple tabs.
- If a user selects multiple datasets, use `zip_csv` instead.

User-facing controls:

- `format = csv`.
- `dataset`: required single dataset dropdown.
- `columns`: optional multi-select.
- `include_highlight_columns`: checkbox.
- `delimiter`: enum `comma`, `tab`, `pipe`.
- `output_path`.

Python runtime:

- Reads exactly one `ctx.datasets[dataset]`.
- Writes one `.csv`.

Fixed output:

- `report_path`.
- `row_count`.
- `column_count`.

#### `zip_csv`

Purpose: multiple CSVs in one downloadable artifact.

Best for:

- "Excel is not allowed" environments;
- systems that ingest one CSV per table;
- preserving multiple datasets without workbook format.

User-facing controls:

- `format = zip_csv`.
- `files`: repeatable file builder, same shape as Excel static tabs.
- `dynamic_files`: optional expansion from refs/MAP.
- `output_path`.

Python runtime:

- Reads multiple datasets.
- Writes one `.zip` containing CSV files.

Fixed output:

- `report_path`.
- `file_count`.

#### `pdf`

Purpose: human-readable final narrative report.

Best for:

- management / compliance summaries;
- evidence narratives;
- static attachments.

PDF should be section-driven, not tab-driven.

User-facing controls:

- `format = pdf`.
- `include_cover`: checkbox.
- `include_executive_summary`: checkbox.
- `sections`: checkbox multi-select from `ctx.sections`.
- `section_order`: drag/drop.
- `include_evidence_tables`: checkbox.
- `evidence_tables`: repeatable dataset/table builder, visible only when enabled.
- `page_size`: enum `A4`, `Letter`.
- `orientation`: enum `portrait`, `landscape`.
- `output_path`.

Python runtime:

- Reads `ctx.sections`, `ctx.executive_summary`, selected `ctx.datasets`.
- Renders a document, not sheets.
- Writes `.pdf`.

Fixed output:

- `report_path`.
- `section_count`.
- Optional `page_count`.

#### `html`

Purpose: previewable report and future web artifact.

This can be a useful intermediate for PDF generation.

User-facing controls:

- Similar to PDF.
- Optional `embed_tables`, `include_styles`.

Python runtime:

- Writes `.html`.

Fixed output:

- `report_path`.

#### `json`

Purpose: machine-readable run result.

User-facing controls:

- `include_context`: checkbox.
- `include_sections`: checkbox.
- `include_executive_summary`: checkbox.
- `include_dataset_summaries`: checkbox.
- `include_full_datasets`: checkbox, advanced and off by default.

Python runtime:

- Writes one structured `.json`.

Fixed output:

- `report_path`.

### `REPORT_OUTPUT` Ideal YAML Shape

```yaml
params:
  - name: format
    type: enum
    enum: [excel, csv, zip_csv, pdf, html, json]
    default: excel

  - name: output_path
    type: string
    required: true

  - name: dataset
    type: input_ref
    visible_if: {format: csv}

  - name: tabs
    type: array
    visible_if: {format: excel}
    item_schema:
      tab_type: {type: enum, enum: [static_dataset, dynamic_from_ref, map_result]}
      name: {type: string}
      dataset: {type: input_ref, visible_if: {tab_type: static_dataset}}
      expand_from: {type: ref, visible_if: {tab_type: dynamic_from_ref}}
      dataset_template: {type: string, visible_if_any: [{tab_type: dynamic_from_ref}, {tab_type: map_result}]}
      include_highlights: {type: boolean, default: true}
      columns: {type: column_list_ref, source: dataset, required: false}

  - name: files
    type: array
    visible_if: {format: zip_csv}
    item_schema:
      filename: {type: string}
      dataset: {type: input_ref}
      columns: {type: column_list_ref, source: dataset}

  - name: sections
    type: string_list
    visible_if_any: [{format: pdf}, {format: html}]
    options_from: sections()

  - name: evidence_tables
    type: array
    visible_if_any: [{format: pdf}, {format: html}]
    item_schema:
      title: {type: string}
      dataset: {type: input_ref}
      columns: {type: column_list_ref, source: dataset}
      max_rows: {type: integer, default: 50}
```

### Output Format Matrix

| Format | Dataset Count | Sections | Highlights | Dynamic MAP Outputs | Best For |
| --- | --- | --- | --- | --- | --- |
| `excel` | Many | Yes | Yes | Yes | Analyst workbook |
| `csv` | One | No | Optional columns only | No | Single-table export |
| `zip_csv` | Many | No | Optional columns only | Yes | Multi-table machine export |
| `pdf` | Optional evidence tables | Yes | Rendered as labels/styles | Limited | Human narrative report |
| `html` | Optional evidence tables | Yes | Yes | Limited | Browser preview/share |
| `json` | Optional summaries/full data | Yes | As fields | Yes | API/integration output |

## Avoiding Bad Combinations

The UI should prevent combinations that sound possible but produce bad UX:

- CSV with multiple tabs: use `zip_csv` or `excel`.
- PDF with hundreds of raw rows: require `max_rows` and evidence table caps.
- LLM summary with uncapped full dataset: require `columns` and `max_rows`.
- `fact_pack_llm` without facts: prompt user to add facts or switch mode.
- `event_narrative` without sort column when a time column exists: warn and suggest the time column.
- Excel dynamic tabs without a valid `expand_from`: block or warn before run.

## Builder UX Recommendation

The right product shape is not "more nodes"; it is "fewer, smarter nodes":

- `SECTION_SUMMARY` should be one node with summary modes.
- `CONSOLIDATED_SUMMARY` should be one node with stitch modes.
- `REPORT_OUTPUT` should be one node with output format modes.
- `FEATURE_ENGINE`, `DATA_HIGHLIGHTER`, and `DECISION_RULE` should use builders
  for their repeatable configs.

This gives the user a compact palette but still supports the real combinations:

- templated stats vs LLM fact packs vs event narratives;
- Excel multi-tab vs CSV single export vs zipped CSV bundle;
- PDF sectioned narrative vs Excel evidence workbook;
- static datasets vs dynamic per-book/per-venue outputs from `MAP`.

## Implementation Priority

1. Add `format` to `REPORT_OUTPUT` and keep existing behavior as `format=excel`.
2. Add single-dataset `csv` support because it is the smallest new format.
3. Add `zip_csv` for multiple datasets without Excel.
4. Add `pdf` after section ordering and evidence-table caps are designed.
5. Rename `SECTION_SUMMARY.field_bindings` to `stats` in the new contract while
   preserving backward compatibility.
6. Add YAML support for `visible_if`, `item_schema`, `column_ref`, and `ref`.

The runtime can evolve incrementally, but the YAML contract should be designed
now so the UI does not have to reverse-engineer mode logic from Python code.

## Per-Node Option Trees

This section maps every node into the option tree the builder should expose.
The goal is that users see a small number of meaningful branches instead of a
flat wall of config fields.

### Palette-Level Grouping

| Stage | Nodes | UX Principle |
| --- | --- | --- |
| Trigger | `ALERT_TRIGGER` | Define alert payload once; downstream nodes pick from context keys. |
| Integrations | `EXECUTION_DATA_COLLECTOR`, `COMMS_COLLECTOR`, `MARKET_DATA_COLLECTOR`, `ORACLE_DATA_COLLECTOR` | Source first, then filters/window/query, then output name. |
| Transform | `TIME_WINDOW`, `FEATURE_ENGINE`, `DATA_HIGHLIGHTER`, `GROUP_BY`, `MAP`, `EXTRACT_LIST`, `EXTRACT_SCALAR` | Pick input dataset, pick operation/mode, expose column pickers and dynamic outputs. |
| Signal / Rule | `SIGNAL_CALCULATOR`, `DECISION_RULE` | Pick signal/rule mode, then show typed parameter forms. |
| Narrative | `SECTION_SUMMARY`, `CONSOLIDATED_SUMMARY` | Pick narrative mode, then show prompt/fact/event/section controls. |
| Output | `REPORT_OUTPUT` | Pick artifact format, then expose layout controls relevant to that format. |

### `ALERT_TRIGGER`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Standard alert schema | `standard_fields` | Checkbox preset list: `trader_id`, `book`, `alert_date`, `currency_pair`, `alert_id`, `event_time`, `entity`, `desk` | `ctx.values[field]` for each present payload key | Warn if no trader/time/instrument-like key is selected. |
| Custom fields | `custom_fields[]` | Repeatable rows: `name`, `type`, `required`, `description`, `default` | `ctx.values[name]` | Block duplicate names and invalid identifiers. |
| Payload preview | sample payload | JSON preview, derived from selected schema | None | Warn if sample misses required fields. |

Ideal YAML additions:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `standard_fields` | `string_list` | always | built-in standard alert fields |
| `custom_fields` | `array<object>` | always | manual |
| `strict_required_fields` | `boolean` | advanced | manual |

### `TIME_WINDOW`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Context anchor | `event_time_key`, `end_time_key` | Context-key dropdowns | `ctx.values[output_name]` window object | Block if `event_time_key` cannot resolve and no literal fallback exists. |
| Literal anchor | `start_time_literal`, `end_time_literal` | Date/time picker or ISO text | `ctx.values[output_name]` window object | Block invalid timestamps. |
| Point window | `pre_minutes`, `post_minutes` | Numeric controls | Start/end derived from one anchor | Warn if both buffers are zero and no end key/literal exists. |
| Range window | `end_time_key` or `end_time_literal`, buffers | Date/time + numeric controls | Start/end range | Block if end before start after buffers. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `anchor_mode` | enum: `context_key`, `literal` | always | fixed |
| `event_time_key` | context ref | `anchor_mode=context_key` | alert/context keys |
| `end_time_key` | context ref | `anchor_mode=context_key` | alert/context keys |
| `start_time_literal` | datetime | `anchor_mode=literal` | manual |
| `end_time_literal` | datetime | `anchor_mode=literal` | manual |
| `pre_minutes` / `post_minutes` | integer | always | manual |
| `output_name` | string | always | manual/default `window` |

### `EXECUTION_DATA_COLLECTOR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| `source=hs_client_order` | order filters, `window_key`, output | Source dropdown + filter builder | Order DataFrame, row count, provenance | Warn if query lacks trader or window filter in production mode. |
| `source=hs_execution` | execution filters, `trade_version` pin, `window_key` | Source-specific query builder | Execution DataFrame, row count, resolved query | Block or auto-pin missing `trade_version:1`. |
| `source=hs_trades` | trade filters | Source-specific query builder | Trade DataFrame | Warn if using deprecated/unsupported fields. |
| `source=hs_orders_and_executions` | order/execution combined filters | Source-specific query builder | Combined DataFrame | Warn about mixed time columns. |
| `source=hs_quotes` | quote/instrument filters | Source-specific query builder | Quote DataFrame | Require instrument/currency filter if no raw query. |
| Raw query override | `query_template` | Advanced textarea with context chips | Resolved query audit value | Warn that raw Solr syntax bypasses guided filters. |
| Loop over books | `loop_over_books`, `books` | Checkbox + chips | Concatenated output with book assignments | Show `books` only when enabled. |
| Demo CSV | `mock_csv_path` | Advanced file/path input | CSV DataFrame | Warn if CSV columns do not match selected source metadata. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `source` | enum | always | `trades.yaml.sources` |
| `filter_mode` | enum: `builder`, `raw_query` | always | fixed |
| `filters` | object | `filter_mode=builder` | source schema + context keys |
| `query_template` | textarea | `filter_mode=raw_query` | context/ref chips |
| `window_key` | value ref | optional | `TIME_WINDOW` outputs |
| `trader_filter_key` | context ref | optional | context keys |
| `loop_over_books` | boolean | source has book column | fixed |
| `books` | string_list | `loop_over_books=true` | manual/context distinct values |
| `mock_csv_path` | string | advanced | filesystem path |
| `output_name` | string | always | manual |

### `COMMS_COLLECTOR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Plain keyword scan | `keywords` | Chips | Comms dataset, `_keyword_hit`, `_matched_keywords`, hit count | Warn if no keywords/categories are supplied. |
| Category scan | `keyword_categories` | Repeatable category with keyword chips | Adds `_matched_categories`, `_hit_<category>` columns | Block empty category names and duplicate category names. |
| Hits-only side output | `emit_hits_only` | Checkbox with generated name preview | Adds `ctx.datasets[{output_name}_hits]` | Warn downstream if using hits dataset while disabled. |
| Windowed comms | `window_key` | Optional value dropdown | Filtered rows if implemented | Warn if declared but handler does not filter. |
| Raw query | `query_template` | Textarea with context chips | Connector query/audit | Warn if ignored by mock mode. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `source` | enum | future/multi-source | fixed `oculus` today |
| `query_mode` | enum: `builder`, `raw_query` | always | fixed |
| `query_template` | textarea | `query_mode=raw_query` | context chips |
| `window_key` | value ref | optional | `TIME_WINDOW` outputs |
| `keywords` | string_list | always | keyword presets + manual |
| `keyword_categories` | object/array | category scan enabled | manual |
| `emit_hits_only` | boolean | always | fixed |
| `output_name` | string | always | manual |

### `MARKET_DATA_COLLECTOR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| EBS ticks | source-specific filters | Source dropdown + instrument field | Tick dataset, tick count, provenance | Require symbol/currency unless raw query. |
| Mercury ticks | source-specific filters | Source dropdown + instrument field | Tick dataset, tick count, provenance | Same as above. |
| Windowed ticks | `window_key` | Value dropdown | Filtered ticks | Block if UI exposes `window_key` but runtime does not implement it. |
| Demo CSV | `mock_csv_path` | Advanced path | CSV DataFrame | Warn if required tick columns missing. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `source` | enum | always | `market.yaml.sources` |
| `filter_mode` | enum: `builder`, `raw_query` | always | fixed |
| `symbol_ref` | context/ref | `filter_mode=builder` | context keys |
| `window_key` | value ref | optional | `TIME_WINDOW` outputs |
| `query_template` | textarea | `filter_mode=raw_query` | context chips |
| `mock_csv_path` | string | advanced | filesystem path |
| `output_name` | string | always | manual |

### `ORACLE_DATA_COLLECTOR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Oracle orders | source-specific filters | Source dropdown + builder | Oracle order DataFrame, count, provenance | Require trader/time filter in production. |
| Oracle executions | source-specific filters | Source dropdown + builder | Oracle execution DataFrame, count, provenance | Require trader/time filter in production. |
| SQL template | `query_template` | Advanced SQL textarea | Resolved query audit value | Block unsafe multi-statement SQL if real connector supports execution. |
| Demo CSV | `mock_csv_path` | Advanced path | CSV DataFrame | Warn on schema mismatch. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `source` | enum | always | `oracle.yaml.sources` |
| `query_mode` | enum: `base_query`, `builder`, `raw_sql` | always | fixed |
| `filters` | object | `query_mode=builder` | source schema + context keys |
| `query_template` | textarea | `query_mode=raw_sql` | context chips |
| `window_key` | value ref | optional | `TIME_WINDOW` outputs |
| `mock_csv_path` | string | advanced | filesystem path |
| `output_name` | string | always | manual |

### `FEATURE_ENGINE`

`FEATURE_ENGINE` is the most important option-tree node after report/summary.
It should be a transform pipeline builder, not raw JSON.

| Operation Branch | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| `window_bucket` | `time_col`, `interval_ms`, `out_col`, optional `as` | Time column dropdown + number | Adds bucket column or publishes intermediate dataset | Require datetime-like column. |
| `time_slice` | `time_col`, `windows[]`, `out_col`, `on_miss` | Window builder with ref chips | Adds phase/slice label column | Warn overlapping windows if order matters. |
| `groupby_agg` | `by`, `aggs`, optional `as` | Multi-select group columns + reducer rows | Aggregated DataFrame, often intermediate | Require at least one group column and one aggregation. |
| `pivot` | `index`, `columns`, `values`, `aggfunc`, optional `as` | Column pickers + reducer dropdown | Pivot DataFrame, often intermediate | Warn if high-cardinality pivot column. |
| `rolling` | `window`, `col`, `agg`, `out_col` | Column picker + reducer + number | Adds rolling column | Require numeric column for numeric reducers. |
| `derive` | `out_col`, `expr` | Expression builder using vectorized columns | Adds derived column | Block Python ternary; suggest `apply_expr`. |
| `apply_expr` | `out_col`, `expr` | Advanced code-ish field | Adds derived column via row eval | Warn/security gate; slower and riskier. |
| `rename` | `mapping[]` | Old column dropdown + new name | Renames columns | Block duplicate target names. |
| `lifecycle_event` | `group_by`, `sort_by`, `status_col`, `out_col` | Column pickers | Adds lifecycle transition column | Require group/status columns; sort recommended. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `input_name` | input_ref | always | upstream datasets |
| `output_name` | string | always | manual/default input name |
| `ops[].op` | enum | each op row | fixed operation registry |
| `ops[].time_col` | column_ref | `op in [window_bucket,time_slice]` | current working schema |
| `ops[].by` | column_list_ref | `op=groupby_agg` | current working schema |
| `ops[].aggs` | object/array | `op=groupby_agg` | numeric/text column reducers |
| `ops[].index/columns/values` | column_ref | `op=pivot` | current working schema |
| `ops[].expr` | expression | `op in [derive,apply_expr]` | column chips |
| `ops[].as` | string | any op | optional intermediate dataset name |

### `SIGNAL_CALCULATOR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Built-in: `FRONT_RUNNING` | `window_minutes`, `price_move_threshold` | Number controls | Signal dataset + flag count | Require `exec_time` and `exec_price` or warn signal will be all false. |
| Built-in: `WASH_TRADE` | `window_minutes`, `ratio_threshold` | Number controls | Signal dataset + flag count | Require `side`, `exec_quantity`. |
| Built-in: `SPOOFING` | `cancel_ratio_threshold`, `window` | Number + duration | Signal dataset + flag count | Require `status`. |
| Built-in: `LAYERING` | `min_layers`, `window` | Number + duration | Signal dataset + flag count | Require `order_type`, `side`. |
| Upload script | `script_content` or `script_path`, `params` | Advanced/admin code editor | Signal dataset + flag count | Hide unless `DBSHERPA_ALLOW_UPLOAD_SCRIPT` is enabled. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `mode` | enum: `configure`, `upload_script` | always | server capability should remove disabled values |
| `signal_type` | enum | `mode=configure` | built-in signal registry |
| `params.window_minutes` | integer | `FRONT_RUNNING` / `WASH_TRADE` | fixed |
| `params.price_move_threshold` | number | `FRONT_RUNNING` | fixed |
| `params.ratio_threshold` | number | `WASH_TRADE` | fixed |
| `params.cancel_ratio_threshold` | number | `SPOOFING` | fixed |
| `params.min_layers` | integer | `LAYERING` | fixed |
| `script_content` | code | `mode=upload_script` | manual |
| `output_name` | string | always | manual |

### `DATA_HIGHLIGHTER`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Preset rules | preset selection | Checkboxes: signal hits, keyword hits, buy/sell, cancelled | Highlight dataset | Warn if preset columns are absent. |
| Rule builder | `rules[]` builder | Column, operator, value/ref, colour, label | Highlight dataset | Block invalid condition builder rows. |
| Raw expression | `condition` text | Advanced expression textarea | Highlight dataset | Warn rule may be skipped if eval fails. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `input_name` | input_ref | always | upstream datasets |
| `output_name` | string | always | default `{input_name}_highlighted` |
| `rule_mode` | enum: `presets`, `builder`, `raw` | always | fixed |
| `preset_rules` | string_list | `rule_mode=presets` | available columns |
| `rules[].left` | column/ref | `rule_mode=builder` | columns + refs |
| `rules[].operator` | enum | `rule_mode=builder` | fixed |
| `rules[].value` | scalar/ref | `rule_mode=builder` | manual/ref |
| `rules[].condition` | string | `rule_mode=raw` | manual |

### `DECISION_RULE`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Threshold mode | `review_threshold`, `escalate_threshold`, `severity_map`, `output_branches` | Number ladder + severity selectors | Disposition, severity, score, flag_count, branch | Block `escalate_threshold < review_threshold`. |
| Rules mode | `rules[]`, fallback thresholds or fallback disposition | Ordered rule builder | Same fixed outputs plus matched rule | Warn if no fallback exists. |
| Raw rule expression | `rules[].when` text | Advanced ref expression | Same | Warn unresolved refs evaluate false. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `mode` | enum: `threshold`, `rules` | always | fixed |
| `input_name` | input_ref | always | signal datasets |
| `review_threshold` | integer | `mode=threshold` or fallback enabled | fixed |
| `escalate_threshold` | integer | `mode=threshold` or fallback enabled | fixed |
| `rules[].name` | string | `mode=rules` | manual |
| `rules[].when` | ref comparison | `mode=rules` | dataset/context refs |
| `rules[].disposition` | enum | `mode=rules` | `ESCALATE`, `REVIEW`, `DISMISS` |
| `rules[].severity` | enum | `mode=rules` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `severity_map` | object | advanced | fixed dispositions |
| `output_branches` | object | advanced | manual |

### `GROUP_BY`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Basic grouping | `input_name`, `group_by_column`, `output_prefix`, `keys_output_name` | Dataset dropdown + column picker | Dynamic datasets and keys object | Block if column absent. |
| Null handling | `dropna` | Checkbox | Changes grouping keys | Warn if many nulls are excluded. |
| Key ordering | `order` | Enum | Ordered keys list | Warn if mixed types cannot sort. |
| Key naming | optional slug/sanitize mode | Enum | Safe dynamic dataset names | Warn raw keys may create awkward dataset names. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `input_name` | input_ref | always | upstream datasets |
| `group_by_column` | column_ref | always | columns(input_name) |
| `output_prefix` | string | always | default from input + column |
| `keys_output_name` | string | always | default from input + column |
| `dropna` | boolean | always | fixed |
| `order` | enum | always | `first_seen`, `sort`, `desc` |
| `key_slug_mode` | enum | advanced | `raw`, `safe_slug`, `hash_suffix` |

### `MAP`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Key-only map | `keys_key`, `iteration_ctx_key`, `sub_workflow`, collections | Value dropdown + nested workflow editor | Aggregate result object | Block if keys object is not `{values:[...]}`. |
| Dataset fan-out map | `dataset_prefix`, `iteration_dataset_alias` | Generated dataset family selector | Child alias + collected datasets | Require alias when prefix is set. |
| Collect values | `collect_values` | Multi-select from child scalar outputs | `ctx.values[output_name].results[key][name]` | Warn if selected child output missing. |
| Collect datasets | `collect_datasets` | Multi-select from child dataset outputs | Dynamic top-level datasets | Show generated dataset names. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `keys_key` | value_ref | always | `EXTRACT_LIST` / `GROUP_BY` outputs |
| `iteration_ctx_key` | string | always | manual |
| `dataset_prefix` | string/dynamic_dataset_family | optional | `GROUP_BY.output_prefix` |
| `iteration_dataset_alias` | string | `dataset_prefix` set | manual/default source-like name |
| `sub_workflow` | workflow | always | nested visual editor |
| `collect_values` | string_list | after sub-workflow exists | child ctx value outputs |
| `collect_datasets` | string_list | after sub-workflow exists | child dataset outputs |
| `output_name` | string | always | manual |

### `EXTRACT_LIST`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Unique values | `input_name`, `column`, `order`, `dropna`, `output_name` | Dataset + column picker | `ctx.values[output_name] = {values:[...]}` | Warn if high cardinality creates too many map iterations. |
| Sorted list | `order=sort` or `desc` | Enum | Sorted values | Warn if values have mixed incomparable types. |
| First-seen list | `order=first_seen` | Enum | Stable input-order values | None. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `input_name` | input_ref | always | upstream datasets |
| `column` | column_ref | always | columns(input_name) |
| `order` | enum | always | `first_seen`, `sort`, `desc` |
| `dropna` | boolean | always | fixed |
| `max_values` | integer | advanced | manual |
| `output_name` | string | always | default `{input_name}_{column}_values` |

### `EXTRACT_SCALAR`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Column reducer | `column`, `reducer`, `output_name` | Column picker + reducer dropdown | Scalar context value | Block numeric reducers on non-numeric columns unless supported by pandas. |
| Row count | `reducer=row_count`, `output_name` | Reducer dropdown, hide column | Scalar count | None. |
| Unique single | `column`, `fail_on_ambiguous` | Column picker + checkbox | One scalar | Warn if multiple values found unless strict mode enabled. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `input_name` | input_ref | always | upstream datasets |
| `reducer` | enum | always | `row_count`, `first`, `unique_single`, `max`, `min`, `count`, `sum`, `mean`, `any`, `all` |
| `column` | column_ref | `reducer != row_count` | columns(input_name) |
| `fail_on_ambiguous` | boolean | `reducer=unique_single` | fixed |
| `output_name` | string | always | generated default |

### `SECTION_SUMMARY`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| `templated_stats` | `stats`, implicit stat toggles, `template` | Stat builder + textarea | Section object | Warn if no stats and no template. |
| `fact_pack_llm` | `facts`, `required_facts`, strictness, LLM prompt | Fact builder + required checkboxes | Section object with fact verification | Block required fact names not in facts. |
| `event_narrative` | `sort_by`, `event_fields`, `event_template`, `max_events`, LLM prompt | Column multi-select + generated template | Section object with event count | Warn if no sort time column. |
| `dataset_llm` | `columns`, `max_rows`, `format`, LLM prompt | Dataset slice builder | Section object with row/column counts | Block uncapped full dataset. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `mode` | enum | always | summary modes |
| `input_name` | input_ref | always | upstream datasets |
| `stats` | array | `templated_stats` | columns + reducers |
| `facts` | array | `fact_pack_llm` | columns + reducers |
| `required_facts` | string_list | `fact_pack_llm` | `facts[].name` |
| `sort_by` | column_ref | `event_narrative` | columns(input_name), time first |
| `event_fields` | column_list_ref | `event_narrative` | columns(input_name) |
| `columns` | column_list_ref | `dataset_llm` | columns(input_name) |
| `llm_prompt_template` | textarea | LLM modes | prompt chips |

### `CONSOLIDATED_SUMMARY`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| LLM stitch | `include_sections`, `section_order`, `llm_prompt_template`, `prompt_context` | Section checklist + prompt textarea | Executive summary | Warn if no sections exist. |
| Template stitch | `include_sections`, `section_order`, `template` | Section checklist + template | Executive summary | Warn unresolved section placeholders. |
| Skip | no summary body fields | Toggle/mode | Empty or unchanged executive summary | Warn report may omit executive summary. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `mode` | enum: `llm_stitch`, `template_stitch`, `none` | always | fixed |
| `include_sections` | string_list | not `none` | `ctx.sections` / upstream section nodes |
| `section_order` | string_list | not `none` | selected sections |
| `llm_prompt_template` | textarea | `llm_stitch` | prompt chips |
| `template` | textarea | `template_stitch` | section/context chips |
| `prompt_context` | object | `llm_stitch`, advanced | refs/dataset block |

### `REPORT_OUTPUT`

| Branch / Option | Show These Fields | Widget Shape | Runtime Writes | Block / Warn |
| --- | --- | --- | --- | --- |
| Excel workbook | `tabs`, summary toggles, cover toggle | Multi-tab builder | `.xlsx` + `report_path` | Warn duplicate/truncated sheet names. |
| CSV single dataset | `dataset`, `columns`, delimiter | Dataset + column picker | `.csv` + `report_path` | Block multiple datasets; suggest `zip_csv` or Excel. |
| ZIP of CSVs | `files[]`, dynamic files | File builder | `.zip` + `report_path` | Warn duplicate filenames. |
| PDF report | section controls, evidence tables, page settings | Section checklist + capped evidence tables | `.pdf` + `report_path` | Block uncapped large evidence tables. |
| HTML report | section controls, evidence tables | Similar to PDF | `.html` + `report_path` | Warn if intended for archival use. |
| JSON result | include toggles | Checkbox groups | `.json` + `report_path` | Warn before including full datasets. |

Ideal option tree:

| Config Key | Type | Visible When | Options Source |
| --- | --- | --- | --- |
| `format` | enum | always | `excel`, `csv`, `zip_csv`, `pdf`, `html`, `json` |
| `output_path` | string | always | manual + context chips |
| `tabs` | array | `format=excel` | dataset refs + dynamic refs |
| `dataset` | input_ref | `format=csv` | upstream datasets |
| `files` | array | `format=zip_csv` | upstream datasets |
| `sections` | string_list | `format in [pdf, html]` | section outputs |
| `evidence_tables` | array | `format in [pdf, html]` | dataset refs + columns |
| `include_full_datasets` | boolean | `format=json`, advanced | fixed |

## Option Tree Implementation Notes

The current `ParamType` set is not enough for the UX above. These do not need
to be Python runtime types immediately, but the YAML schema should support them
as UI/validation hints:

| Needed Type / Hint | Purpose | Used By |
| --- | --- | --- |
| `column_ref` | One column from a selected dataset | summaries, feature ops, extractors, group-by, highlighter |
| `column_list_ref` | Multiple columns from a selected dataset | report columns, event fields, dataset LLM |
| `context_ref` | One key from `ctx.values` / alert payload | time window, collectors, prompts |
| `value_ref` | A `ctx.values` object/scalar output | `MAP.keys_key`, collector `window_key` |
| `dataset_family_ref` | Dynamic dataset prefix produced by `GROUP_BY` / `MAP` | `MAP`, `REPORT_OUTPUT` |
| `ref_expression` | `{dataset.column.agg}` or `{context.key}` expression | decision rules, highlighter rules, report expansion |
| `visible_if` | Hide irrelevant mode fields | all mode-driven nodes |
| `item_schema` | Define rows inside array params | feature ops, report tabs, rules, facts |
| `advanced` | Hide dangerous/raw controls by default | raw query, SQL, upload script, apply expr |

If these hints exist in YAML, the frontend can render guided forms and the
validator can enforce the same contract without hard-coding special cases per
node.

## Developer Build Blueprint

This is the clean design to hand to a development team. The goal is to support
trade surveillance today, but any future data workflow + reporting use case
tomorrow.

### North Star

Build a small workflow platform around typed node contracts.

Each node should declare:

- what it consumes;
- what it produces;
- which config fields are real user choices;
- which config fields can be inferred from parent outputs;
- which fields are mode-specific;
- which fields reference dataset columns, context values, sections, or dynamic dataset families.

The builder should never force users to manually repeat information already
available from upstream nodes.

### Core Runtime Model

Keep the current `RunContext` model, but formalize it:

| Runtime Store | Purpose | Examples |
| --- | --- | --- |
| `ctx.alert_payload` | immutable workflow invocation input | raw alert JSON |
| `ctx.values` | scalar/object context | `trader_id`, `window`, `flag_count`, `per_book` |
| `ctx.datasets` | DataFrames | `orders`, `executions_signals`, `comms_hits` |
| `ctx.sections` | report sections | `trade_analysis`, `comms_narrative` |
| `ctx.executive_summary` | final narrative summary | executive summary text |
| `ctx.report_path` | terminal artifact path | `output/report.xlsx` |

Do not expose this storage model directly as user configuration. It should power
dropdowns, validation, and defaults.

### Node Contract Schema

Every YAML node spec should support this shape:

```yaml
type_id: SECTION_SUMMARY
description: "Create a report section from a dataset"

inputs:
  - name: dataset
    kind: dataframe
    source_config_key: input_name
    required: true

outputs:
  - name: section
    kind: section
    store_at: "ctx.sections[{section_name}]"
    schema:
      required_keys: [name, mode, stats, narrative, dataset]

params:
  - name: input_name
    type: input_ref
    required: true

  - name: mode
    type: enum
    enum: [templated_stats, fact_pack_llm, event_narrative, dataset_llm]
    default: templated_stats

  - name: facts
    type: array
    visible_if: {mode: fact_pack_llm}
    item_schema: {}

ui:
  palette_section: narrative
  advanced_fields: [prompt_context]

validation:
  column_refs:
    - facts[].column
    - stats[].column
```

The exact names can differ, but these ideas must exist:

| Contract Feature | Why It Matters |
| --- | --- |
| `source_config_key` | Connects a wireable input to config like `input_name`. |
| `visible_if` | Prevents irrelevant config fields from showing. |
| `item_schema` | Makes arrays render as builders instead of raw JSON. |
| `column_ref` | Lets UI/validator use upstream schema. |
| `context_ref` | Lets nodes pick alert/runtime values safely. |
| `value_ref` | Lets nodes consume scalar/object outputs like windows and map keys. |
| `dataset_family_ref` | Lets `MAP` and reports understand dynamic outputs. |
| `ref_expression` | Supports `{dataset.column.agg}` with validation. |
| `advanced` | Hides raw SQL, raw expressions, script upload, mock CSV paths. |

### Parent-To-Child Inference

When a user connects node A to node B, the builder should use A's outputs to
pre-fill B's config.

| Parent Output | Child Field To Auto-Fill | Example |
| --- | --- | --- |
| Dataset output | `input_name` | `SIGNAL_CALCULATOR.input_name = executions_features` |
| Value object output | `window_key`, `keys_key` | `EXECUTION_DATA_COLLECTOR.window_key = window` |
| Dataset schema | column dropdowns | `GROUP_BY.group_by_column` options from `orders` |
| Dynamic dataset family | `dataset_prefix` | `MAP.dataset_prefix = orders_by_book` |
| Section output | `include_sections` | `CONSOLIDATED_SUMMARY` section checklist |
| Highlighted dataset sibling | `include_highlights` suggestion | Report tab can use `signals_highlighted` |

The child should still let users override the inferred value when multiple
parent outputs are available.

### Three-Layer System Design

#### Layer 1: Node Registry

Responsibilities:

- load YAML specs;
- attach Python handlers;
- expose node contracts to frontend/API;
- expose data-source metadata;
- expose server capabilities such as `upload_script_enabled`.

Should not:

- hard-code frontend rendering logic;
- duplicate source schemas already in `data_sources/metadata`.

#### Layer 2: Workflow Compiler / Validator

Responsibilities:

- resolve edges into typed inputs;
- infer parent-derived defaults;
- build column lineage;
- validate config shape and mode-specific fields;
- validate every `column_ref`, `context_ref`, `value_ref`, `dataset_family_ref`, and `ref_expression`;
- produce actionable errors for the UI and Copilot.

Should validate:

- unknown node types;
- missing required params;
- bad enum values;
- bad mode-specific combinations;
- unknown dataset refs;
- unknown columns;
- invalid dynamic report tabs;
- unsafe script/raw SQL controls when disabled;
- required signal columns by signal type.

#### Layer 3: Executor

Responsibilities:

- run nodes in topological order;
- pass `RunContext`;
- enforce runtime port schemas;
- write artifacts;
- capture node outputs for trace/debug.

Should not:

- silently accept invalid node configs that the validator could catch;
- rely on frontend-only validation.

### UI Builder Principles

The UI should follow this hierarchy:

1. Pick node.
2. Connect parent.
3. Auto-infer input/output defaults.
4. Pick mode.
5. Configure mode-specific business choices.
6. Hide advanced/raw fields by default.

Examples:

| Node | User Should Configure | User Should Not Manually Repeat |
| --- | --- | --- |
| `SECTION_SUMMARY` | stats/facts/events/prompt | parent source schema |
| `SIGNAL_CALCULATOR` | signal type and thresholds | signal output columns |
| `GROUP_BY` | grouping column | parent dataset columns by hand |
| `MAP` | sub-workflow and collections | raw generated dataset names unless overriding |
| `REPORT_OUTPUT` | format and layout | all available datasets manually if auto-include is selected |

### Scalable Node Vocabulary

Keep the node palette small:

| Category | Nodes |
| --- | --- |
| Trigger | `ALERT_TRIGGER` |
| Collect | Solr/trade collector, comms collector, market collector, SQL/Oracle collector |
| Transform | `TIME_WINDOW`, `FEATURE_ENGINE`, `GROUP_BY`, `MAP`, `EXTRACT_LIST`, `EXTRACT_SCALAR`, `DATA_HIGHLIGHTER` |
| Detect / Decide | `SIGNAL_CALCULATOR`, `DECISION_RULE` |
| Narrative | `SECTION_SUMMARY`, `CONSOLIDATED_SUMMARY` |
| Output | `REPORT_OUTPUT` |

Do not create one node per scenario. FX front-running, FI wash trade, FISL, and
future scenarios should be mostly configuration over the same nodes.

### Data Workflow Generalization

To scale beyond surveillance, avoid surveillance-specific assumptions in core
contracts:

| Current Surveillance Concept | Generalized Platform Concept |
| --- | --- |
| alert payload | run input |
| trader/book/currency pair | context fields |
| orders/executions/comms | datasets |
| signal columns | standardized derived columns |
| section summary | narrative block |
| Excel report | output artifact |
| disposition | decision result |

Surveillance nodes can provide presets, but the core runtime should work for
any tabular data workflow.

### Recommended Build Sequence

#### Phase 1: Contract Schema

Implement YAML support for:

- `visible_if`;
- `item_schema`;
- `column_ref`;
- `column_list_ref`;
- `context_ref`;
- `value_ref`;
- `dataset_family_ref`;
- `ref_expression`;
- `advanced`;
- `capability_required`.

Deliverable:

- Updated node specs can describe UI and validation without Python sniffing.

#### Phase 2: Lineage And Inference

Implement a graph compiler that derives:

- datasets available at each node;
- values available at each node;
- sections available at each node;
- columns available for each dataset;
- dynamic dataset families from `GROUP_BY` and `MAP`;
- generated columns from `FEATURE_ENGINE`, `SIGNAL_CALCULATOR`, `COMMS_COLLECTOR`, and `DATA_HIGHLIGHTER`.

Deliverable:

- Parent outputs automatically populate child dropdowns and defaults.

#### Phase 3: Universal Validator

Extend validation from node-specific checks to contract-driven checks:

- all column refs;
- all context refs;
- all value refs;
- all ref expressions;
- all mode-specific required fields;
- all report format constraints.

Deliverable:

- Invalid workflows fail before runtime with precise UI-highlightable errors.

#### Phase 4: Guided UI Forms

Build renderers for:

- enum/select;
- checkboxes;
- chips;
- dataset dropdown;
- column picker;
- ref picker;
- repeatable item builders;
- nested workflow editor for `MAP`;
- mode-specific panels;
- advanced panels.

Deliverable:

- Users configure workflows through guided controls instead of raw JSON.

#### Phase 5: Runtime Cleanup

Fix current drifts while preserving backward compatibility:

- `ORACLE_DATA_COLLECTOR` template injection.
- `MARKET_DATA_COLLECTOR.window_key`.
- `DECISION_RULE` default mismatch.
- `SECTION_SUMMARY.row_count` fact.
- `REPORT_OUTPUT.format`.
- legacy config aliases such as `summary_mode`, `field_bindings`, `map_tab_sets`.

Deliverable:

- Existing workflows still run, new workflows use clean contracts.

### Backward Compatibility Strategy

Do not break existing workflow JSON immediately.

Use migration aliases:

| Old Config | New Config |
| --- | --- |
| `SECTION_SUMMARY.field_bindings` | `SECTION_SUMMARY.stats` |
| `SECTION_SUMMARY.mode=templated` | `mode=templated_stats` |
| `SECTION_SUMMARY.summary_mode` | `mode` |
| `REPORT_OUTPUT.tabs` | `format=excel`, `tabs` |
| `REPORT_OUTPUT.map_tab_sets` | `tabs[].tab_type=map_result` |
| `FEATURE_ENGINE.operations` | `ops` |
| `DECISION_RULE.flag_count_expr` | `rules[]` or threshold mode |

Add migration warnings so authors learn the new shape.

### Definition Of Done

The design is clean when:

- a child node can infer valid inputs from its parent edge;
- every dropdown is populated from actual upstream outputs or metadata;
- every column selection is validated before run;
- every mode hides irrelevant fields;
- every repeatable config has an item schema;
- raw JSON is only needed in advanced/debug cases;
- all output formats are represented as modes of `REPORT_OUTPUT`;
- existing FX FRO, FISL, and FI wash workflows can be migrated without custom nodes.
