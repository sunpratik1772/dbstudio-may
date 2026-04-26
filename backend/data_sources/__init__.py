"""
Data source metadata package.

Each dataset the engine can read from is declared as a YAML file in
`backend/data_sources/metadata/*.yaml`. The `DataSourceRegistry`
parses those files at import time and exposes them to:

  * the validator — to check that `field_bindings[].field`,
    `field_renames` keys, and signal-script column references exist
    on the declared data source (future wiring);
  * the copilot prompt builder — to ground the LLM with real column
    names per source instead of guessing;
  * the frontend palette / config editor — to show typed column
    dropdowns instead of free-text fields.

This module ships the registry + YAML skeletons. Handlers today are
**not yet required** to consult it; adoption is incremental so we
don't force a handler rewrite before the review.
"""
from .registry import (
    ColumnSpec,
    DataSource,
    DataSourceRegistry,
    SourceSchema,
    get_registry,
    split_source_ref,
)

__all__ = [
    "ColumnSpec",
    "DataSource",
    "DataSourceRegistry",
    "SourceSchema",
    "get_registry",
    "split_source_ref",
]
