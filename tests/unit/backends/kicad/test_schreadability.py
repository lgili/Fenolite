# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Readability measures of a sheet (capability kicad-schematic, "Readability measures of a generated
sheet"; change c0406). Hermetic: a wired sheet of an authored design is built in memory and changed."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from _wireddesigns import DESIGNS, build_authored

from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.schreadability import measure_sheet, measure_sheets
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.schematic import Junction, SchematicSheet, Wire

G = schlayout.GRID


@cache
def opamp() -> SchematicSheet:
    output = build_authored(DESIGNS["opamp"]())
    assert output.schematic is not None
    return output.schematic.sheet


def far(sheet: SchematicSheet) -> Point:
    """A grid point right of everything on ``sheet``."""
    xs = [p.x for w in sheet.wires for p in (w.start, w.end)] + [s.position.x for s in sheet.symbols]
    ys = [p.y for w in sheet.wires for p in (w.start, w.end)]
    return Point(max(xs) + 40 * G, min(ys) + 10 * G)


def wire(start: Point, end: Point, tag: str) -> Wire:
    return Wire(start, end, id=derived_id("wir", "fenolite", f"test:{tag}"))


def with_wires(sheet: SchematicSheet, *wires: Wire, junctions: tuple[Junction, ...] = ()) -> SchematicSheet:
    return replace(sheet, wires=(*sheet.wires, *wires), junctions=(*sheet.junctions, *junctions))


def test_clean_wired_sheet() -> None:
    found = measure_sheet(opamp())
    assert found.wires == len(opamp().wires) and found.junctions == len(opamp().junctions)
    assert found.power_symbols > 0 and found.label_count == len(opamp().labels)
    assert (found.wire_over_pin, found.wire_over_body, found.four_way, found.bare_tees, found.overlaps) == (
        0,
        0,
        0,
        0,
        0,
    )


def test_a_crossing_is_counted() -> None:
    o = far(opamp())
    sheet = with_wires(
        opamp(),
        wire(Point(o.x - 4 * G, o.y), Point(o.x + 4 * G, o.y), "h"),
        wire(Point(o.x, o.y - 4 * G), Point(o.x, o.y + 4 * G), "v"),
    )
    assert measure_sheet(sheet).crossings == measure_sheet(opamp()).crossings + 1


def test_four_wires_at_one_point() -> None:
    o = far(opamp())
    arms = [
        Point(o.x - 4 * G, o.y),
        Point(o.x + 4 * G, o.y),
        Point(o.x, o.y - 4 * G),
        Point(o.x, o.y + 4 * G),
    ]
    sheet = with_wires(opamp(), *(wire(o, arm, f"arm{i}") for i, arm in enumerate(arms)))
    assert measure_sheet(sheet).four_way == 1


def test_a_tee_without_a_junction() -> None:
    o = far(opamp())
    through = wire(Point(o.x - 4 * G, o.y), Point(o.x + 4 * G, o.y), "through")
    stem = wire(o, Point(o.x, o.y + 4 * G), "stem")
    assert measure_sheet(with_wires(opamp(), through, stem)).bare_tees == 1
    dot = Junction(o, id=derived_id("wir", "fenolite", "test:dot"))
    assert measure_sheet(with_wires(opamp(), through, stem, junctions=(dot,))).bare_tees == 0


def test_a_wire_over_a_body_and_a_pin() -> None:
    sheet = opamp()
    u1 = next(s for s in sheet.symbols if s.ref == "U1")
    across = wire(
        Point(u1.position.x - 20 * G, u1.position.y), Point(u1.position.x + 20 * G, u1.position.y), "x"
    )
    found = measure_sheet(with_wires(sheet, across))
    assert found.wire_over_body >= 1


def test_measures_add_up() -> None:
    one = measure_sheet(opamp())
    two = measure_sheets([opamp(), opamp()])
    assert two.wires == 2 * one.wires and two.label_count == 2 * one.label_count


def test_readable_blink_measured() -> None:
    """Scenario "Readable sheet measured"."""
    from _buildhelp import blink, build

    output = build(blink(), schematic_layout="readable")
    assert output.schematic is not None
    sheet = output.schematic.sheet
    found = measure_sheet(sheet)
    assert found.labels["global"] == len(sheet.labels)
    assert found.junctions == 0 and found.crossings == 0
