# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source symbols kept in both directions (change c0470, tasks 3.1 and 3.2; design D2)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _altium_sch_build import SHEET, ascii_doc
from _drawings import BLINK, HIER, altium_sheets

from fenolite.backends.altium import drawn_read, drawn_symbols
from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.read import sch
from fenolite.backends.kicad import sym
from fenolite.backends.kicad.schlayout import pin_point
from fenolite.core.coords import Point
from fenolite.model.library import SymbolDef

DEG = 1_000_000
Symbols = dict[tuple[str, int], tuple[SymbolDef, Counter[str]]]


def _symbols(sheets: list[SheetInput]) -> tuple[drawn_read.Extracted, Symbols]:
    found = drawn_read.extract_with_pins(sheets)
    out: Symbols = {}
    for sheet, drawn in zip(sheets, found.drawn.sheets[-len(sheets) :], strict=True):
        components = [
            r for r in sheet.document.all_records() if isinstance(r, sch.Component) and r.owner is None
        ]
        for number, component in enumerate(components):
            out[(drawn.key, number)] = drawn_symbols.component_symbol(
                sheet.document, component, name=f"S{number}", library="lib"
            )
    return found, out


def _check_pins(found: drawn_read.Extracted, symbols: Symbols) -> int:
    """Each symbol's pins, posed as the drawn symbol is, lie on the pin points of the source sheet."""
    checked = 0
    for sheet in found.drawn.sheets:
        for number, placed in enumerate(sheet.symbols):
            definition, _ = symbols[(sheet.key, number)]
            posed = sorted(
                (pin.number, pin_point(placed.at, pin.position, placed.rotation // DEG, placed.mirror))
                for pin in definition.pins if pin.unit == placed.unit
            )  # fmt: skip
            source = sorted((p.number, p.at) for p in found.pins[(sheet.key, "symbol", number)])
            assert posed == source, (sheet.key, placed.part)
            checked += len(posed)
    return checked


@pytest.mark.parametrize("project", [BLINK, HIER], ids=["blink", "hier"])
def test_to_kicad_pins_land_on_the_source_points(project: Path) -> None:
    """Task 3.1: the symbol of each placed part, posed by its drawn symbol, puts every pin on its sheet."""
    found, symbols = _symbols(altium_sheets(project))
    assert _check_pins(found, symbols) > 0
    for definition, _ in symbols.values():
        assert definition.graphics, definition.name


def _component(
    ref: str, x: int, y: int, index: int, *, orientation: int = 0, mirrored: bool = False
) -> list[str]:
    mirror = "|ISMIRRORED=T" if mirrored else ""
    return [
        f"|RECORD=1|LIBREFERENCE=AUTHORED|CURRENTPARTID=2|PARTCOUNT=3|DISPLAYMODECOUNT=2|LOCATION.X={x}"
        f"|LOCATION.Y={y}|ORIENTATION={orientation}{mirror}",
        f"|RECORD=34|OWNERINDEX={index}|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y + 30}|TEXT={ref}"
        "|NAME=Designator",
        # part 1: one pin pointing left, a rectangle and an arc; part 2: one pin pointing down
        f"|RECORD=2|OWNERINDEX={index}|OWNERPARTID=1|LOCATION.X={x}|LOCATION.Y={y + 10}|PINLENGTH=20"
        "|PINCONGLOMERATE=34|DESIGNATOR=1|NAME=A|ELECTRICAL=0",
        f"|RECORD=14|OWNERINDEX={index}|OWNERPARTID=1|LOCATION.X={x}|LOCATION.Y={y}|CORNER.X={x + 40}"
        f"|CORNER.Y={y + 20}|ISSOLID=T|LINEWIDTH=1",
        f"|RECORD=12|OWNERINDEX={index}|OWNERPARTID=1|LOCATION.X={x + 20}|LOCATION.Y={y + 10}|RADIUS=5"
        "|STARTANGLE=0|ENDANGLE=180",
        f"|RECORD=2|OWNERINDEX={index}|OWNERPARTID=2|LOCATION.X={x + 20}|LOCATION.Y={y}|PINLENGTH=10"
        "|PINCONGLOMERATE=35|DESIGNATOR=2|NAME=B|ELECTRICAL=0",
        f"|RECORD=13|OWNERINDEX={index}|OWNERPARTID=2|LOCATION.X={x}|LOCATION.Y={y}|CORNER.X={x + 40}"
        f"|CORNER.Y={y}",
        # display mode 1 of part 2: not shown, counted
        f"|RECORD=13|OWNERINDEX={index}|OWNERPARTID=2|OWNERPARTDISPLAYMODE=1|LOCATION.X={x}|LOCATION.Y={y}"
        f"|CORNER.X={x}|CORNER.Y={y + 40}",
        f"|RECORD=4|OWNERINDEX={index}|OWNERPARTID=1|LOCATION.X={x}|LOCATION.Y={y}|TEXT=body",
    ]


@pytest.mark.parametrize(("orientation", "mirrored"), [(o, m) for o in range(4) for m in (False, True)])
def test_to_kicad_multi_part_symbol_in_every_pose(orientation: int, mirrored: bool) -> None:
    """Task 3.1: parts become units, the shown display mode body style 1; every pose puts the pins back."""
    data = ascii_doc([SHEET, *_component("U1", 300, 300, 1, orientation=orientation, mirrored=mirrored)])
    sheets = [SheetInput("authored.SchDoc", "", sch.read_schematic(data, file="authored.SchDoc"))]
    found, symbols = _symbols(sheets)
    definition, changed = symbols[("authored", 0)]
    assert [(u.unit, u.body_style) for u in definition.units] == [(1, 1), (2, 1)]
    assert {(p.number, p.unit) for p in definition.pins} == {("1", 1), ("2", 2)}
    assert sorted((g.kind, g.unit) for g in definition.graphics) == [("line", 1), ("line", 2), ("rect", 1)]
    assert dict(changed) == {
        drawn_symbols.CHANGED_ARC: 1, drawn_symbols.CHANGED_MODE: 1, drawn_symbols.CHANGED_TEXT: 1,
    }  # fmt: skip
    assert found.drawn.sheets[0].symbols[0].unit == 2
    assert _check_pins(found, symbols) == 1
    rect = next(g for g in definition.graphics if g.kind == "rect")
    assert rect.filled and rect.width == 254_000
    if orientation == 0 and not mirrored:
        assert rect.points == (Point(0, 0), Point(40 * 254_000, 20 * 254_000))
        pin = next(p for p in definition.pins if p.number == "1")
        assert (pin.position, pin.rotation) == (Point(-20 * 254_000, 10 * 254_000), 0)


def test_to_kicad_symbol_library_reads_back() -> None:
    """Task 3.1: the symbols write as a KiCad library and read back with the same pins and shapes."""
    _, symbols = _symbols(altium_sheets(BLINK))
    definitions = tuple(definition for definition, _ in symbols.values())
    text = sym.write_symbol_library(definitions, target=10)
    back = sym.read_symbol_library(text, library="lib")
    for written, read in zip(definitions, back, strict=True):
        assert {(p.number, p.position, p.rotation) for p in read.pins} == {
            (p.number, p.position, p.rotation) for p in written.pins
        }
        assert len(read.graphics) == len(written.graphics)


def test_to_altium_draws_each_symbol_from_its_graphics(tmp_path: Path) -> None:
    """Task 3.2: a KiCad source with sheets converts with ``--altium-symbols graphics``: each SchLib symbol
    draws the shapes of its KiCad definition, and no symbol is simplified to a generic rectangle."""
    from _schbuild import built_nested, write_files

    from fenolite.backends.altium.read.schlib import read_schlib
    from fenolite.backends.kicad import parity_inputs
    from fenolite.convert import convert_project

    write_files(built_nested(), tmp_path)
    conversion = convert_project(tmp_path / "nested.kicad_pro", to="altium", allow_lossy=True)
    assert [i.code for i in conversion.issues if i.code == "altium.symbol-simplified"] == []
    sheets = parity_inputs.read_sheets(tmp_path / "nested.kicad_sch")
    shapes = {
        definition.name: sorted(g.kind for g in definition.graphics)
        for sheet in sheets.values()
        for definition in sheet.lib_symbols
    }
    kinds = {"Rectangle": "rect", "Polyline": "line", "Line": "line", "Polygon": "polygon"}
    kinds["Ellipse"] = "circle"
    (library,) = [read_schlib(data) for name, data in conversion.files.items() if name.endswith(".SchLib")]
    assert library.components
    for component in library.components:
        drawn = sorted(kinds[type(r).__name__] for r in component.records if type(r).__name__ in kinds)
        assert drawn in shapes.values(), component.name
