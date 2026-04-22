"""
DataSourceRegistry — declarative, YAML-driven catalog of every
dataset the engine can read from.

Why this exists
---------------
Today our collector handlers hand back DataFrames whose columns are
defined implicitly by the upstream system (Solr response shape,
Oculus mapping, EBS tick feed). That's fine until:

  * A user writes `field_bindings: [{field: "trader"}]` and the real
    column is `trader_id` → silent empty stats.
  * The copilot invents a column name from prompt context → runtime
    KeyError four nodes downstream.
  * A new data source is onboarded and nobody knows which columns
    exist without reading the handler.

A registry sourced from YAML files solves all three — the column
schema becomes a checked artifact, not a handler implementation
detail.

Structure
---------
Each `metadata/<id>.yaml` declares:

    id: trades
    description: Trade/order rows from Solr hs_client_order | hs_execution
    sources:
      - hs_client_order
      - hs_execution
    columns:
      - name: trader_id
        type: string
        semantic: trader
        description: Desk-scoped trader identifier
      - name: qty
        type: number
        semantic: size
        ...

The `semantic` field drives two things:

  1. **Prompt injection** — `DataSourceRegistry.schema_hints_for_prompt()` embeds
     every source's exact column names into the LLM system prompt so the model
     never invents a column name ("size" instead of "qty").
  2. **Validator check** — `engine/validator._validate_field_bindings()` emits
     UNKNOWN_COLUMN warnings when a SECTION_SUMMARY references a column that
     doesn't exist in the resolved data source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml


METADATA_DIR = Path(__file__).parent / "metadata"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str                # "string" | "number" | "integer" | "boolean" | "datetime" | "object"
    description: str = ""
    semantic: str | None = None   # e.g. "trader", "size", "price", "time"
    optional: bool = False

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "semantic": self.semantic,
            "optional": self.optional,
        }


@dataclass(frozen=True)
class DataSource:
    id: str
    description: str
    sources: tuple[str, ...]            # downstream system identifiers (e.g. "hs_client_order")
    columns: tuple[ColumnSpec, ...]

    def column(self, name: str) -> ColumnSpec | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def semantic_map(self) -> dict[str, list[str]]:
        """Return {semantic_tag: [column_names]} for every tagged column.

        A semantic can map to multiple columns (e.g. "price" → ["bid","ask","mid"]
        on the market source).  Callers that want a single canonical column should
        take the first element.
        """
        result: dict[str, list[str]] = {}
        for c in self.columns:
            if c.semantic:
                result.setdefault(c.semantic, []).append(c.name)
        return result

    def schema_hint(self) -> str:
        """Compact, LLM-readable listing of this source's columns.

        Included verbatim in the system prompt so the model always uses real
        column names rather than inventing semantic aliases.
        """
        src_list = ", ".join(self.sources) if self.sources else self.id
        lines = [f"**{self.id}** ({src_list}) — {self.description}"]
        for c in self.columns:
            sem = f"  [semantic: {c.semantic}]" if c.semantic else ""
            opt = "  (optional)" if c.optional else ""
            lines.append(f"  - `{c.name}` ({c.type}){sem}{opt}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "sources": list(self.sources),
            "columns": [c.to_json() for c in self.columns],
        }


class DataSourceRegistry:
    """
    Immutable-after-load catalog. Instantiated once at import time
    (via `get_registry()`), read-only thereafter. Adding a new
    dataset is a single YAML file, no Python code change.
    """

    def __init__(self, sources: Iterable[DataSource]) -> None:
        self._by_id: dict[str, DataSource] = {s.id: s for s in sources}

    def get(self, source_id: str) -> DataSource | None:
        return self._by_id.get(source_id)

    def all(self) -> tuple[DataSource, ...]:
        return tuple(self._by_id.values())

    def schema_hints_for_prompt(self) -> str:
        """All data-source schemas in a single block for the LLM system prompt.

        Tells the model exactly which column names exist on each dataset.
        Semantic tags are shown as reference only — the model must use the real
        column name (e.g. `qty`, not `size`) in field_bindings and conditions.
        """
        sections = "\n\n".join(s.schema_hint() for s in self.all())
        return (
            "Use ONLY the exact column names listed below. "
            "Semantic tags describe meaning — the column name is what you write "
            "in `field_bindings`, highlight `condition`, and any config that "
            "references a column. Never invent aliases.\n\n"
            + sections
        )

    def to_json(self) -> dict:
        return {"sources": [s.to_json() for s in self.all()]}


def _parse_column(raw: dict) -> ColumnSpec:
    return ColumnSpec(
        name=raw["name"],
        type=raw.get("type", "string"),
        description=raw.get("description", ""),
        semantic=raw.get("semantic"),
        optional=bool(raw.get("optional", False)),
    )


def _parse_source(path: Path) -> DataSource:
    raw = yaml.safe_load(path.read_text())
    return DataSource(
        id=raw["id"],
        description=raw.get("description", ""),
        sources=tuple(raw.get("sources", [])),
        columns=tuple(_parse_column(c) for c in raw.get("columns", [])),
    )


def _load_all() -> DataSourceRegistry:
    sources: list[DataSource] = []
    if METADATA_DIR.is_dir():
        for path in sorted(METADATA_DIR.glob("*.yaml")):
            sources.append(_parse_source(path))
    return DataSourceRegistry(sources)


_REGISTRY: DataSourceRegistry = _load_all()


def get_registry() -> DataSourceRegistry:
    return _REGISTRY


__all__ = ["ColumnSpec", "DataSource", "DataSourceRegistry", "get_registry"]
