# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium libraries as library definitions (capability altium-import, "Footprint libraries" and "Symbol
libraries"; change c0043).

``import_footprints`` maps a ``read.pcblib.PcbLibrary`` to ``FootprintDef``s and ``import_symbols`` a
``read.schlib.SchLibrary`` to ``SymbolDef``s. Ids follow "Identifiers of library definitions": a definition
has the native id ``<library>:<name>``, and what it holds is scoped to it.
"""

# evidence: see import_evidence

from __future__ import annotations

from fenolite.backends.altium.adapter.bodies import component_body
from fenolite.backends.altium.adapter.codes import Census
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.copper import definition_graphics
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import BACKEND, Ids, bag
from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.backends.altium.adapter.pads import pad
from fenolite.backends.altium.adapter.pins import pin_etype, pin_shape
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcblib import LibFootprint, PcbLibrary
from fenolite.backends.altium.read.pcbprims import BODY, PadRecord, RawPrimitive, TextRecord
from fenolite.backends.altium.read.sch import (
    Component,
    Designator,
    Implementation,
    ImplementationList,
    ImplementationParameters,
    MapDefiner,
    MapDefinerList,
    Parameter,
    Pin,
)
from fenolite.backends.altium.read.schlib import SchLibComponent, SchLibrary
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.board import ComponentBody, Pad
from fenolite.model.library import FootprintDef, FootprintKind, Library, SymbolDef, SymbolPin, SymbolUnit

FOOTPRINT_KIND = "altium_pcblib"
SYMBOL_KIND = "altium_schlib"
FOOTPRINT_MODEL = "PCBLIB"
QUARTER = 90_000_000


def _native(library: str, name: str) -> str:
    return f"{library}:{name}" if library else name


def _footprint(
    footprint: LibFootprint, library: str, *, file: str, sha256: str, census: Census, issues: list[Issue]
) -> FootprintDef:
    native = _native(library, footprint.name)
    layers = LayerMap.two_layer()
    ctx = Context(ids=Ids(native, EVIDENCE), layers=layers, file=file, sha256=sha256, census=census)
    layers.issues = ctx.issues
    storage = footprint.storage
    pads: list[Pad] = []
    bodies: list[ComponentBody] = []
    for index, item in enumerate(footprint.primitives):
        locator = f"{storage}/Data#{index}"
        if isinstance(item, PadRecord):
            unique = footprint.unique_ids.get(index)
            pads.append(
                pad(
                    item,
                    ctx,
                    locator=locator,
                    native=f"{native}:{unique}" if unique else None,
                    frame=None,
                    definition=True,
                )  # fmt: skip
            )
            census.map("pads")
        elif isinstance(item, TextRecord):
            census.skip("texts", "texts")
        elif isinstance(item, RawPrimitive):
            if item.type != BODY:
                census.skip("raw", "raw-primitives")
                continue
            for record in read_bodies(item.raw, storage=storage, issues=ctx.issues):
                body = (
                    component_body(record, None, ctx, locator=locator, section="bdy")
                    if record.framed
                    else None
                )
                if body is None:
                    census.skip("bodies", "bodies")
                else:
                    bodies.append(body)
                    census.map("bodies")
    graphics = definition_graphics(footprint.primitives, ctx, storage)
    kind: FootprintKind = "unspecified"
    if any(p.drill is not None for p in pads):
        kind = "through_hole"
    elif pads:
        kind = "smd"
    description = footprint.description or ""
    properties: dict[str, str] = {}
    if description:
        properties["Description"] = description
    height = footprint.parameters.get("HEIGHT")
    if height:
        properties["Height"] = height
    issues.extend(ctx.issues)
    return FootprintDef(
        id=derived_id("fpd", BACKEND, native),
        native_ids={BACKEND: native},
        provenance=ctx.provenance(f"{storage}/Data"),
        name=footprint.name,
        library=library,
        description=description,
        kind=kind,
        properties=properties,
        pads=tuple(pads),
        graphics=tuple(graphics),
        bodies=tuple(bodies),
    )


def import_footprints(
    library: PcbLibrary, *, name: str, file: str, sha256: str, issues: list[Issue] | None = None
) -> Library:
    """A PCB library as a ``Library`` named ``name`` with one ``FootprintDef`` per footprint, in library
    order. A pad on Multi-Layer has the layers ``("*.Cu",)``; tracks, arcs, fills and regions are graphics;
    texts are counted as unmapped."""
    census = Census()
    found: list[Issue] = []
    footprints: list[FootprintDef] = []
    seen: set[str] = set()
    for footprint in library.footprints:
        if footprint.name in seen:
            census.skip("footprints", "footprints")
            continue
        seen.add(footprint.name)
        footprints.append(_footprint(footprint, name, file=file, sha256=sha256, census=census, issues=found))
    found.extend(census.issues(file))
    if issues is not None:
        issues.extend(found)
    return Library(name=name, footprints=tuple(footprints))


_SYMBOL_RECORDS = (
    Component,
    Pin,
    Designator,
    Parameter,
    Implementation,
    ImplementationList,
    ImplementationParameters,
    MapDefiner,
    MapDefinerList,
)


def _symbol(
    component: SchLibComponent, library: str, *, ids: Ids, file: str, sha256: str, census: Census
) -> SymbolDef:
    native = _native(library, component.name)
    pins: list[SymbolPin] = []
    symbols: list[str] = []
    for pin in component.pins:
        etype, _pairs = pin_etype(pin)
        shape, other = pin_shape(pin)
        x, y = pin.hot_end
        if other:
            symbols.append(f"{pin.designator}={other}")
        pins.append(
            SymbolPin(
                number=pin.designator,
                name=pin.name,
                etype=etype,
                position=Point(x.nm(), y.nm()),
                shape=shape,
                rotation=(pin.direction * QUARTER + 2 * QUARTER) % (4 * QUARTER),
                length=pin.length.nm(),
                unit=max(pin.owner_part, 0),
                body_style=pin.owner_display_mode + 1,
                hidden=pin.hidden,
            )
        )
    properties: dict[str, str] = {}
    designator = next((r.text for r in component.of_type(Designator)), "")
    if designator:
        properties["Reference"] = designator
    for parameter in component.of_type(Parameter):
        key = "Value" if parameter.name == "Comment" else parameter.name
        if key and key not in properties:
            properties[key] = parameter.text
    head = component.component
    description = component.description or (head.description if head is not None else "")
    if description:
        properties["Description"] = description
    for model in component.of_type(Implementation):
        if model.model_type.upper() == FOOTPRINT_MODEL and (
            model.is_current or "Footprint" not in properties
        ):
            properties["Footprint"] = model.model_name
    graphics = sum(1 for record in component.records if not isinstance(record, _SYMBOL_RECORDS))
    census.skip("symbol-records", "symbol-graphics", graphics)
    units = tuple(SymbolUnit(part, mode + 1) for part in component.parts for mode in component.modes)
    return SymbolDef(
        id=derived_id("sym", BACKEND, native),
        native_ids={BACKEND: native},
        provenance=ids.provenance(file, sha256, f"{component.storage_name}/Data#0"),
        ext=bag([("pin_symbols", ";".join(symbols))] if symbols else []),
        name=component.name,
        library=library,
        properties=properties,
        units=units,
        pins=tuple(pins),
    )


def import_symbols(
    library: SchLibrary, *, name: str, file: str, sha256: str, issues: list[Issue] | None = None
) -> Library:
    """A schematic library as a ``Library`` named ``name`` with one ``SymbolDef`` per component. A pin's
    position is its electrical end, kept without a flip; its rotation is the direction from that end
    towards the body; body graphics are counted as unmapped."""
    census = Census()
    ids = Ids(SYMBOL_KIND, EVIDENCE)
    symbols: list[SymbolDef] = []
    seen: set[str] = set()
    for component in library.components:
        if component.name in seen:
            census.skip("symbols", "symbols")
            continue
        seen.add(component.name)
        symbols.append(_symbol(component, name, ids=ids, file=file, sha256=sha256, census=census))
    if issues is not None:
        issues.extend(census.issues(file))
    return Library(name=name, symbols=tuple(symbols))


__all__ = ["FOOTPRINT_KIND", "SYMBOL_KIND", "import_footprints", "import_symbols"]
