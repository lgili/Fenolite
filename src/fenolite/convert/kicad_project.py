# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad project around a converted Altium board (capability design-conversion, "Altium to KiCad
direction" and "Report of the Altium to KiCad direction"; change c0161).

``derived_library`` gives the footprint library ``<project>.pretty``: one definition per footprint name,
from its first instance in reference order, taken back to the library's frame (a bottom instance is the
library footprint mirrored about local X with its layers flipped, ``docs/formats/kicad/board.md``, the row
of ``H-G-BOTTOM-STORE``); an instance that differs from its definition is ``changed``. ``generic_symbols``
gives each component a symbol with one pin per pin of the circuit, and ``schematic`` runs KiCad's
schematic generator (``schgen.generate_schematic``, layout ``readable``: one sheet per module) on them.
The symbols that the import's ``.SchLib`` files hold are not read: the first item of the design's cut
order. Nothing is written to disk.
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.backends.kicad import schgen, symembed
from fenolite.backends.kicad.layers import flip_layer
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.mod import write_footprint
from fenolite.backends.kicad.sch import write_schematic
from fenolite.backends.kicad.schlayout import natural_key
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import FULL_TURN
from fenolite.model.board import Graphic, Pad, Padstack
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef, SymbolGraphic, SymbolPin

PIN_PITCH = 2_540_000
PIN_LENGTH = 2_540_000
BODY_WIDTH = 10_160_000
HALF_TURN = 180_000_000
KEY_GRID = 10
"""Two instances of one name are one library footprint when their pads and drawings agree on a grid of
10 nm: the import places the items of each instance in its own frame, which rounds them by a nanometre or
two apart (``-06``: 475 000 and 475 001 nm)."""
REASON_EDITED = (
    "the instance differs from the library footprint of its name, its first instance in reference order"
)
REASON_SCHEMATIC = "the schematic is generated from the circuit, one sheet per module, with generic symbols"
REASON_SCHEMATIC_REFUSED = "the schematic generator refuses the circuit: no schematic is written"


def _unflip_point(point: Point) -> Point:
    return Point(point.x, -point.y)


def _unflip_angle(udeg: int) -> int:
    return (-udeg) % FULL_TURN


def _library_pad(pad: Pad, bottom: bool) -> Pad:
    """``pad`` as its library holds it: no net, and for a bottom instance mirrored about local X."""
    pad = dataclasses.replace(pad, net_id=None, native_ids={}, ext={}, provenance=None, zone_connection=None)
    if not bottom:
        return pad
    stack = pad.padstack
    if stack is not None:
        stack = dataclasses.replace(
            stack,
            layers=tuple(
                dataclasses.replace(e, layer=flip_layer(e.layer), offset=_unflip_point(e.offset))
                for e in stack.layers
            ),
            hole_rotation=_unflip_angle(stack.hole_rotation),
        )
    return dataclasses.replace(
        pad,
        position=_unflip_point(pad.position),
        rotation=_unflip_angle(pad.rotation),
        layers=tuple(flip_layer(name) for name in pad.layers),
        padstack=stack,
    )


def _library_graphic(graphic: Graphic, bottom: bool) -> Graphic:
    graphic = dataclasses.replace(graphic, native_ids={}, ext={}, provenance=None)
    if not bottom:
        return graphic
    return dataclasses.replace(
        graphic, layer=flip_layer(graphic.layer), points=tuple(_unflip_point(p) for p in graphic.points)
    )


def _period(pad: Pad) -> int:
    """The turn after which the copper of ``pad`` looks the same: none for a circle, a half turn for a
    rectangle, an oval and a rounded rectangle, a full turn otherwise."""
    if pad.shape == "circle":
        return 1
    return HALF_TURN if pad.shape in ("rect", "oval", "roundrect") else FULL_TURN


def _q(value: int) -> int:
    return round(value / KEY_GRID) * KEY_GRID


def _qp(point: Point) -> tuple[int, int]:
    return _q(point.x), _q(point.y)


def _shape(pad: Pad) -> str:
    stack: Padstack | None = pad.padstack
    held = None if stack is None else (stack.layers, stack.hole_shape, stack.hole_length, stack.hole_rotation)
    turn = pad.rotation % _period(pad)
    size = (_q(pad.size.w), _q(pad.size.h))
    drill = None if pad.drill is None else _q(pad.drill)
    return repr((pad.number, pad.kind, pad.shape, size, _qp(pad.position), turn, drill, sorted(pad.layers),
                 held, pad.corner_ratio))  # fmt: skip


def _graphic_shape(graphic: Graphic) -> str:
    points = graphic.points
    if graphic.kind == "circle" and len(points) == 2:
        centre, end = points
        radius = _q(math.isqrt((end.x - centre.x) ** 2 + (end.y - centre.y) ** 2))
        return repr((graphic.kind, graphic.layer, _qp(centre), radius, _q(graphic.width), graphic.filled))
    if graphic.kind in ("line", "rect", "arc") and points and points[-1] < points[0]:
        points = tuple(reversed(points))  # a line or an arc drawn the other way is the same drawing
    return repr((graphic.kind, graphic.layer, [_qp(p) for p in points], _q(graphic.width), graphic.filled))


def footprint_key(
    pads: tuple[Pad, ...], graphics: tuple[Graphic, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What two instances of one name must share to be one library footprint: their pads and drawings in
    the library's frame, in any order, each line or arc in either direction."""
    return tuple(sorted(_shape(p) for p in pads)), tuple(sorted(_graphic_shape(g) for g in graphics))


@dataclass(frozen=True)
class DerivedLibrary:
    """The definitions of ``<project>.pretty`` by name, and the instances that differ from theirs."""

    definitions: Mapping[str, FootprintDef]
    edited: tuple[str, ...]


def derived_library(design: Design, project: str) -> DerivedLibrary:
    """One definition per footprint name of the board (``lib_ref`` ``<project>:<name>``), from the first
    instance in reference order; the ids of the instances whose pads or drawings differ from it."""
    board = design.board
    if board is None:
        return DerivedLibrary({}, ())
    refs = {c.id: c.ref for c in design.circuit.components}
    ordered = sorted(board.footprints, key=lambda fp: (natural_key(refs.get(fp.component_id, "")), fp.id))
    definitions: dict[str, FootprintDef] = {}
    keys: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    edited: list[str] = []
    for fp in ordered:
        nickname, colon, name = fp.lib_ref.partition(":")
        if not colon or nickname != project or not name:
            continue
        bottom = fp.side == "bottom"
        pads = tuple(_library_pad(pad, bottom) for pad in fp.pads)
        graphics = tuple(_library_graphic(g, bottom) for g in fp.graphics)
        key = footprint_key(pads, graphics)
        if name in definitions:
            if key != keys[name]:
                edited.append(fp.id)
            continue
        keys[name] = key
        kind = (
            "through_hole" if any(p.kind == "thru_hole" for p in pads) else "smd" if pads else "unspecified"
        )
        definitions[name] = FootprintDef(
            id=derived_id("fpd", "fenolite", f"{project}:{name}"),
            name=name,
            library=project,
            kind=kind,  # type: ignore[arg-type]
            pads=tuple(
                dataclasses.replace(p, id=derived_id("pad", "fenolite", f"{project}:{name}:{i}"))
                for i, p in enumerate(pads)
            ),
            graphics=tuple(
                dataclasses.replace(g, id=derived_id("gfx", "fenolite", f"{project}:{name}:{i}"))
                for i, g in enumerate(graphics)
            ),
        )
    return DerivedLibrary(dict(sorted(definitions.items())), tuple(edited))


def library_files(
    library: DerivedLibrary, project: str, *, target: int, issues: list[Issue]
) -> tuple[dict[str, bytes], dict[str, str]]:
    """The files ``<project>.pretty/<name>.kicad_mod`` and ``fp-lib-table``, and the names whose
    definition the footprint writer refused, with the writer's message."""
    files: dict[str, bytes] = {}
    refused: dict[str, str] = {}
    for name, definition in library.definitions.items():
        try:
            text = write_footprint(definition, target=target, allow_lossy=True, issues=issues)
        except (ValueError, LookupError) as error:  # LossyWriteError is a FenoliteError, not caught here
            refused[name] = str(error)
            continue
        files[f"{project}.pretty/{name}.kicad_mod"] = text.encode("utf-8")
    row = LibRow(project, "KiCad", f"${{KIPRJMOD}}/{project}.pretty")
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", (row,)), target=target).encode("utf-8")
    return files, refused


# --- symbols and the schematic -----------------------------------------------------------------------


@dataclass(frozen=True)
class _Part:
    """A component with its generic symbol, as ``schgen.SchematicPart`` reads it."""

    component: Component
    path: str
    symbol: SymbolDef
    footprint: FootprintDef
    parents: tuple[SymbolDef, ...] = ()
    symbol_origin: str = "project"


_SYMBOL_NAME = re.compile(r"[^A-Za-z0-9_.+-]")


def _prefix(ref: str) -> str:
    letters = re.match(r"[A-Za-z_#]*", ref)
    return (letters.group(0) if letters else "") or "U"


def generic_symbol(component: Component, name: str, library: str) -> SymbolDef:
    """A box with the pins of ``component``: the first half, in natural order of their numbers, on the
    left, the rest on the right, 2.54 mm apart, each 2.54 mm long."""
    pins = sorted(component.pins, key=lambda p: natural_key(p.number))
    left = (len(pins) + 1) // 2
    rows = max(left, len(pins) - left, 1)
    half_h = (rows + 1) * PIN_PITCH // 2
    half_w = BODY_WIDTH // 2
    made: list[SymbolPin] = []
    for index, pin in enumerate(pins):
        on_left = index < left
        row = index if on_left else index - left
        y = half_h - PIN_PITCH * (row + 1)
        x = -(half_w + PIN_LENGTH) if on_left else half_w + PIN_LENGTH
        made.append(
            SymbolPin(
                number=pin.number,
                name=pin.name or pin.number,
                etype=pin.etype,
                position=Point(x, y),
                rotation=0 if on_left else 180_000_000,
                length=PIN_LENGTH,
                unit=1,
                body_style=1,
            )
        )
    box = SymbolGraphic("rect", (Point(-half_w, half_h), Point(half_w, -half_h)), width=254_000)
    return SymbolDef(
        id=derived_id("sym", "fenolite", f"{library}:{name}"),
        name=name,
        library=library,
        properties={"Reference": _prefix(component.ref), "Value": name},
        pins=tuple(made),
        graphics=(box,),
    )


def generic_symbols(design: Design, library: str) -> dict[str, SymbolDef]:
    """Each component's generic symbol by component id, named after the Altium symbol it links (its
    ``lib_symbol_ref`` after the colon) or its footprint; a name whose pins differ between components
    takes a suffix ``_2``, ``_3`` …"""
    by_pins: dict[str, list[tuple[tuple[str, ...], str]]] = {}
    found: dict[str, SymbolDef] = {}
    for component in sorted(design.circuit.components, key=lambda c: natural_key(c.ref)):
        if not component.pins:
            continue
        base = component.lib_symbol_ref.partition(":")[2] or component.lib_symbol_ref
        base = base or component.lib_footprint_ref.partition(":")[2] or "Part"
        base = _SYMBOL_NAME.sub("_", base)
        pins = tuple(sorted((p.number for p in component.pins), key=natural_key))
        known = by_pins.setdefault(base, [])
        name = next((n for p, n in known if p == pins), None)
        if name is None:
            name = base if not known else f"{base}_{len(known) + 1}"
            known.append((pins, name))
        symbol = generic_symbol(component, name, library)
        found[component.id] = symbol
    return found


@dataclass(frozen=True)
class Schematic:
    """The files of the generated schematic and its symbol library, the design written beside it (pads
    of open pins on the nets KiCad derives, components on the paths of their symbols), and the issues;
    ``files`` is empty when the generator refused."""

    files: Mapping[str, bytes]
    design: Design
    issues: tuple[Issue, ...]


def schematic(design: Design, project: str, *, target: int) -> Schematic:
    """The schematic of the circuit of ``design`` with generic symbols (``generic_symbols``)."""
    symbols = generic_symbols(design, project)
    empty = FootprintDef(id=derived_id("fpd", "fenolite", f"{project}:none"), name="none", library=project)
    parts: list[_Part] = []
    seen: set[str] = set()
    for component in design.circuit.components:
        if component.id not in symbols or not component.ref:
            continue  # a pad without a component has no symbol
        path = component.path or component.ref
        n = 2
        while path in seen:  # a reference that several components share: one symbol each
            path = f"{component.path or component.ref}_{n}"
            n += 1
        seen.add(path)
        parts.append(_Part(component, path, symbols[component.id], empty))
    generated = schgen.generate_schematic(design, parts, name=project, target=target, allow_lossy=True)
    issues = list(generated.issues)
    if any(found.severity == "error" for found in issues):
        return Schematic({}, design, tuple(issues))
    files: dict[str, bytes] = {}
    written = write_schematic(generated.sheet, target=target, allow_lossy=True)
    issues += written.issues
    files[f"{project}.kicad_sch"] = written.text.encode("utf-8")
    for path, child in generated.children.items():
        written = write_schematic(child, target=target, allow_lossy=True)
        issues += written.issues
        files[path] = written.text.encode("utf-8")
    rows: list[LibRow] = []
    for nickname, found in sorted(generated.libraries.items()):
        file = f"{nickname}.kicad_sym"
        files[file] = symembed.write_symbol_library(list(found), target=target).encode("utf-8")
        rows.append(LibRow(nickname, "KiCad", f"${{KIPRJMOD}}/{file}"))
    files["sym-lib-table"] = write_lib_table(LibTable("symbol", tuple(rows)), target=target).encode("utf-8")
    return Schematic(files, schgen.lower_for_schematic(design, generated), tuple(issues))


__all__ = [
    "DerivedLibrary",
    "REASON_EDITED",
    "REASON_SCHEMATIC",
    "REASON_SCHEMATIC_REFUSED",
    "Schematic",
    "derived_library",
    "generic_symbol",
    "generic_symbols",
    "library_files",
    "schematic",
]
