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

## Backend-Connected Sources

Some sources are only metadata changes. Others also need backend connection
code. Use this split:

```text
backend/data_sources/metadata/<source>.yaml       # what tables/columns exist
backend/data_sources/connectors/<source>.py       # how to connect/query
backend/engine/nodes/<source>_collector.yaml      # node params/ports/UI
backend/engine/nodes/<source>_collector.py        # handler that calls connector
```

Do not put passwords, tokens, or connection strings in metadata YAML. Metadata
is safe schema truth for Copilot, validation, docs, and UI dropdowns. Runtime
secrets belong in environment variables, with commented examples in
`backend/.env.example`.

### Redshift Example

Example goal:

- one backend data source: `redshift`
- one Studio node: `Redshift Data Loader`
- one dropdown param: `table`
- two table choices: `funds` and `hedges`

First declare the two allowed tables and their columns:

```yaml
# backend/data_sources/metadata/redshift.yaml
id: redshift
description: Reference tables from Redshift.
sources:
  - funds
  - hedges

source_schemas:
  funds:
    description: Fund reference data.
    base_query: "select fund_id, fund_name, desk, currency from reference.funds"
    columns:
      - name: fund_id
        type: string
      - name: fund_name
        type: string
      - name: desk
        type: string
      - name: currency
        type: string

  hedges:
    description: Hedge reference data.
    base_query: "select hedge_id, fund_id, instrument, hedge_ratio from reference.hedges"
    columns:
      - name: hedge_id
        type: string
      - name: fund_id
        type: string
      - name: instrument
        type: string
      - name: hedge_ratio
        type: number
```

Then add commented env vars:

```bash
# backend/.env.example
# REDSHIFT_HOST=
# REDSHIFT_PORT=5439
# REDSHIFT_DATABASE=
# REDSHIFT_USER=
# REDSHIFT_PASSWORD=
```

Create a small connector. Keep SQL construction conservative: table names come
from trusted YAML, while user values are passed as parameters.

```python
# backend/data_sources/connectors/redshift.py
import os
from typing import Any

import pandas as pd


def _connect():
    """Create a Redshift connection from environment variables."""
    return redshift_driver.connect(
        host=os.environ["REDSHIFT_HOST"],
        port=int(os.environ.get("REDSHIFT_PORT", "5439")),
        database=os.environ["REDSHIFT_DATABASE"],
        user=os.environ["REDSHIFT_USER"],
        password=os.environ["REDSHIFT_PASSWORD"],
    )


def query_table(sql: str, params: dict[str, Any]) -> pd.DataFrame:
    """Run one approved query and return a DataFrame."""
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)
```

Define a collector node whose dropdown is populated from `redshift.yaml`:

```yaml
# backend/engine/nodes/redshift_data_loader.yaml
type_id: REDSHIFT_DATA_LOADER
description: "Loads an approved Redshift table into the workflow."

ui:
  color: "#8B5CF6"
  icon: Database
  display_name: Redshift Data Loader
  config_tags: [table, output_name]
  palette:
    section:
      id: collect
      label: Collect
      order: 10
      color: "#60A5FA"
    node_order: 40

output_ports:
  - name: rows
    type: dataframe
    store_at: "ctx.datasets[{output_name}]"

params:
  - name: table
    type: enum
    description: "Redshift table declared in redshift.yaml."
    required: true
    enum: []  # filled from metadata/redshift.yaml by the Python handler
  - name: output_name
    type: string
    default: redshift_table
    required: true
```

The handler loads the metadata, replaces the dropdown enum, and runs only the
approved base query for the selected table:

```python
# backend/engine/nodes/redshift_data_loader.py
from dataclasses import replace
from pathlib import Path

from data_sources import get_registry
from data_sources.connectors.redshift import query_table

from ..context import RunContext
from ..node_spec import NodeSpec, _spec_from_yaml


def _spec_with_redshift_metadata() -> NodeSpec:
    spec = _spec_from_yaml(Path(__file__).with_suffix(".yaml"), handle_redshift_data_loader)
    redshift = get_registry().get("redshift")
    if redshift is None:
        return spec

    tables = tuple(redshift.sources)  # ("funds", "hedges")
    params = tuple(
        replace(param, enum=tables)
        if param.name == "table"
        else param
        for param in spec.params
    )

    # Optional: expose table-specific columns to Copilot/docs/runtime checks.
    required_by_table = {
        table: [c.name for c in schema.columns if not c.optional]
        for table, schema in redshift.source_schemas.items()
    }
    contract = {
        **spec.contract,
        "params": [param.to_json() for param in params],
        "output_columns_by_source": required_by_table,
    }

    return replace(spec, params=params, contract=contract)


def handle_redshift_data_loader(node: dict, ctx: RunContext) -> None:
    cfg = node.get("config") or {}
    table = cfg["table"]
    output_name = cfg.get("output_name", "redshift_table")

    redshift = get_registry().get("redshift")
    schema = redshift.source_schema(table)
    sql = schema.base_query

    # The table SQL comes from trusted YAML, not user input.
    ctx.datasets[output_name] = query_table(sql, params={})

NODE_SPEC = _spec_with_redshift_metadata()
```

The exact driver/import may differ (`psycopg`, SQLAlchemy, or the bank's
approved Redshift client), but the boundary should stay the same: YAML declares
schema; connector owns credentials/query execution; node handler maps workflow
config to an approved connector call.

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
