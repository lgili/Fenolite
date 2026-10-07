# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbol graphics in libraries and bodies (capability altium-schematic-writer, "Symbol graphics in
libraries and bodies"; change c0086).

A symbol is mapped, written into a schematic library and onto a sheet, and read back with the product
reader ``fenolite.backends.altium.read``: the records it finds must be the model's graphics. Evidence of
level INFERRED (``H-A-SCHX-READBACK``): Fenolite's writer read by Fenolite's reader.
"""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.altium.altsym import (
    DEFAULT_BODIES,
    GRAPHIC_KINDS,
    AltiumGraphic,
    AltiumSymbol,
    from_symbol_def,
    map_graphic,
    unit_and_frac,
)
from fenolite.backends.altium.binary import write_schdoc_binary
from fenolite.backends.altium.layout import PartSpec, layout_sheet
from fenolite.backends.altium.read.sch import Ellipse, Line, Polygon, Rectangle, read_schematic
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.altium.schdoc import GRAPHIC_RECORDS, graphic_fields, schdoc_records
from fenolite.backends.altium.schlib import write_schlib
from fenolite.catalog import get_symbol, list_entries
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolUnit

MIL = 25_400
Shape = tuple[str, tuple[tuple[int, int], ...], bool]


def mapped(symbol: SymbolDef, issues: list[Issue] | None = None, **kwargs: object) -> AltiumSymbol:
    """``symbol`` mapped with ``bodies="graphics"`` unless ``kwargs`` says otherwise."""
    options = {"bodies": "graphics", **kwargs}
    return from_symbol_def(symbol, lib_ref=symbol.name, footprint=None, issues=issues, **options)  # type: ignore[arg-type]


def same(found: list[Shape], expected: list[Shape]) -> bool:
    """Equal kinds, fills and points, each coordinate within 1 nm: a ``_FRAC`` step is 2.54 nm, so a
    coordinate that is no multiple of 127 nm reads back rounded."""
    if [(kind, len(points), filled) for kind, points, filled in found] != [
        (kind, len(points), filled) for kind, points, filled in expected
    ]:
        return False
    return all(
        abs(a - b) <= 1
        for (_, mine, _), (_, theirs, _) in zip(found, expected, strict=True)
        for p, q in zip(mine, theirs, strict=True)
        for a, b in zip(p, q, strict=True)
    )


def test_graphics_are_the_default_and_generic_keeps_the_rectangles() -> None:
    """``graphics`` is the default (decision of the maintainer, 2026-10-06); ``generic`` keeps the
    rectangles and the info of change c0034, the form his earlier author reports covered."""
    symbol = get_symbol("Fenolite:Resistor")
    assert DEFAULT_BODIES == "graphics"
    assert from_symbol_def(symbol, lib_ref="Resistor", footprint=None).drawn
    issues: list[Issue] = []
    plain = from_symbol_def(symbol, lib_ref="Resistor", footprint=None, issues=issues, bodies="generic")
    assert not plain.drawn and plain.graphics == ()
    assert [i.message for i in issues] == ["Fenolite:Resistor: its graphics became one rectangle per part"]
    with pytest.raises(ValueError, match="unknown symbol bodies"):
        from_symbol_def(symbol, lib_ref="Resistor", footprint=None, bodies="lines")  # type: ignore[arg-type]


def model_shapes(symbol: SymbolDef) -> list[Shape]:
    """The graphics of a model symbol as (record kind, points in nm, filled), a circle as its centre and a
    point one radius to its right."""
    found: list[Shape] = []
    for graphic in symbol.graphics:
        points = tuple((p.x, p.y) for p in graphic.points)
        if graphic.kind == "rect":
            (ax, ay), (bx, by) = points
            found.append(
                ("rectangle", ((min(ax, bx), min(ay, by)), (max(ax, bx), max(ay, by))), graphic.filled)
            )
        elif graphic.kind == "circle":
            found.append(("ellipse", points, graphic.filled))
        else:
            found.append((graphic.kind, points, graphic.filled and graphic.kind == "polygon"))
    return found


def read_shapes(records: tuple[object, ...]) -> list[Shape]:
    """The graphic records a reader found, in the form of ``model_shapes``."""
    found: list[Shape] = []
    for record in records:
        if isinstance(record, Line):
            ends = (record.location, record.corner)
            found.append(("line", tuple((x.nm(), y.nm()) for x, y in ends), False))
        elif isinstance(record, Rectangle):
            ends = (record.location, record.corner)
            found.append(("rectangle", tuple((x.nm(), y.nm()) for x, y in ends), record.solid))
        elif isinstance(record, Polygon):
            found.append(("polygon", tuple((x.nm(), y.nm()) for x, y in record.points), record.solid))
        elif isinstance(record, Ellipse):
            x, y = record.location[0].nm(), record.location[1].nm()
            assert record.radius == record.secondary_radius
            found.append(("ellipse", ((x, y), (x + record.radius.nm(), y)), record.solid))
    return found


def library_shapes(symbol: AltiumSymbol) -> list[Shape]:
    library = read_schlib(write_schlib([symbol], library="t.SchLib"), file="t.SchLib")
    return read_shapes(library.get(symbol.lib_ref).records)


def test_graphic_kinds_are_the_model_kinds() -> None:
    assert GRAPHIC_KINDS == ("circle", "line", "polygon", "rect")
    assert sorted(GRAPHIC_RECORDS) == ["ellipse", "line", "polygon", "rectangle"]


@pytest.mark.parametrize(
    ("nm", "unit", "frac"),
    [(0, 0, 0), (254_000, 1, 0), (381_000, 1, 50_000), (-381_000, -1, -50_000), (-127_000, 0, -50_000)],
)
def test_unit_and_frac_keep_their_own_signs(nm: int, unit: int, frac: int) -> None:
    assert unit_and_frac(nm) == (unit, frac) and unit * 100_000 + frac == nm * 50 // 127


def test_resistor_symbol() -> None:
    """Scenario "Resistor symbol": the catalog resistor is eight lines; the library holds eight line
    records with its coordinates, two pins and no rectangle."""
    symbol = get_symbol("Fenolite:Resistor")
    issues: list[Issue] = []
    resistor = mapped(symbol, issues)
    assert resistor.drawn and len(resistor.graphics) == 8 and not issues
    library = read_schlib(write_schlib([resistor], library="t.SchLib"), file="t.SchLib")
    component = library.get("Resistor")
    assert len(component.pins) == 2
    assert not [r for r in component.records if isinstance(r, Rectangle)]
    assert len([r for r in component.records if isinstance(r, Line)]) == 8
    assert library_shapes(resistor) == model_shapes(symbol)


def test_rectangle_symbol_keeps_its_size() -> None:
    symbol = get_symbol("Fenolite:Linear_Regulator")
    regulator = mapped(symbol)
    (shape,) = library_shapes(regulator)
    # 600 mil square since change c0134: room for IN, OUT and GND at the size Altium draws them
    assert shape == ("rectangle", ((-300 * MIL, -300 * MIL), (300 * MIL, 300 * MIL)), True)
    assert regulator.rectangle(1) == dataclasses.replace(
        regulator.rectangle(1), x0=-300, y0=-300, x1=300, y1=300
    )


def test_every_catalog_symbol_reads_back() -> None:
    """The four graphic kinds, filled and not, off the 10-mil grid: every catalog symbol is drawn from its
    graphics and reads back to them, within the 2.54 nm step of a ``_FRAC`` key."""
    kinds: set[str] = set()
    off_grid: list[str] = []
    for entry in list_entries(kind="symbol"):
        symbol = get_symbol(entry.lib_id)
        issues: list[Issue] = []
        try:
            written = mapped(symbol, issues)
        except ValueError:  # a pin off the 10-mil grid, which the build reports (altium.symbol-off-grid)
            off_grid.append(entry.lib_id)
            continue
        assert written.drawn, entry.lib_id
        assert not [i for i in issues if i.code == "altium.symbol-simplified"], entry.lib_id
        assert same(library_shapes(written), model_shapes(symbol)), entry.lib_id
        kinds |= {graphic.kind for graphic in symbol.graphics}
    assert kinds == set(GRAPHIC_KINDS)
    assert off_grid == ["Fenolite:Potentiometer", "Fenolite:Terminal_1Pin"]


def test_pins_stay_as_written_and_touch_the_box() -> None:
    symbol = get_symbol("Fenolite:Comparator")
    drawn = mapped(symbol)
    plain = mapped(dataclasses.replace(symbol, graphics=()))
    assert drawn.pins == plain.pins
    box = drawn.rectangle(1)
    assert all(box.x0 <= pin.x <= box.x1 and box.y0 <= pin.y <= box.y1 for pin in drawn.pins)


def _simplified(symbol: SymbolDef, **kwargs: object) -> tuple[AltiumSymbol, Issue]:
    issues: list[Issue] = []
    written = mapped(symbol, issues, **kwargs)
    (found,) = [i for i in issues if i.code == "altium.symbol-simplified"]
    assert found.severity == "info" and symbol.lib_id in found.message
    return written, found


def test_symbol_with_a_graphic_the_writer_lacks() -> None:
    """Scenario "Symbol with a curve the writer lacks": a kind outside ``GRAPHIC_KINDS``, in the model or
    named by the caller, keeps the synthesised rectangle and is reported once."""
    symbol = get_symbol("Fenolite:Capacitor")
    curve = SymbolGraphic("bezier", (Point(0, 0), Point(MIL, MIL)))  # type: ignore[arg-type]
    for variant, kwargs in (
        (dataclasses.replace(symbol, graphics=(*symbol.graphics, curve)), {}),
        (symbol, {"unmodelled": ("arc",)}),
    ):
        written, found = _simplified(variant, **kwargs)
        assert not written.drawn and "have no record" in found.message
        assert library_shapes(written) == [
            ("rectangle", ((-100 * MIL, -100 * MIL), (100 * MIL, 100 * MIL)), True)
        ]
    with pytest.raises(ValueError, match="bezier"):
        map_graphic(curve)


def test_symbol_without_graphics_and_symbol_of_two_units() -> None:
    symbol = get_symbol("Fenolite:Capacitor")
    bare, found = _simplified(dataclasses.replace(symbol, graphics=()))
    assert not bare.drawn and "holds no graphics" in found.message
    two = dataclasses.replace(symbol, units=(SymbolUnit(1, 1), SymbolUnit(2, 1)))
    dual, found = _simplified(two)
    assert not dual.drawn and dual.parts == 2 and len(dual.rectangles) == 2
    assert "which unit or body style" in found.message


def test_body_on_the_sheet_is_the_symbol_moved() -> None:
    """The same graphics on the sheet: each record is the library record moved by the component's
    location, and no rectangle is drawn."""
    symbol = get_symbol("Fenolite:LED")
    body = mapped(symbol)
    spec = PartSpec("D1", "D1", "red", "t.SchLib", "LED", None, "AAAAAAAA", body, {})
    plan = layout_sheet([spec])
    (placed,) = plan.parts
    document = read_schematic(write_schdoc_binary(plan), file="t.SchDoc")
    (component,) = document.components()
    children = document.children_of(component)
    assert not [r for r in children if isinstance(r, Rectangle)]
    dx, dy = placed.x * MIL, (plan.size.height - placed.y) * MIL
    moved = [
        (kind, tuple((x + dx, y + dy) for x, y in points), filled)
        for kind, points, filled in model_shapes(symbol)
    ]
    assert same(read_shapes(children), moved)
    assert sum(1 for record in schdoc_records(plan) if record[0][1] in GRAPHIC_RECORDS.values()) == len(
        symbol.graphics
    )


def test_graphic_record_keys() -> None:
    """The keys of each record, in the order ``schematic-records.md`` ("Graphics the writer draws") gives."""

    def keys(graphic: AltiumGraphic) -> list[str]:
        return [key for key, _ in graphic_fields(graphic, lambda x, y: (x, y))]

    here, there = (0, 0), (381_000, 254_000)
    assert keys(AltiumGraphic("line", 1, (here, there))) == [
        "RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.X_FRAC", "CORNER.Y",
        "LINEWIDTH", "COLOR",
    ]  # fmt: skip
    assert keys(AltiumGraphic("rectangle", 1, (here, there), True))[-3:] == ["COLOR", "AREACOLOR", "ISSOLID"]
    assert keys(AltiumGraphic("rectangle", 1, (here, there)))[-2:] == ["COLOR", "AREACOLOR"]
    assert keys(AltiumGraphic("ellipse", 1, (here,), True, 254_000)) == [
        "RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "RADIUS", "SECONDARYRADIUS", "LINEWIDTH",
        "COLOR", "AREACOLOR", "ISSOLID",
    ]  # fmt: skip
    assert keys(AltiumGraphic("ellipse", 1, (here,), False, 254_000))[-2:] == ["COLOR", "AREACOLOR"]
    assert keys(AltiumGraphic("polygon", 1, (here, there, (0, 254_000)), True)) == [
        "RECORD", "OWNERPARTID", "LINEWIDTH", "COLOR", "AREACOLOR", "ISSOLID", "LOCATIONCOUNT",
        "X1", "Y1", "X2", "X2_FRAC", "Y2", "X3", "Y3",
    ]  # fmt: skip
