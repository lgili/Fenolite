# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Current model schema ids; earlier major directories remain immutable snapshots."""

from __future__ import annotations

from fenolite.model.design import SCHEMA_VERSION, parse_version

_MAJOR = parse_version(SCHEMA_VERSION)[0]
SCHEMA_DIR = f"schemas/fenolite.model.v{_MAJOR}"

# layer file name -> (schema id, "module:Class")
LAYER_SCHEMAS: dict[str, tuple[str, str]] = {
    "meta.json": (f"fenolite.meta.v{_MAJOR}", "fenolite.model.design:DesignHeader"),
    "circuit.json": (f"fenolite.circuit.v{_MAJOR}", "fenolite.model.circuit:Circuit"),
    "board.json": (f"fenolite.board.v{_MAJOR}", "fenolite.model.board:Board"),
    "rules.json": (f"fenolite.rules.v{_MAJOR}", "fenolite.model.rules:RuleSet"),
    "manufacturing.json": (f"fenolite.manufacturing.v{_MAJOR}", "fenolite.model.manufacturing:Manifest"),
    "findings.json": (f"fenolite.findings.v{_MAJOR}", "fenolite.model.findings:Findings"),
}

# Library definitions are reference data, not a layer of a design: (file name, schema id, "module:Class").
LIBRARY_SCHEMA: tuple[str, str, str] = (
    "library.json",
    f"fenolite.library.v{_MAJOR}",
    "fenolite.model.library:Library",
)

# Drawing sheets are definitions outside a design, like library definitions (change c0012).
SHEET_SCHEMA: tuple[str, str, str] = (
    "drawing_sheet.json",
    f"fenolite.drawing_sheet.v{_MAJOR}",
    "fenolite.model.presentation:DrawingSheet",
)

# Schematic sheets are definitions outside a design too (change c0060).
SCHEMATIC_SCHEMA: tuple[str, str, str] = (
    "schematic.json",
    f"fenolite.schematic.v{_MAJOR}",
    "fenolite.model.schematic:SchematicSheet",
)

# Panels are definitions outside a design too: copies of one built board (change c0173).
PANEL_SCHEMA: tuple[str, str, str] = (
    "panel.json",
    f"fenolite.panel_model.v{_MAJOR}",
    "fenolite.model.panel:Panel",
)

__all__ = [
    "LAYER_SCHEMAS",
    "LIBRARY_SCHEMA",
    "PANEL_SCHEMA",
    "SCHEMATIC_SCHEMA",
    "SCHEMA_DIR",
    "SHEET_SCHEMA",
]
