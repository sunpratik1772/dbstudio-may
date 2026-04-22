"""
Workflow schema version gate + migration seam.

Every workflow persisted on disk or submitted over the wire carries a
top-level `schema_version` (a simple dotted string like "1.0"). The
engine refuses to run a workflow whose schema is newer than it
understands, and refuses to run one whose schema is too old to migrate.

This matters because users author YAML/JSON workflows offline, hand us
the file, and expect today's file to still run tomorrow — even after
we've renamed a param or changed a node contract. Without a version
gate, yesterday's user file silently runs against a newer schema and
may produce subtly wrong results instead of failing loudly.

The migration path is deliberately small and explicit: `MIGRATIONS`
maps `from_version -> (to_version, transform)` — when someone ships
a backward-incompatible change they add a migration here and bump
`ENGINE_SCHEMA_VERSION`. Until then there are no migrations and the
gate just enforces equality.
"""
from __future__ import annotations

from typing import Callable

from .validation_codes import ValidationErrorCode


# The schema version this build understands. Bump this when you make
# any of the following changes, and add a migration below:
#   * Rename a required ParamSpec field.
#   * Remove a node type.
#   * Change the shape of the on-wire edge or node object.
#   * Introduce a new required top-level key on the workflow object.
ENGINE_SCHEMA_VERSION = "1.0"

# The oldest schema we will accept and try to migrate forward. Older
# files must be upgraded offline.
MIN_SUPPORTED_SCHEMA_VERSION = "1.0"


# Migrations are pure functions: dict -> dict. They must be
# **idempotent** and must not raise on already-migrated workflows.
Migration = Callable[[dict], dict]

MIGRATIONS: dict[str, tuple[str, Migration]] = {
    # "0.9": ("1.0", _migrate_0_9_to_1_0),
}


class SchemaVersionError(Exception):
    """Raised when a workflow's schema_version cannot be reconciled."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def coerce_version(dag: dict) -> str:
    """
    Extract a schema version from `dag`. Historical files may carry it
    at the top level as `schema_version` OR as the legacy `version`
    field. If both are absent we assume the earliest supported version
    so files predating this gate continue to load.
    """
    v = dag.get("schema_version") or dag.get("version") or MIN_SUPPORTED_SCHEMA_VERSION
    if not isinstance(v, str):
        raise SchemaVersionError(
            ValidationErrorCode.BAD_SCHEMA_VERSION,
            f"schema_version must be a string, got {type(v).__name__}.",
        )
    return v


def _parse(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError as e:
        raise SchemaVersionError(
            ValidationErrorCode.BAD_SCHEMA_VERSION, f"schema_version '{version}' is not a dotted-number string."
        ) from e


def migrate_to_current(dag: dict) -> dict:
    """
    Return `dag` migrated to the engine's current schema version.
    Raises `SchemaVersionError` if that's impossible. The input is not
    mutated; callers get a shallow copy back with `schema_version`
    stamped on.
    """
    current = coerce_version(dag)
    if _parse(current) > _parse(ENGINE_SCHEMA_VERSION):
        raise SchemaVersionError(
            ValidationErrorCode.SCHEMA_TOO_NEW,
            (
                f"Workflow schema_version '{current}' is newer than this engine "
                f"supports ('{ENGINE_SCHEMA_VERSION}'). Upgrade the backend."
            ),
        )
    if _parse(current) < _parse(MIN_SUPPORTED_SCHEMA_VERSION):
        raise SchemaVersionError(
            ValidationErrorCode.SCHEMA_TOO_OLD,
            (
                f"Workflow schema_version '{current}' is older than this engine's "
                f"minimum ('{MIN_SUPPORTED_SCHEMA_VERSION}'). Migrate the workflow offline."
            ),
        )

    migrated = dict(dag)
    migrated["schema_version"] = current
    while migrated["schema_version"] != ENGINE_SCHEMA_VERSION:
        step = MIGRATIONS.get(migrated["schema_version"])
        if step is None:
            raise SchemaVersionError(
                ValidationErrorCode.MIGRATION_MISSING,
                (
                    f"No migration from schema_version '{migrated['schema_version']}' "
                    f"to '{ENGINE_SCHEMA_VERSION}'."
                ),
            )
        next_version, transform = step
        migrated = transform(migrated)
        migrated["schema_version"] = next_version
    return migrated


__all__ = [
    "ENGINE_SCHEMA_VERSION",
    "MIN_SUPPORTED_SCHEMA_VERSION",
    "MIGRATIONS",
    "SchemaVersionError",
    "coerce_version",
    "migrate_to_current",
]
