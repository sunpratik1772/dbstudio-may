# Node Contract Final Blueprint

This is the clean end-to-end design for the workflow builder and node runtime.
It consolidates the audit findings into a developer-ready build document.

The goal is to scale from the current trade surveillance workflows to any
tabular data workflow and reporting use case without creating a new node for
every scenario.

## 1. Product Goal

Users should build workflows by connecting a small set of powerful nodes.

The builder should infer as much as possible from parent outputs:

- upstream datasets populate dataset dropdowns;
- upstream schemas populate column pickers;
- upstream scalar/object outputs populate value pickers;
- upstream section outputs populate report/summary section selectors;
- dynamic outputs from `GROUP_BY` and `MAP` populate map/report controls.

Users should configure business choices, not implementation plumbing.

## 2. Core Runtime Model

Keep one shared `RunContext`, but make its shelves explicit.

| Store | Meaning | Examples |
| --- | --- | --- |
| `ctx.alert_payload` | Immutable workflow input | raw alert/request JSON |
| `ctx.values` | Scalar/object context | `trader_id`, `window`, `flag_count`, `per_book` |
| `ctx.datasets` | DataFrame outputs | `orders`, `executions_signals`, `comms_hits` |
| `ctx.sections` | Narrative report sections | `trade_analysis`, `comms_narrative` |
| `ctx.executive_summary` | Final cross-section summary | executive summary text |
| `ctx.report_path` | Final artifact path | `output/report.xlsx` |

The UI should not expose these stores as raw implementation details. It should
use them to power dropdowns, validation, defaults, and previews.

## 3. Clean Node Contract Schema

Each node spec should declare four contracts:

| Contract | Purpose |
| --- | --- |
| YAML user contract | User-facing inputs, outputs, params, UI hints, validation hints. |
| Python runtime contract | Exact config keys read and exact `RunContext` reads/writes. |
| Fixed runtime inputs | Implicit context the node reads, such as alert fields or sections. |
| Fixed runtime outputs | Stable fields/columns/objects the node always writes. |

Recommended YAML concepts:

| Feature | Purpose |
| --- | --- |
| `source_config_key` | Binds a port to a param such as `input_name`. |
| `visible_if` | Shows params only for relevant modes. |
| `item_schema` | Renders arrays as builders, not raw JSON. |
| `column_ref` | Selects one column from an input dataset. |
| `column_list_ref` | Selects multiple columns from an input dataset. |
| `context_ref` | Selects a key from alert/runtime context. |
| `value_ref` | Selects an object/scalar output from `ctx.values`. |
| `dataset_family_ref` | Selects a dynamic dataset family from `GROUP_BY` / `MAP`. |
| `ref_expression` | Validated expression like `{dataset.column.sum}`. |
| `advanced` | Hides raw SQL/code/mock/debug fields by default. |
| `capability_required` | Hides features disabled by server policy. |

Example shape:

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
    item_schema:
      name: {type: string}
      column: {type: column_ref, source: input_name}
      reducer: {type: enum, enum: [row_count, count, sum, mean, min, max, nunique, count_where]}
```

## 4. Parent-To-Child Inference

When a user connects node A to node B, B should infer defaults from A.

| Parent Output | Child Config To Fill | Example |
| --- | --- | --- |
| DataFrame output | `input_name` | `SIGNAL_CALCULATOR.input_name = executions_features` |
| Window object | `window_key` | collector uses `window` |
| Key list object | `keys_key` | `MAP.keys_key = book_keys` |
| Dataset schema | column dropdowns | `GROUP_BY.group_by_column` options |
| Dynamic dataset family | `dataset_prefix` | `orders_by_book` |
| Section object | `include_sections` | consolidated summary section list |
| Highlighted sibling dataset | `include_highlights` | report tab suggestion |

If multiple parent outputs are valid, the UI should ask the user to choose.
If only one is valid, it should auto-fill but still allow override.

## 5. Platform Layers

### Layer 1: Registry

Loads node YAML, attaches handlers, exposes node contracts, exposes data-source
metadata, and exposes server capabilities.

### Layer 2: Compiler / Validator

Resolves edges, infers parent-derived defaults, builds column lineage, validates
mode-specific config, validates refs/columns/value refs, and returns precise
UI-highlightable errors.

### Layer 3: Executor

Runs nodes in topological order, passes `RunContext`, enforces runtime schemas,
writes artifacts, and records traces.

The executor should not be the first place invalid configs are discovered.

## 6. Node Vocabulary

Keep the palette compact.

| Stage | Nodes |
| --- | --- |
| Trigger | `ALERT_TRIGGER` |
| Integrations | `EXECUTION_DATA_COLLECTOR`, `COMMS_COLLECTOR`, `MARKET_DATA_COLLECTOR`, `ORACLE_DATA_COLLECTOR` |
| Transform | `TIME_WINDOW`, `FEATURE_ENGINE`, `GROUP_BY`, `MAP`, `EXTRACT_LIST`, `EXTRACT_SCALAR`, `DATA_HIGHLIGHTER` |
| Signal / Rule | `SIGNAL_CALCULATOR`, `DECISION_RULE` |
| Narrative | `SECTION_SUMMARY`, `CONSOLIDATED_SUMMARY` |
| Output | `REPORT_OUTPUT` |

Do not create scenario-specific nodes for FX FRO, FISL, wash trade, or future
workflows. Those should be configurations of the same node vocabulary.

## 7. Per-Node Final Contracts And Pseudocode

### `ALERT_TRIGGER`

Purpose: bind run input fields into context.

User config:

| Field | Widget |
| --- | --- |
| `standard_fields` | checkbox list |
| `custom_fields[]` | repeatable `{name, type, required, description, default}` |
| `strict_required_fields` | advanced checkbox |

Inputs:

- fixed: `ctx.alert_payload`.

Outputs:

- `ctx.values[field_name]` for each bound field.
- `ctx.values.context_keys`.

Pseudocode:

```python
def handle_alert_trigger(node, ctx):
    cfg = node.config
    schema = standard_fields(cfg) + custom_fields(cfg)

    for field in schema:
        value = ctx.alert_payload.get(field.name, field.default)
        if field.required and value is missing:
            raise ValidationError(field.name)
        if value is not missing:
            ctx.set(field.name, value)

    ctx.set("context_keys", all_bound_context_values())
```

### `TIME_WINDOW`

Purpose: create a reusable time window object.

User config:

| Field | Widget |
| --- | --- |
| `anchor_mode` | enum `context_key`, `literal` |
| `event_time_key` / `end_time_key` | context-key dropdowns |
| `start_time_literal` / `end_time_literal` | datetime inputs |
| `pre_minutes` / `post_minutes` | numeric controls |
| `output_name` | text, default `window` |

Inputs:

- fixed: `ctx.values`.

Outputs:

- `ctx.values[output_name] = {start_time, end_time, buffer_minutes}`.

Pseudocode:

```python
def handle_time_window(node, ctx):
    cfg = node.config

    if cfg.anchor_mode == "context_key":
        start = parse_time(ctx.get(cfg.event_time_key))
        end = parse_time(ctx.get(cfg.end_time_key)) if cfg.end_time_key else start
    else:
        start = parse_time(cfg.start_time_literal)
        end = parse_time(cfg.end_time_literal) if cfg.end_time_literal else start

    if start is None:
        ctx.set(cfg.output_name, {})
        return

    start = start - minutes(cfg.pre_minutes)
    end = (end or start) + minutes(cfg.post_minutes)

    ctx.set(cfg.output_name, {
        "start_time": iso(start),
        "end_time": iso(end),
        "buffer_minutes": {"pre": cfg.pre_minutes, "post": cfg.post_minutes},
    })
```

### `EXECUTION_DATA_COLLECTOR`

Purpose: collect Solr trade/order/execution/quote rows.

User config:

| Field | Widget |
| --- | --- |
| `source` | dropdown from `trades.yaml` |
| `filter_mode` | enum `builder`, `raw_query` |
| `filters` | source-specific filter builder |
| `query_template` | advanced textarea |
| `window_key` | value dropdown from `TIME_WINDOW` |
| `trader_filter_key` | context-key dropdown |
| `loop_over_books` / `books` | checkbox + chips |
| `mock_csv_path` | advanced path |
| `output_name` | text |

Inputs:

- fixed: `ctx.values` for query refs/window/trader filter.
- optional: `ctx.values[window_key]`.

Outputs:

- `ctx.datasets[output_name]`.
- `ctx.values[{output_name}_count]`.
- `ctx.values[_{output_name}_resolved_query]`.
- dataset provenance.

Pseudocode:

```python
def handle_execution_data_collector(node, ctx):
    cfg = node.config
    source = cfg.source

    query = build_query_from_filters(cfg.filters, ctx) if cfg.filter_mode == "builder" else render(cfg.query_template, ctx)
    query = enforce_source_hard_rules(source, query)

    if cfg.mock_csv_path:
        df = read_csv_or_mock(cfg.mock_csv_path, source, ctx)
    else:
        df = connector_or_mock_query(source, query, ctx)

    df = filter_by_context_trader(df, ctx.get(cfg.trader_filter_key))
    df = apply_window_if_present(df, ctx.get(cfg.window_key), source_time_column(source))

    if cfg.loop_over_books:
        df = repeat_or_filter_for_books(df, cfg.books)

    ctx.datasets[cfg.output_name] = df
    ctx.set(f"{cfg.output_name}_count", len(df))
    ctx.set(f"_{cfg.output_name}_resolved_query", query)
    record_provenance(cfg.output_name, source)
```

### `COMMS_COLLECTOR`

Purpose: collect communications and annotate keyword/category hits.

User config:

| Field | Widget |
| --- | --- |
| `source` | dropdown, default `oculus` |
| `query_mode` | enum `builder`, `raw_query` |
| `query_template` | textarea |
| `window_key` | value dropdown |
| `keywords` | chips |
| `keyword_categories` | category builder |
| `emit_hits_only` | checkbox |
| `mock_csv_path` | advanced path |
| `output_name` | text |

Outputs:

- `ctx.datasets[output_name]`.
- `ctx.values[{output_name}_keyword_hits]`.
- optional `ctx.datasets[{output_name}_hits]`.
- optional `ctx.values[{output_name}_hits_count]`.

Pseudocode:

```python
def handle_comms_collector(node, ctx):
    cfg = node.config
    query = build_or_render_query(cfg, ctx)
    df = read_csv_or_query_or_mock(cfg.mock_csv_path, query, ctx)

    df = apply_window_if_present(df, ctx.get(cfg.window_key), "timestamp")
    df["_matched_keywords"] = scan_keywords(df["display_post"], cfg.keywords)
    df["_keyword_hit"] = df["_matched_keywords"].map(bool)

    if cfg.keyword_categories:
        df["_matched_categories"] = scan_categories(df["display_post"], cfg.keyword_categories)
        for category in cfg.keyword_categories:
            df[f"_hit_{category}"] = df["_matched_categories"].contains(category)

    ctx.datasets[cfg.output_name] = df
    ctx.set(f"{cfg.output_name}_keyword_hits", sum(df["_keyword_hit"]))

    if cfg.emit_hits_only:
        hits = df[df["_keyword_hit"]].reset_index(drop=True)
        ctx.datasets[f"{cfg.output_name}_hits"] = hits
        ctx.set(f"{cfg.output_name}_hits_count", len(hits))
```

### `MARKET_DATA_COLLECTOR`

Purpose: collect normalized market ticks.

User config:

| Field | Widget |
| --- | --- |
| `source` | dropdown from `market.yaml` |
| `filter_mode` | enum `builder`, `raw_query` |
| `symbol_ref` | context/ref picker |
| `window_key` | value dropdown |
| `query_template` | advanced textarea |
| `mock_csv_path` | advanced path |
| `output_name` | text |

Outputs:

- `ctx.datasets[output_name]`.
- `ctx.values[{output_name}_tick_count]`.
- provenance.

Pseudocode:

```python
def handle_market_data_collector(node, ctx):
    cfg = node.config
    query = build_market_query(cfg, ctx)
    df = read_csv_or_query_or_mock(cfg.mock_csv_path, cfg.source, query, ctx)

    df = normalize_market_columns(df)
    df = apply_window_if_present(df, ctx.get(cfg.window_key), "timestamp")

    ctx.datasets[cfg.output_name] = df
    ctx.set(f"{cfg.output_name}_tick_count", len(df))
    record_provenance(cfg.output_name, cfg.source)
```

### `ORACLE_DATA_COLLECTOR`

Purpose: collect rows from warehouse extracts.

User config:

| Field | Widget |
| --- | --- |
| `source` | dropdown from `oracle.yaml` |
| `query_mode` | enum `base_query`, `builder`, `raw_sql` |
| `filters` | source-specific filter builder |
| `query_template` | advanced SQL textarea |
| `window_key` | optional value dropdown |
| `mock_csv_path` | advanced path |
| `output_name` | text |

Outputs:

- `ctx.datasets[output_name]`.
- `ctx.values[{output_name}_count]`.
- `ctx.values[_{output_name}_resolved_query]`.
- provenance.

Pseudocode:

```python
def handle_oracle_data_collector(node, ctx):
    cfg = node.config

    if cfg.query_mode == "base_query":
        query = metadata_base_query(cfg.source)
    elif cfg.query_mode == "builder":
        query = build_sql_from_filters(cfg.source, cfg.filters, ctx)
    else:
        query = render_template(cfg.query_template, ctx)

    df = read_csv_or_query_or_mock(cfg.mock_csv_path, cfg.source, query, ctx)
    df = apply_window_if_present(df, ctx.get(cfg.window_key), source_time_column(cfg.source))

    ctx.datasets[cfg.output_name] = df
    ctx.set(f"{cfg.output_name}_count", len(df))
    ctx.set(f"_{cfg.output_name}_resolved_query", query)
    record_provenance(cfg.output_name, cfg.source)
```

### `FEATURE_ENGINE`

Purpose: apply a typed transform pipeline to a dataset.

User config:

| Field | Widget |
| --- | --- |
| `input_name` | dataset dropdown |
| `output_name` | text |
| `ops[]` | operation builder |

Supported operation branches:

| Operation | Key Fields |
| --- | --- |
| `window_bucket` | `time_col`, `interval_ms`, `out_col`, `as` |
| `time_slice` | `time_col`, `windows[]`, `out_col`, `on_miss` |
| `groupby_agg` | `by`, `aggs`, `as` |
| `pivot` | `index`, `columns`, `values`, `aggfunc`, `as` |
| `rolling` | `window`, `col`, `agg`, `out_col` |
| `derive` | `out_col`, vector expression |
| `apply_expr` | `out_col`, advanced row expression |
| `rename` | `mapping[]` |
| `lifecycle_event` | `group_by`, `sort_by`, `status_col`, `out_col` |

Outputs:

- final `ctx.datasets[output_name]`.
- optional intermediate `ctx.datasets[ops[].as]`.
- derived-column lineage metadata.

Pseudocode:

```python
def handle_feature_engine(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]
    schema = lineage_schema(cfg.input_name)

    for op in cfg.ops:
        validate_op_against_schema(op, schema)
        result = apply_feature_op(df, op, ctx)

        if op.as:
            ctx.datasets[op.as] = result
            register_lineage(op.as, result.schema)
        else:
            df = result
            schema = update_schema(schema, op)

    ctx.datasets[cfg.output_name] = df
    register_lineage(cfg.output_name, schema)
```

### `SIGNAL_CALCULATOR`

Purpose: compute standard signal columns from a dataset.

User config:

| Field | Widget |
| --- | --- |
| `mode` | enum `configure`, `upload_script` |
| `signal_type` | dropdown |
| signal-specific params | typed fields |
| `script_content` / `script_path` | advanced, capability-gated |
| `input_name`, `output_name` | dropdown/text |

Outputs:

- `ctx.datasets[output_name]`.
- fixed signal columns: `_signal_flag`, `_signal_score`, `_signal_reason`, `_signal_type`, `_signal_window`.
- `ctx.values[{output_name}_flag_count]`.

Pseudocode:

```python
def handle_signal_calculator(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]

    if cfg.mode == "configure":
        validate_required_columns(df, signal_requirements(cfg.signal_type))
        df = run_builtin_signal(cfg.signal_type, df, cfg.params)
    else:
        require_capability("upload_script")
        df = run_custom_script(df, cfg.script_content or cfg.script_path, cfg.params)

    df = ensure_signal_columns(df)
    ctx.datasets[cfg.output_name] = df
    ctx.set(f"{cfg.output_name}_flag_count", int(df["_signal_flag"].sum()))
```

### `DATA_HIGHLIGHTER`

Purpose: add row-level highlight metadata.

User config:

| Field | Widget |
| --- | --- |
| `input_name`, `output_name` | dataset dropdown/text |
| `rule_mode` | enum `presets`, `builder`, `raw` |
| `preset_rules` | checkbox list |
| `rules[]` | condition builder |

Outputs:

- `ctx.datasets[output_name]`.
- fixed columns `_highlight_colour`, `_highlight_label`.

Pseudocode:

```python
def handle_data_highlighter(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name].copy()
    df["_highlight_colour"] = "#FFFFFF"
    df["_highlight_label"] = ""

    rules = compile_highlight_rules(cfg, available_schema(cfg.input_name))

    for rule in rules:
        condition = resolve_refs(rule.condition, ctx)
        mask = evaluate_condition(df, condition)
        df.loc[mask, "_highlight_colour"] = rule.colour
        df.loc[mask, "_highlight_label"] = rule.label

    ctx.datasets[cfg.output_name] = df
```

### `DECISION_RULE`

Purpose: set disposition, severity, score, and branch.

User config:

| Field | Widget |
| --- | --- |
| `mode` | enum `threshold`, `rules` |
| `input_name` | signal dataset dropdown |
| thresholds | numeric controls |
| `rules[]` | ordered ref-comparison builder |
| `severity_map`, `output_branches` | advanced maps |

Outputs:

- `ctx.disposition`.
- `ctx.output_branch`.
- `ctx.values.disposition`.
- `ctx.values.output_branch`.
- `ctx.values.severity`.
- `ctx.values.score`.
- `ctx.values.flag_count`.
- `ctx.values.matched_rule`.

Pseudocode:

```python
def handle_decision_rule(node, ctx):
    cfg = node.config
    flag_count = count_signal_flags(ctx.datasets.get(cfg.input_name), ctx.get(f"{cfg.input_name}_flag_count"))
    ctx.set("flag_count", flag_count)

    if cfg.mode == "rules":
        match = first_matching_rule(cfg.rules, ctx)
        disposition = match.disposition if match else fallback_disposition(cfg, flag_count)
        severity = match.severity if match else severity_for(disposition, cfg.severity_map)
        matched_rule = match.name if match else ""
    else:
        disposition = threshold_disposition(flag_count, cfg.review_threshold, cfg.escalate_threshold)
        severity = severity_for(disposition, cfg.severity_map)
        matched_rule = ""

    score = normalize_score(flag_count, cfg.escalate_threshold)
    branch = cfg.output_branches.get(disposition, disposition)

    ctx.disposition = disposition
    ctx.output_branch = branch
    ctx.set_many({
        "disposition": disposition,
        "output_branch": branch,
        "severity": severity,
        "score": score,
        "matched_rule": matched_rule,
    })
```

### `GROUP_BY`

Purpose: split one dataset into dynamic per-key datasets.

User config:

| Field | Widget |
| --- | --- |
| `input_name` | dataset dropdown |
| `group_by_column` | column picker |
| `output_prefix` | text/default |
| `keys_output_name` | text/default |
| `dropna`, `order`, `key_slug_mode` | checkbox/select |

Outputs:

- `ctx.values[keys_output_name] = {values: keys}`.
- dynamic datasets `ctx.datasets[{output_prefix}_{key}]`.

Pseudocode:

```python
def handle_group_by(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]
    keys = distinct_values(df[cfg.group_by_column], dropna=cfg.dropna, order=cfg.order)

    safe_keys = normalize_keys(keys, cfg.key_slug_mode)

    for raw_key, safe_key in zip(keys, safe_keys):
        ctx.datasets[f"{cfg.output_prefix}_{safe_key}"] = df[df[cfg.group_by_column] == raw_key].reset_index(drop=True)

    ctx.set(cfg.keys_output_name, {"values": safe_keys})
    register_dataset_family(cfg.output_prefix, safe_keys)
```

### `MAP`

Purpose: run a nested workflow once per key.

User config:

| Field | Widget |
| --- | --- |
| `keys_key` | value dropdown |
| `iteration_ctx_key` | text |
| `dataset_prefix` | dynamic dataset family selector |
| `iteration_dataset_alias` | text |
| `sub_workflow` | nested workflow editor |
| `collect_values`, `collect_datasets` | child-output multi-select |
| `output_name` | text |

Outputs:

- `ctx.values[output_name] = {results: {...}}`.
- optional dynamic datasets `ctx.datasets[{output_name}_{key}_{dataset}]`.

Pseudocode:

```python
def handle_map(node, ctx):
    cfg = node.config
    keys = ctx.get(cfg.keys_key)["values"]
    results = {}

    for key in keys:
        child = fork_child_context(ctx)
        child.set(cfg.iteration_ctx_key, key)

        if cfg.dataset_prefix:
            child.datasets[cfg.iteration_dataset_alias] = ctx.datasets[f"{cfg.dataset_prefix}_{key}"]

        execute_sub_workflow(cfg.sub_workflow, child)

        per_key = {}
        for value_name in cfg.collect_values:
            per_key[value_name] = child.get(value_name)
        for dataset_name in cfg.collect_datasets:
            df = child.datasets[dataset_name]
            per_key[dataset_name] = dataset_summary_or_ref(df)
            ctx.datasets[f"{cfg.output_name}_{key}_{dataset_name}"] = df

        results[key] = per_key

    ctx.set(cfg.output_name, {"results": results})
```

### `EXTRACT_LIST`

Purpose: extract unique values from a column for fan-out.

User config:

| Field | Widget |
| --- | --- |
| `input_name` | dataset dropdown |
| `column` | column picker |
| `order` | enum |
| `dropna` | checkbox |
| `max_values` | advanced number |
| `output_name` | text/default |

Outputs:

- `ctx.values[output_name] = {values: [...]}`.

Pseudocode:

```python
def handle_extract_list(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]
    values = unique_values(df[cfg.column], dropna=cfg.dropna, order=cfg.order)

    if cfg.max_values and len(values) > cfg.max_values:
        values = values[:cfg.max_values]

    ctx.set(cfg.output_name, {"values": normalize_scalars(values)})
```

### `EXTRACT_SCALAR`

Purpose: reduce a dataset column or row set to one scalar.

User config:

| Field | Widget |
| --- | --- |
| `input_name` | dataset dropdown |
| `reducer` | enum |
| `column` | column picker, hidden for `row_count` |
| `fail_on_ambiguous` | checkbox for `unique_single` |
| `output_name` | text/default |

Outputs:

- `ctx.values[output_name] = scalar`.

Pseudocode:

```python
def handle_extract_scalar(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]

    if cfg.reducer == "row_count":
        value = len(df)
    else:
        series = df[cfg.column]
        value = reduce_series(series, cfg.reducer, fail_on_ambiguous=cfg.fail_on_ambiguous)

    ctx.set(cfg.output_name, normalize_scalar(value))
```

### `SECTION_SUMMARY`

Purpose: create one report section from one dataset.

Modes:

| Mode | Best For |
| --- | --- |
| `templated_stats` | deterministic stats / non-LLM sections |
| `fact_pack_llm` | grounded LLM narrative with exact facts |
| `event_narrative` | chronological/event prose |
| `dataset_llm` | capped dataset slice to LLM |

Outputs:

- `ctx.sections[section_name] = {name, mode, stats, narrative, dataset}`.

Pseudocode:

```python
def handle_section_summary(node, ctx):
    cfg = node.config
    df = ctx.datasets[cfg.input_name]
    slots = common_prompt_slots(ctx)

    if cfg.mode == "templated_stats":
        stats = compute_stats(df, cfg.stats, cfg.implicit_stat_toggles)
        narrative = render_template(cfg.template, stats=stats, **slots)

    elif cfg.mode == "fact_pack_llm":
        facts = compute_facts(df, cfg.facts)
        prompt = render_prompt(cfg.llm_prompt_template, facts=facts, **slots)
        narrative = call_llm(prompt)
        verification = verify_required_facts(facts, cfg.required_facts, narrative)
        if verification.missing and cfg.strictness == "retry_missing_facts":
            narrative = call_llm(add_missing_fact_instruction(prompt, verification.missing))

    elif cfg.mode == "event_narrative":
        events = build_event_lines(df, cfg.sort_by, cfg.event_fields, cfg.event_template, cfg.max_events)
        prompt = render_prompt(cfg.llm_prompt_template, events=events, **slots)
        narrative = call_llm(prompt)
        stats = {"row_count": len(df), "event_count": len(events)}

    elif cfg.mode == "dataset_llm":
        dataset_block = serialize_dataset(df, cfg.columns, cfg.max_rows, cfg.format)
        prompt = render_prompt(cfg.llm_prompt_template, dataset=dataset_block, **slots)
        narrative = call_llm(prompt)
        stats = {"row_count": len(df), "rows_sent_to_llm": min(len(df), cfg.max_rows)}

    ctx.sections[cfg.section_name] = {
        "name": cfg.section_name,
        "mode": cfg.mode,
        "stats": stats,
        "narrative": narrative,
        "dataset": cfg.input_name,
    }
```

### `CONSOLIDATED_SUMMARY`

Purpose: combine report sections into an executive summary.

Modes:

| Mode | Best For |
| --- | --- |
| `llm_stitch` | analyst executive summary |
| `template_stitch` | deterministic summary |
| `none` | skip executive summary |

Outputs:

- `ctx.executive_summary`.
- `ctx.values.executive_summary`.

Pseudocode:

```python
def handle_consolidated_summary(node, ctx):
    cfg = node.config

    if cfg.mode == "none":
        ctx.executive_summary = ""
        ctx.set("executive_summary", "")
        return

    sections = select_and_order_sections(ctx.sections, cfg.include_sections, cfg.section_order)
    section_text = render_sections_as_text(sections)
    slots = common_prompt_slots(ctx) | {"section_text": section_text}

    if cfg.mode == "template_stitch":
        summary = render_template(cfg.template, **slots)
    else:
        prompt = render_prompt(cfg.llm_prompt_template, **slots)
        summary = call_llm(prompt)

    ctx.executive_summary = summary
    ctx.set("executive_summary", summary)
```

### `REPORT_OUTPUT`

Purpose: write the final artifact.

Formats:

| Format | Shape |
| --- | --- |
| `excel` | multi-tab workbook |
| `csv` | one dataset, one file |
| `zip_csv` | many datasets, zipped CSV files |
| `pdf` | sectioned narrative report |
| `html` | browser-readable report |
| `json` | machine-readable run output |

Outputs:

- `ctx.report_path`.
- `ctx.values.report_path`.
- optional report metadata.

Pseudocode:

```python
def handle_report_output(node, ctx):
    cfg = node.config
    path = resolve_output_path(cfg.output_path, ctx, cfg.format)

    if cfg.format == "excel":
        workbook = new_workbook()
        if cfg.include_cover:
            add_cover_sheet(workbook, ctx)
        if cfg.include_executive_summary:
            add_exec_summary_sheet(workbook, ctx.executive_summary)
        if cfg.include_section_summaries:
            add_section_summary_sheet(workbook, ctx.sections)
        for tab in expand_tabs(cfg.tabs, ctx):
            df = select_dataset_for_tab(tab, ctx.datasets)
            add_dataframe_sheet(workbook, tab.name, df, include_highlights=tab.include_highlights)
        save_workbook(workbook, path)

    elif cfg.format == "csv":
        df = ctx.datasets[cfg.dataset]
        df = select_columns(df, cfg.columns)
        write_csv(df, path, delimiter=cfg.delimiter)

    elif cfg.format == "zip_csv":
        files = expand_files(cfg.files, ctx)
        write_zip_of_csvs(files, ctx.datasets, path)

    elif cfg.format == "pdf":
        doc = build_pdf_doc(ctx, cfg.sections, cfg.evidence_tables, cfg.page_settings)
        write_pdf(doc, path)

    elif cfg.format == "html":
        html = build_html_report(ctx, cfg.sections, cfg.evidence_tables)
        write_text(path, html)

    elif cfg.format == "json":
        payload = build_json_result(ctx, cfg.include_options)
        write_json(path, payload)

    ctx.report_path = path
    ctx.set("report_path", path)
    ctx.set("report_metadata", collect_report_metadata(path, cfg.format))
```

## 8. Validation Rules

The compiler/validator should enforce these before runtime:

| Area | Rule |
| --- | --- |
| Graph | known node types, no dangling edges, no cycles |
| Required params | validate only params visible for selected mode |
| Enums | values must be in allowed set |
| Dataset refs | `input_name` must resolve to upstream dataset |
| Value refs | `window_key`, `keys_key`, etc. must resolve to upstream value/object |
| Column refs | every selected column must exist in inferred schema |
| Ref expressions | `{dataset.column.agg}` and `{context.key}` must resolve |
| Signal types | required input columns must exist or produce clear warning/error |
| Report formats | CSV cannot have multiple datasets; PDF evidence tables must be capped |
| Advanced capabilities | script upload/raw code disabled unless server permits |

## 9. Backward Compatibility

Existing workflows should be migrated, not broken.

| Old Config | New Config |
| --- | --- |
| `SECTION_SUMMARY.field_bindings` | `SECTION_SUMMARY.stats` |
| `SECTION_SUMMARY.mode=templated` | `mode=templated_stats` |
| `SECTION_SUMMARY.summary_mode` | `mode` |
| `REPORT_OUTPUT.tabs` | `format=excel`, `tabs` |
| `REPORT_OUTPUT.map_tab_sets` | `tabs[].tab_type=map_result` |
| `FEATURE_ENGINE.operations` | `ops` |
| `DECISION_RULE.flag_count_expr` | `rules[]` or threshold config |
| magic `count_where_buy` | structured `{reducer: count_where, value: BUY}` |

Migration should produce warnings so workflow authors learn the clean shape.

## 10. Implementation Roadmap

### Phase 1: Contract Schema

Add YAML support for mode visibility, item schemas, column refs, value refs,
context refs, ref expressions, advanced fields, and capability gates.

### Phase 2: Lineage Compiler

Derive available datasets, values, sections, columns, dynamic dataset families,
and generated columns at every node.

### Phase 3: Contract-Driven Validator

Validate refs, columns, mode-specific fields, report formats, and advanced
capabilities through the contract schema.

### Phase 4: Guided UI

Render dataset dropdowns, column pickers, ref pickers, repeatable builders,
nested workflow editor, mode panels, and advanced sections.

### Phase 5: Runtime Cleanup

Fix known drift:

- Oracle template rendering.
- Market collector window filtering.
- Decision threshold defaults.
- Section summary row-count facts.
- Report output format modes.
- Legacy alias migrations.

## 11. Definition Of Done

The platform is clean when:

- parent outputs automatically populate child defaults and dropdowns;
- users rarely edit raw JSON;
- every mode hides irrelevant fields;
- every column/ref-bearing config is validated before run;
- repeatable params have item schemas;
- dynamic outputs from `GROUP_BY` and `MAP` are visible to downstream nodes;
- `REPORT_OUTPUT` handles Excel, CSV, zipped CSV, PDF, HTML, and JSON through modes;
- existing FX FRO, FISL, FI wash, and future data workflows use the same node vocabulary.
