"""The always-on agentic workflow skill must stay in sync with runtime inventory."""
from __future__ import annotations

from pathlib import Path

from agent.prompt_builder import ALWAYS_ON_SKILLS, PromptBuilder
from data_sources import get_registry
from engine.registry import NODE_SPECS


SKILL_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "skills-agentic-workflow-builder.md"
)
SKILL_NAME = "skills-agentic-workflow-builder"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_agentic_workflow_skill_is_always_matched() -> None:
    pb = PromptBuilder()

    assert SKILL_NAME in ALWAYS_ON_SKILLS
    assert SKILL_NAME in pb.list_skills()
    assert pb.match_skills("Create a small unrelated workflow")[0] == SKILL_NAME


def test_agentic_workflow_skill_mentions_every_registered_node() -> None:
    text = _skill_text()

    missing = sorted(node_type for node_type in NODE_SPECS if node_type not in text)

    assert not missing, (
        "Update backend/skills/skills-agentic-workflow-builder.md when node "
        f"inventory changes. Missing node type(s): {missing}"
    )


def test_agentic_workflow_skill_mentions_every_data_source() -> None:
    text = _skill_text()
    registry = get_registry()
    missing: list[str] = []

    for source in registry.all():
        if source.id not in text:
            missing.append(source.id)
        for concrete in source.sources:
            if concrete not in text:
                missing.append(concrete)

    assert not missing, (
        "Update backend/skills/skills-agentic-workflow-builder.md when data "
        f"sources change. Missing source(s): {sorted(missing)}"
    )


def test_agentic_workflow_skill_delegates_columns_to_registry_prompt() -> None:
    text = _skill_text()

    assert "Data Source Column Schemas" in text
    assert "DataSourceRegistry" in text
    assert "do not copy column lists into this skill" in text
    assert "Use only exact columns from the data source registry:" not in text


def test_system_prompt_includes_every_registry_column() -> None:
    prompt = PromptBuilder().system_prompt()
    registry = get_registry()
    missing: list[str] = []

    for source in registry.all():
        for column in source.columns:
            if f"`{column.name}`" not in prompt:
                missing.append(f"{source.id}.{column.name}")
        for concrete, schema in source.source_schemas.items():
            for column in schema.columns:
                if f"`{column.name}`" not in prompt:
                    missing.append(f"{source.id}:{concrete}.{column.name}")

    assert not missing, (
        "PromptBuilder.system_prompt() must expose exact data-source columns "
        f"from DataSourceRegistry. Missing column(s): {missing}"
    )
