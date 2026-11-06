# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fill of an Altium document stays a fill through a conversion to KiCad and back (change c0450)."""

import dataclasses
import math
from collections import Counter

from _convert import two_layer

from fenolite.backends.altium import fills, lower, pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import FillRecord, RegionRecord
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.design import Design

MM = 1_000_000
TOP = 1


def _fill(ident: str, *points: Point, kind: str = "polygon", marked: bool = True) -> Graphic:
    graphic = Graphic(id=ident, kind=kind, layer="F.SilkS", points=points, width=0, filled=True)  # type: ignore[arg-type]
    return fills.marked(graphic) if marked else graphic


def _turned(angle: float, cx: int, cy: int, w: int, h: int) -> tuple[Point, ...]:
    """The corners of a ``w`` × ``h`` rectangle about ``(cx, cy)`` turned by ``angle`` degrees."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))
    return tuple(Point(round(cx + x * c - y * s), round(cy + x * s + y * c)) for x, y in corners)


def _design() -> Design:
    """The two-layer board with a marked square, a marked turned rectangle, an unmarked square of the board
    and a marked square of its first footprint, all on the top overlay."""
    design = two_layer()
    assert design.board is not None
    square = (Point(10 * MM, 10 * MM), Point(12 * MM, 12 * MM))
    graphics = (
        _fill("gra-square", *square, kind="rect"),
        _fill("gra-turned", *_turned(30.0, 20 * MM, 20 * MM, 3 * MM, MM)),
        _fill("gra-plain", Point(30 * MM, 0), Point(32 * MM, 2 * MM), kind="rect", marked=False),
    )
    first, *rest = design.board.footprints
    own = _fill("gra-own", Point(-MM, 2 * MM), Point(MM, 3 * MM), kind="rect")
    first = dataclasses.replace(first, graphics=(*first.graphics, own))
    board = dataclasses.replace(
        design.board, graphics=(*design.board.graphics, *graphics), footprints=(first, *rest)
    )
    return dataclasses.replace(design, board=board)


def test_a_fill_uuid_carries_its_marker() -> None:
    text = fills.fill_uuid("gfx-1")
    assert fills.is_fill_uuid(text) and text.startswith("616c7466-696c-8")
    assert text == fills.fill_uuid("gfx-1") and text != fills.fill_uuid("gfx-2")
    assert not fills.is_fill_uuid("00000000-0000-4000-8000-000000000000")


def test_fill_geometry_of_a_ring() -> None:
    """Scenario "A fill comes back as a fill" (record level): a square ring is a fill of rotation 0, a turned
    rectangle one of its turn about its centre, in either winding; a trapezium is none."""
    assert pcbdoc.fill_geometry([(0, 0), (100, 0), (100, 50), (0, 50)]) == ((0, 0), (100, 50), 0.0)
    ring = [(p.x, p.y) for p in _turned(30.0, 1_000_000, 2_000_000, 400_000, 100_000)]
    a, b, turn = pcbdoc.fill_geometry(ring) or ((0, 0), (0, 0), 0.0)
    assert abs(turn - 30.0) < 1e-4 and (b[0] - a[0], b[1] - a[1]) == (400_000, 100_000)
    assert ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2) == (1_000_000, 2_000_000)
    back = pcbdoc.fill_geometry(ring[::-1])
    assert back is not None and abs(back[2] % 180 - 30.0) < 1e-4
    assert pcbdoc.fill_geometry([(0, 0), (100, 0), (80, 50), (20, 50)]) is None


def test_a_fill_record_is_read_back() -> None:
    record = rec.fill_record(TOP, 0x0100_0001, (10, 20), (30, 40), 45.0, net=3, component=1)
    assert record[0] == rec.FILL and len(record) == 1 + 4 + rec.FILL_SIZE
    body = record[5:]
    assert body[37:42] == bytes(5) and body[42:46] == bytes.fromhex("01000001") and body[46:] == bytes(4)


def test_marked_fills_are_written_as_fills() -> None:
    """Scenario "A fill comes back as a fill": the marked square, the marked turned rectangle and the marked
    square of the footprint are fill records, the last with its component; the unmarked square is a region."""
    design = _design()
    written = lower.write_design(design, allow_lossy=True)
    document = read_pcbdoc(written.files[f"{design.header.name}.PcbDoc"])
    found = [f for f in document.fills if isinstance(f, FillRecord)]
    owners = Counter("component" if f.prefix.component is not None else "free" for f in found)
    assert owners == {"free": 2, "component": 1}
    # the board's Y axis points down and Altium's up: the turn of 30 degrees is one of -30 there
    free = sorted(round(f.rotation % 180, 3) for f in found if f.prefix.component is None)
    assert free == [0.0, 150.0]
    # the square of the footprint turns with its placement
    assert design.board is not None
    turn = design.board.footprints[0].rotation / 1_000_000
    (own,) = [f for f in found if f.prefix.component is not None]
    assert round(own.rotation % 180, 3) == round(-turn % 180, 3)
    overlay = rec.LAYER_MAP["F.SilkS"]
    regions = [r for r in document.regions if isinstance(r, RegionRecord) and r.prefix.layer == overlay]
    assert len(regions) == 1 and regions[0].prefix.component is None
