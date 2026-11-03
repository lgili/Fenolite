# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Validate complete CLI replies against the prepared, closed result declarations."""

from __future__ import annotations

import json
import tomllib
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import _schema

from fenolite.cli.api import PlannedWrite
from fenolite.cli.output import to_jsonable
from fenolite.cli.results import RESULTS


@cache
def result_schema(command: str) -> dict[str, Any]:
    # Prepared v1 descriptors include error/protocol branches without rewriting legacy v0 files.
    return _schema.closed(_schema.load(f"fenolite.{command}.v1.json"))


def result_problems(command: str, result: object) -> list[str]:
    if command not in RESULTS:  # synthetic commands in protocol tests have their own wire contracts
        return []
    wire = to_jsonable(result)
    return [f"{command}{problem}" for problem in _schema.validate(wire, result_schema(command))]


@lru_cache(maxsize=1)
def _formats() -> dict[str, dict[str, Any]]:
    formats = {
        raw["$id"]: raw
        for path in sorted((_schema.SCHEMAS / "formats").glob("*.json"))
        if (raw := json.loads(path.read_text()))
    }
    for identifier, schema in list(formats.items()):
        if identifier.endswith(".v1"):
            formats.setdefault(identifier[:-1] + "0", schema)
    return formats


def document_problems(writes: tuple[PlannedWrite, ...]) -> list[str]:
    """Check public documents already materialized by real writers, without evaluating deferred writes."""
    problems: list[str] = []
    formats = _formats()
    for write in writes:
        path = Path(write.path)
        if write.deferred or path.suffix not in {".json", ".toml"}:
            continue
        try:
            text = write.data.decode("utf-8")
            data = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
        except (ValueError, UnicodeError):
            continue  # unrelated JSON/TOML files have their own format tests
        if not isinstance(data, dict):
            continue
        identifier = data.get("schema")
        if path.name == "library.toml" and identifier == "fenolite.library.v0":
            identifier = "fenolite.library-metadata.v1"
        if identifier not in formats:
            continue  # canonical models and internal documents have separate schema owners
        schema = formats[identifier]
        wire = {**data, "schema": schema["$id"]}
        problems.extend(f"{write.path}{error}" for error in _schema.validate(wire, schema))
    return problems
