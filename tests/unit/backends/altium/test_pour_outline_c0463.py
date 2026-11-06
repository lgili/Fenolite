# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygon outlines the pour used to refuse (change c0463; capability altium-pour, "Outline arcs poured" and
"Outlines made simple by Altium's rule"; ``docs/formats/altium/pcb-pour.md``, S-2221 and S-2222).

The boards are authored for these tests (``_altium_pour``). The writer writes a zone's outline as line
vertices, so a test that needs arc vertices puts them in the read polygon record, and gives the zone no
outline, as the import does for a record with an arc vertex (``altium.import.zone-arc``)."""

from __future__ import annotations

import dataclasses
import importlib.util
import math
from fractions import Fraction

import pytest
from _altium_pour import MIL, Board, clearance, mm, rect, via, zone

from fenolite.backends.altium.adapter.units import NM_PER_UNIT
from fenolite.backends.altium.pour import (
    PourReading,
    _chord_count,  # pyright: ignore[reportPrivateUsage]
    area,
    polygons_of,
    pour_reading,
    record_outline,
)
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.core.coords import Point

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

D = mm(0.0254)
"""The ``ARCRESOLUTION`` of the arc tests: 1 mil."""
R = mm(2)
"""The radius of the rounded corners."""
X0, Y0 = 1040 * MIL, 1040 * MIL
"""The lower-left corner of the outline in the Altium frame (Y up): 40 mil inside the board's corner,
which the writer puts at 1000 mil."""
W, H = mm(36), mm(26)


def _units(nm: int) -> Fraction:
    return Fraction(nm) / NM_PER_UNIT


def _line(x: int, y: int) -> OutlineVertex:
    zero = Fraction(0)
    return OutlineVertex(0, _units(x), _units(y), zero, zero, 0.0, 0.0, zero)


def _arc(x: int, y: int, cx: int, cy: int, radius: int, start: float, end: float) -> OutlineVertex:
    return OutlineVertex(1, _units(x), _units(y), _units(cx), _units(cy), start, end, _units(radius))


def _rounded(*, clockwise: bool = False) -> tuple[OutlineVertex, ...]:
    """The outline ``W`` by ``H`` from (``X0``, ``Y0``) with its lower-left and upper-right corners rounded
    by arcs of radius ``R``, counter-clockwise in the Altium frame (or clockwise)."""
    x1, y1 = X0 + W, Y0 + H
    if not clockwise:
        return (
            _line(X0 + R, Y0),
            _line(x1, Y0),
            _arc(x1, y1 - R, x1 - R, y1 - R, R, 0.0, 90.0),
            _line(x1 - R, y1),
            _line(X0, y1),
            _arc(X0, Y0 + R, X0 + R, Y0 + R, R, 180.0, 270.0),
        )
    return (
        _arc(X0 + R, Y0, X0 + R, Y0 + R, R, 180.0, 270.0),
        _line(X0, Y0 + R),
        _line(X0, y1),
        _line(x1 - R, y1),
        _arc(x1 - R, y1, x1 - R, y1 - R, R, 0.0, 90.0),
        _line(x1, y1 - R),
        _line(x1, Y0),
    )


def _with_outline(reading: PourReading, vertices: tuple[OutlineVertex, ...], d: str = "1mil") -> PourReading:
    """``reading`` whose one polygon record holds ``vertices`` and ``ARCRESOLUTION=d``, and whose zone has no
    outline, as the import gives a record with an arc vertex."""
    (polygon,) = reading.document.polygons
    fields = tuple((key, d if key == "ARCRESOLUTION" else value) for key, value in polygon.record.fields)
    record = PropertyRecord(polygon.record.raw, fields, polygon.record.lead)
    document = dataclasses.replace(
        reading.document, polygons=(dataclasses.replace(polygon, record=record, vertices=vertices),)
    )
    board = reading.design.board
    assert board is not None
    zones = tuple(dataclasses.replace(z, outline=()) for z in board.zones)
    design = dataclasses.replace(reading.design, board=dataclasses.replace(board, zones=zones))
    return dataclasses.replace(reading, document=document, design=design)


def _board() -> Board:
    return Board(zones=(zone("z1", "GND", rect(2, 2, 38, 28)),), vias=(via("v1", "GND", 20, 15),),
                 rules=(clearance(0.2),))  # fmt: skip


def _centres() -> tuple[Point, Point]:
    """The centres of the two corner arcs in the frame of the reading (Y negated)."""
    return Point(X0 + W - R, -(Y0 + H - R)), Point(X0 + R, -(Y0 + R))


def test_arc_chord_count_is_the_largest_step_within_d() -> None:
    """The fewest equal chords whose sagitta is at most ``d``: 5 for a quarter turn of 2 mm at 1 mil."""
    quarter = 90_000_000
    n = _chord_count(_units(R), quarter, D)
    assert n == 5
    for chords, within in ((n, True), (n - 1, False)):
        sagitta = R * (1 - math.cos(math.radians(90 / chords / 2)))
        assert (sagitta <= D) is within


@pytest.mark.parametrize("clockwise", [False, True], ids=["ccw", "cw"])
def test_arc_outline_is_chorded_on_the_arc(clockwise: bool) -> None:
    """Each arc becomes ``n`` chords whose ends lie on the arc, its two vertices at the ends, walked from
    vertex k to vertex k + 1 whatever the direction of the ring."""
    ring = record_outline(_rounded(clockwise=clockwise), D)
    assert len(ring) == 6 + 2 * 4  # six vertices and four inner chord ends per arc
    for centre in _centres():
        on = [p for p in ring if abs(math.hypot(p.x - centre.x, p.y - centre.y) - R) <= 2]
        assert len(on) == 6
    assert len(set(ring)) == len(ring)


def test_arc_outline_poured_within_d_of_the_rounded_area() -> None:
    """Scenario "A rounded outline": the polygon is poured, and its pour lies within ``d`` of the exact
    rounded area."""
    reading = _with_outline(_board().base(), _rounded())
    (polygon,) = polygons_of(reading)
    assert polygon.reason == ""
    (pour,) = pour_reading(reading).polygons
    assert pour.poured, pour.reason
    (piece,) = pour.pieces
    exact = W * H - 2 * (R * R - math.pi * R * R / 4)
    arcs = math.pi * R  # two quarter turns
    assert abs(float(area(piece)) - exact) <= D * arcs
    for centre in _centres():
        near = [p for p in piece.outer if abs(p.x - centre.x) <= R and abs(p.y - centre.y) <= R]
        for p in near:  # a vertex of the corner lies within d of the arc, outside it by rounding only
            distance = math.hypot(p.x - centre.x, p.y - centre.y)
            assert R - D <= distance <= R + 50


def test_arc_pour_leaves_the_polygon_record() -> None:
    """The pour adds regions and leaves the polygon record with its arc vertices as read."""
    reading = _with_outline(_board().base(), _rounded())
    before = reading.document.polygons
    pour_reading(reading)
    assert reading.document.polygons == before
    assert sum(v.kind for v in before[0].vertices) == 2


def test_arc_refused_without_radius_or_place() -> None:
    """An arc of zero radius, or one whose ends lie away from its two vertices, still refuses
    ``outline-arc``; an unreadable ``ARCRESOLUTION`` refuses ``threshold``."""
    base = _board().base()
    vertices = list(_rounded())
    flat = dataclasses.replace(vertices[2], radius=Fraction(0))
    away = dataclasses.replace(vertices[2], cx=vertices[2].cx - _units(mm(1)))
    for bad in (flat, away):
        reading = _with_outline(base, (*vertices[:2], bad, *vertices[3:]))
        (polygon,) = polygons_of(reading)
        assert polygon.reason == "outline-arc"
        (pour,) = pour_reading(reading).polygons
        assert pour.reason == "outline-arc"
    (polygon,) = polygons_of(_with_outline(base, _rounded(), d="none"))
    assert polygon.reason == "threshold"


# --- 2.2: outlines made simple ------------------------------------------------------------------------------


def _poured(outline: tuple[Point, ...], *vias: tuple[float, float]) -> tuple[str, int]:
    """The reason and the number of pieces of one ``GND`` polygon of ``outline`` (authored frame) with a
    ``GND`` via at each of ``vias`` (one at (6, 6) by default)."""
    places = vias or ((6, 6),)
    board = Board(zones=(zone("z1", "GND", outline),), vias=tuple(via(f"v{k}", "GND", x, y) for k, (x, y) in
                  enumerate(places)), rules=(clearance(0.2),))  # fmt: skip
    (pour,) = pour_reading(board.base()).polygons
    return pour.reason, len(pour.pieces)


def test_repeat_vertex_kept_once() -> None:
    """An outline that repeats a vertex, as two polygons of the public rows do (S-2222), is poured as the
    ring without the repeat."""
    square = rect(2, 2, 12, 12)
    assert _poured((*square[:3], square[2], square[3])) == ("", 1)


def test_touch_at_a_vertex_pours_two_pieces() -> None:
    """Scenario "A ring touching itself": an outline of two squares that share one vertex is poured as two
    pieces, one per square."""
    a, b = rect(2, 2, 12, 12), rect(12, 12, 22, 22)
    touching = (a[0], a[1], a[2], b[1], b[2], b[3], a[2], a[3])
    assert _poured(touching, (6, 6), (18, 18)) == ("", 2)


def test_crossing_ring_stays_refused() -> None:
    """A ring that crosses itself (a bow tie) still refuses ``outline``: no source shows Altium's fill."""
    a = rect(2, 2, 12, 12)
    assert _poured((a[0], a[2], a[1], a[3]))[0] == "outline"
