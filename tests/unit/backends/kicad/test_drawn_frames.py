# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored CC0 nested pages sharing one logical code module (c0327 replay compatibility)."""

from __future__ import annotations

from _drawn import library

from fenolite.backends.kicad import drawn
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.schematic import SchematicSheet, SheetRef, SymbolInstance


def ident(kind: str, name: str) -> str:
    return derived_id(kind, "authored-shared-module", name)


def reference(name: str) -> SheetRef:
    return SheetRef(
        id=ident("shr", name),
        name=name,
        file=name + ".kicad_sch",
        position=Point(10_000_000, 10_000_000),
        size=Size(10_000_000, 10_000_000),
    )


def test_equal_parent_child_module_frame_is_empty_relative() -> None:
    definition = library()["Mini:Mini_R"]

    def page(name: str, ref: str, refs: tuple[SheetRef, ...] = ()) -> SchematicSheet:
        symbol = SymbolInstance(
            id=ident("sci", ref),
            lib_ref=definition.lib_id,
            position=Point(50_800_000, 50_800_000),
            ref=ref,
            value="1k",
            properties={"Reference": ref, "Value": "1k", "Footprint": "Mini:R"},
        )
        return SchematicSheet(
            id=ident("sch", name), name=name, lib_symbols=(definition,), symbols=(symbol,), sheets=refs
        )

    root = SchematicSheet(id=ident("sch", "root"), name="root", sheets=(reference("parent"),))
    parent = page("parent", "R1", (reference("child"),))
    child = page("child", "R2")
    found = drawn.extract_with_pins(
        root,
        {"parent.kicad_sch": parent, "child.kicad_sch": child},
        components={"R1": "m/R1", "R2": "m/R2"},
        root_file="root.kicad_sch",
    )
    assert not found.issues
    parent_page = found.drawn.sheet("parent")
    assert parent_page is not None
    assert found.drawn.sheets[0].sheet_refs[0].module == "m"
    assert parent_page.sheet_refs[0].module == ""
    resolved = drawn._resolve_extracted(found)
    assert {path for path, pin in resolved.pins} == {"m/R1", "m/R2"}
    assert len(resolved.pins) == len(resolved.open) == 4
