# How To Onboard A Data Source

> The rule: dataset truth lives in `backend/data_sources/metadata/*.yaml`.
> Copilot prompts, validator column checks, collector dropdowns, and docs should
> consume that metadata instead of duplicating schemas.

## Where Data Sources Live

Data source metadata files live here:

```text
backend/data_sources/metadata/
```

Current examples:

- `trades.yaml` for Solr trade/order/execution/quote collections.
- `market.yaml` for market data.
- `comms.yaml` for communications.
- `oracle.yaml` for Oracle extracts.
- `signals.yaml` for signal output schema.

The loader is `backend/data_sources/registry.py`. It loads every YAML file at import time and exposes `get_registry()`.

## YAML Shape

Use this shape for a simple source:

```yaml
id: positions
description: Daily position snapshots.
sources:
  - position_keeper
columns:
  - name: trader_id
    type: string
    semantic: trader
    description: Trader under review.
  - name: as_of_date
    type: datetime
    semantic: time
  - name: notional
    type: number
    semantic: notional
```

Use `source_schemas` when one logical data source has multiple concrete collections:

```yaml
id: trades
description: Trade / order rows from Solr.
sources:
  - hs_client_order
  - hs_execution
source_schemas:
  hs_client_order:
    description: Client order rows.
    base_query: "*:*"
    columns:
      - name: order_id
        type: string
      - name: trader_id
        type: string
        semantic: trader
  hs_execution:
    description: Execution rows.
    base_query: "*:* AND trade_version:1"
    columns:
      - name: exec_id
        type: string
      - name: trade_version
        type: integer
```

## Column Fields

Each column supports:

- `name`: physical column name used in workflows.
- `type`: `string`, `number`, `integer`, `datetime`, `boolean`, etc.
- `description`: human explanation.
- `semantic`: optional meaning tag.
- `optional`: optional columns are available to Copilot/docs but not required by runtime output contracts.

Useful semantic tags include:

- `trader`
- `time`
- `price`
- `size`
- `notional`

The model may see semantic tags, but workflows must still use physical column names.

## What Metadata Drives

Data source YAML is used by:

- `PromptBuilder.system_prompt()` through `schema_hints_for_prompt()`.
- Field-binding validation in `engine/validator.py`.
- Source-keyed runtime output checks for collectors such as `EXECUTION_DATA_COLLECTOR`.
- Live node manifests and generated node docs when a node derives params/schema from the registry.

## Solr Sources

Solr trade/order sources are consolidated under `trades.yaml`.

To add another Solr collection:

1. Add the source name under `sources`.
2. Add a matching `source_schemas.<source_name>` block.
3. Add a mock generator branch in `backend/engine/nodes/execution_data_collector.py` if workflows must run offline.
4. Run artifact generation.

The UI source dropdown for `Solr Data Collector` is populated from this YAML at backend import time. After backend restart, click the node palette refresh icon or reload the app.

## Optional vs Required Columns

Only mark a column `optional: true` when:

- Real feeds may not always provide it, or
- It is fixture/scenario-specific helper data.

Required columns become runtime output-contract checks for source-keyed collectors. If a synthetic/mock collector omits a required column, tests should fail.

## Tests

Add or update tests when metadata changes any shipped path:

- Validator field-binding tests if new columns are expected in summaries.
- Golden workflow tests if the source powers a scenario.
- Runtime contract tests if a collector derives output schema from the metadata.

Run:

```bash
uv run pytest backend/tests -q
```

## Regenerate Artifacts

Run:

```bash
uv run python backend/scripts/gen_artifacts.py
```

This refreshes `node_detail.md`, backend contracts, type ids, and frontend fallback metadata.

## Checklist

- YAML file is under `backend/data_sources/metadata/`.
- Physical column names match real/synthetic data.
- Semantic tags are helpful but not invented.
- Optional columns are intentionally optional.
- Source-keyed collectors derive dropdown/schema from the YAML.
- Artifacts regenerated.
- Backend tests pass.
