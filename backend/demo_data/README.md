# Demo data fixtures

These CSVs are the mock datasets the `/run/demo` endpoint feeds into
the engine. They're the same shape the real Solr / Oculus / EBS
collectors produce — exported once from the in-code generators so the
demo path is reproducible across runs and deployments.

| File | Source collection | Shape | Notes |
|------|-------------------|-------|-------|
| `trades_hs_client_order.csv` | `hs_client_order` | 50 × 11 | Orders (LIMIT / MARKET / STOP), prices, venues, statuses. |
| `trades_hs_execution.csv`    | `hs_execution`    | 40 × 13 | Executions linked to orders; `trade_version=1` on every row. |
| `comms.csv`                  | Oculus            | 30 × 4 | Chat / voice / email messages; `_keyword_hit` is computed downstream. |
| `market.csv`                 | EBS               | 200 × 10 | Normalised FX tick data (ISO timestamps, bid/ask/mid). |

## How they're used

The `/run/demo` endpoint loads `backend/workflows/fx_fro_v2_workflow.json`
by default. That workflow sets
`config.mock_csv_path` on each collector node to point at one of
these files. At run time the collector handlers detect the config
and read the CSV verbatim instead of calling their synthetic
generator — nothing else in the pipeline knows or cares.

## Regenerating

```bash
cd backend
python scripts/gen_demo_data.py
```

Uses the exact generator functions (`_mock_hs_client_order`, …) that
production collectors fall back to when `mock_csv_path` is not set,
so the two paths stay in sync.
