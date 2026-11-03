# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pure, explicit migration steps for whole canonical model folders (c0218).

The candidate keeps every current field and opaque extension pending maintainer review. Public release
fixtures already decode with their defaults, so the first step changes only the schema marker.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.model.design import SCHEMA_VERSION, parse_version

Folder = dict[str, Any]


class MigrationError(FormatError):
    """An invalid version, missing path or malformed migration input."""

    cli_code = "FEN-3004"


class FutureVersionError(MigrationError):
    """A newer major/minor may hold fields that writing with this reader would lose."""

    cli_code = "FEN-3002"


@dataclass(frozen=True, slots=True)
class Step:
    from_version: str
    to_version: str
    apply: Callable[[Folder], Folder]
    notes: str


def validate_version(version: object, *, file: str = "meta.json") -> str:
    """Refuse malformed and future versions before a caller decodes unknown layer content."""
    try:
        if not isinstance(version, str):
            raise ValueError("model schema version must be a string")
        parsed = parse_version(version)
    except ValueError as exc:
        raise MigrationError(str(exc), file=file, locator="/schema_version") from None
    if parsed > parse_version(SCHEMA_VERSION):
        raise FutureVersionError(
            f"model schema version {version!r} is from a future format version; "
            f"this reader supports {SCHEMA_VERSION!r}",
            file=file,
            locator="/schema_version",
        )
    return version


def _to_one(folder: Folder) -> Folder:
    folder["meta.json"]["schema_version"] = "1.0"
    return folder


STEPS: tuple[Step, ...] = (
    Step(
        "0",
        "1.0",
        _to_one,
        "Keep all existing fields, ids, integer units and opaque fragments; update only the schema marker.",
    ),
)


def _folder(value: object, *, file: str) -> Folder:
    if not isinstance(value, dict):
        raise MigrationError("a model folder needs a meta.json object", file=file, locator="/")
    data = cast(Folder, value)
    if not isinstance(data.get("meta.json"), dict):
        raise MigrationError("a model folder needs a meta.json object", file=file, locator="/")
    return data


def migrate(folder_json: Folder, version: str, *, file: str = "meta.json") -> tuple[Folder, tuple[str, ...]]:
    """Return a migrated deep copy and the ordered steps; never mutate the caller's JSON."""
    current = validate_version(version, file=file)
    folder_json = _folder(folder_json, file=file)
    if folder_json["meta.json"].get("schema_version") != current:
        raise MigrationError(
            "version argument disagrees with meta.json", file=file, locator="/schema_version"
        )
    data: Folder = deepcopy(folder_json)
    applied: list[str] = []
    seen: set[str] = set()
    while current != SCHEMA_VERSION:
        candidates = [step for step in STEPS if step.from_version == current]
        if len(candidates) != 1 or current in seen:
            raise MigrationError(
                f"no unique migration path from model version {current!r} to {SCHEMA_VERSION!r}",
                file=file,
                locator="/schema_version",
            )
        seen.add(current)
        step = candidates[0]
        data = _folder(step.apply(data), file=file)
        if data["meta.json"].get("schema_version") != step.to_version:
            raise MigrationError(
                "migration step did not set its target version", file=file, locator="/schema_version"
            )
        applied.append(f"{step.from_version} -> {step.to_version}")
        current = validate_version(step.to_version, file=file)
    return data, tuple(applied)


__all__ = ["FutureVersionError", "MigrationError", "STEPS", "Step", "migrate", "validate_version"]
