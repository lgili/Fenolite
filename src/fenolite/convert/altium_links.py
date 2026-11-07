# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The library links of an Altium board's components through a KiCad project and back (capability
design-conversion, "Altium round trip keeps texts, values and library links"; change c0451).

The KiCad project of an Altium conversion holds one derived footprint library and one generated symbol per
component, so the source's links have no place in KiCad's own. ``carry`` writes them as two hidden
footprint properties, each held by a hidden field on the footprint's fabrication layer; ``restore`` gives
them back in a conversion to Altium and drops the two properties. A footprint link comes back only while
the KiCad footprint is still the one the conversion derived from the source pattern: its link item is
``library_name(pattern)``, perhaps with a variant suffix ``_<n>`` (change c0425).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.libnames import library_name
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design

FOOTPRINT = "Altium Footprint"
"""The KiCad footprint property that holds the source's footprint link, ``<library>:<pattern>``."""
SYMBOL = "Altium Symbol"
"""The KiCad footprint property that holds the source's symbol link, ``<library>:<symbol>``."""
NAMES = (FOOTPRINT, SYMBOL)
FIELD_SIZE = 1_000_000
FIELD_STROKE = 150_000


def _field(fp: FootprintInstance, name: str) -> FootprintField:
    bottom = fp.side == "bottom"
    return FootprintField(
        id=derived_id("fld", "c0451", f"{fp.id}:{name}"),
        name=name,
        position=Point(0, 0),
        layer="B.Fab" if bottom else "F.Fab",
        size=Size(FIELD_SIZE, FIELD_SIZE),
        thickness=FIELD_STROKE,
        visible=False,
        mirrored=bottom,
    )


def carry(design: Design, footprint_links: Mapping[str, str]) -> Design:
    """``design`` (the KiCad design of an Altium conversion) whose components with a reference hold the
    source's links as the properties ``FOOTPRINT`` (from ``footprint_links``, component id → the source's
    footprint link) and ``SYMBOL`` (the component's own symbol link), each placed by a hidden field of its
    footprint. An empty link gives no property."""
    board = design.board
    if board is None:
        return design
    held: dict[str, dict[str, str]] = {}
    components: list[Component] = []
    for component in design.circuit.components:
        found = {FOOTPRINT: footprint_links.get(component.id, ""), SYMBOL: component.lib_symbol_ref}
        found = {name: value for name, value in found.items() if value}
        if not component.ref or not found:
            components.append(component)
            continue
        held[component.id] = found
        components.append(dataclasses.replace(component, properties={**component.properties, **found}))
    footprints = tuple(
        dataclasses.replace(fp, fields=(*fp.fields, *(_field(fp, name) for name in held[fp.component_id])))
        if fp.component_id in held and not any(f.name in NAMES for f in fp.fields)
        else fp
        for fp in board.footprints
    )
    return dataclasses.replace(
        design,
        board=dataclasses.replace(board, footprints=footprints),
        circuit=dataclasses.replace(design.circuit, components=tuple(components)),
    )


def derived_from(link: str, source: str) -> bool:
    """Whether the KiCad footprint link ``link`` names the footprint the conversion derived from the source
    link ``source``: its item is the source pattern after ``library_name``, perhaps with ``_<n>``."""
    item = link.rpartition(":")[2]
    derived = library_name(source.rpartition(":")[2], allow_space=True)
    return item == derived or re.fullmatch(re.escape(derived) + r"_\d+", item) is not None


def _suffixed(link: str, suffix: str) -> str:
    """``link`` whose library part ends with ``suffix`` (in any letter case): the form of an Altium link,
    which the Altium writer files under that library (``project.pcblib_name``, ``schlib_name``); the
    import reads it back without the suffix. An empty link or library stays as it is."""
    library, colon, item = link.rpartition(":")
    if not colon or not library or library.lower().endswith(suffix.lower()):
        return link
    return f"{library}{suffix}:{item}"


def held(design: Design) -> dict[str, tuple[str, str]]:
    """Component id → ``(footprint link, symbol link)`` that ``carry`` wrote and that come back: the
    component holds ``FOOTPRINT`` and its first footprint is still ``derived_from`` it."""
    board = design.board
    if board is None:
        return {}
    first = {fp.component_id: fp for fp in reversed(board.footprints)}
    found: dict[str, tuple[str, str]] = {}
    for component in design.circuit.components:
        footprint = component.properties.get(FOOTPRINT, "")
        fp = first.get(component.id)
        if footprint and fp is not None and derived_from(fp.lib_ref, footprint):
            found[component.id] = (
                _suffixed(footprint, ".PcbLib"),
                _suffixed(component.properties.get(SYMBOL, ""), ".SchLib"),
            )
    return found


def restore(design: Design) -> Design:
    """``design`` (read from a KiCad project) with the links that ``carry`` wrote given back (``held``): the
    footprint link to the component and its footprints, the symbol link to the component; the two
    properties and their fields are dropped either way."""
    board = design.board
    if board is None or not any(name in c.properties for c in design.circuit.components for name in NAMES):
        return design
    restored = held(design)
    components: list[Component] = []
    for component in design.circuit.components:
        properties = {k: v for k, v in component.properties.items() if k not in NAMES}
        if component.id in restored:
            footprint, symbol = restored[component.id]
            component = dataclasses.replace(
                component, lib_footprint_ref=footprint, lib_symbol_ref=symbol or component.lib_symbol_ref
            )
        if properties != component.properties:
            component = dataclasses.replace(component, properties=properties)
        components.append(component)
    footprints = tuple(
        dataclasses.replace(
            fp,
            lib_ref=restored[fp.component_id][0] if fp.component_id in restored else fp.lib_ref,
            fields=tuple(f for f in fp.fields if f.name not in NAMES),
        )
        for fp in board.footprints
    )
    return dataclasses.replace(
        design,
        board=dataclasses.replace(board, footprints=footprints),
        circuit=dataclasses.replace(design.circuit, components=tuple(components)),
    )


def symbol_links(design: Design) -> dict[str, str]:
    """Reference → the symbol link ``held`` gives back, for the schematic of a conversion to Altium."""
    refs = {c.id: c.ref for c in design.circuit.components}
    return {refs[ident]: symbol for ident, (_, symbol) in held(design).items() if symbol and refs.get(ident)}


__all__ = ["FOOTPRINT", "NAMES", "SYMBOL", "carry", "derived_from", "held", "restore", "symbol_links"]
