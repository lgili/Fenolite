# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed discovery of explicitly off-board purchasing symbols; never opaque graphics (c0334)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Component

if TYPE_CHECKING:
    from fenolite.importer.source import Source
    from fenolite.model.design import Design


def preserve(design: Design, root: Path) -> Design:
    """Attach source-only purchasing identities when a public comparison reads a native board."""
    from fenolite.backends.kicad.parity_inputs import read_sheets
    from fenolite.importer.source import Source

    if not root.is_file():
        return design
    source = Source(root.stem, "kicad", design, "", 10, (), hierarchy=read_sheets(root))
    return discover(source).design


def discover(source: Source) -> Source:
    """Add only resolved, pinless, non-power source items, preserving every hierarchy identity."""
    from fenolite.importer.emit.sheets import Hierarchy, instances

    components = list(source.design.circuit.components)
    physical: set[str] = (
        {footprint.component_id for footprint in source.design.board.footprints}
        if source.design.board
        else set()
    )
    hierarchy = Hierarchy(source)
    for instance in instances(source, include_root=True):
        sheet = source.hierarchy[instance.file]
        definitions = {definition.lib_id: definition for definition in sheet.lib_symbols}
        for symbol in sheet.symbols:
            ref = instance.refs.get(symbol.id)
            if ref is None or symbol.on_board or not symbol.in_bom:
                continue
            definition = definitions.get(symbol.lib_name or symbol.lib_ref)
            # Unresolved/inherited definitions remain strict drawing findings, never guessed pinless.
            if definition is None or definition.extends or definition.pins or definition.power:
                continue
            path = "/".join(hierarchy.paths.get(ref, (*instance.path, symbol.ref or ref)))
            current = next((component for component in components if component.ref == ref), None)
            if current is not None and (current.pins or current.id in physical):
                raise FormatError(
                    f"{ref}: off-board BOM-only symbol conflicts with physical or electrical component",
                    file=instance.file,
                )
            component = Component(
                id=derived_id("cmp", "kicad-bom-only", f"{symbol.id}:{path}"),
                ref=ref,
                path=path,
                value=symbol.value,
                dnp=symbol.dnp,
                lib_symbol_ref=symbol.lib_ref,
                lib_footprint_ref=symbol.footprint,
                properties={**symbol.properties, "fenolite.path": path},
                bom_only=True,
            )
            if current is None:
                components.append(component)
            else:
                components[components.index(current)] = replace(component, id=current.id)
    return replace(
        source,
        design=replace(source.design, circuit=replace(source.design.circuit, components=tuple(components))),
    )
