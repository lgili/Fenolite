# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schema ids of the canonical layer files. ``tools/gen_schemas.py`` generates one JSON Schema per
entry into ``schemas/fenolite.model.v0/``; ids stay ``v0`` until 1.0."""

from __future__ import annotations

SCHEMA_DIR = "schemas/fenolite.model.v0"

# layer file name -> (schema id, "module:Class")
LAYER_SCHEMAS: dict[str, tuple[str, str]] = {
    "meta.json": ("fenolite.meta.v0", "fenolite.model.design:DesignHeader"),
    "circuit.json": ("fenolite.circuit.v0", "fenolite.model.circuit:Circuit"),
    "board.json": ("fenolite.board.v0", "fenolite.model.board:Board"),
    "rules.json": ("fenolite.rules.v0", "fenolite.model.rules:RuleSet"),
    "manufacturing.json": ("fenolite.manufacturing.v0", "fenolite.model.manufacturing:Manifest"),
    "findings.json": ("fenolite.findings.v0", "fenolite.model.findings:Findings"),
}

# Library definitions are reference data, not a layer of a design: (file name, schema id, "module:Class").
LIBRARY_SCHEMA: tuple[str, str, str] = (
    "library.json",
    "fenolite.library.v0",
    "fenolite.model.library:Library",
)

__all__ = ["LAYER_SCHEMAS", "LIBRARY_SCHEMA", "SCHEMA_DIR"]
