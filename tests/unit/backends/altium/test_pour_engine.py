# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour engine on authored boards (change c0215; capability altium-pour, "Pour engine"; the inputs of
``docs/formats/altium/pcb-pour.md``). Each test is one input: what the engine pours, judged with the exact
predicates of the copper check (``geometry.thick``) and with points that must or must not hold copper."""

from __future__ import annotations

import dataclasses
import importlib.util

import pytest
from _altium_pour import MIL, Board, at, clearance, mm, pad, rect, track, via, zone

from fenolite.backends.altium.pour import PolygonPour, PourReading, PourResult, area, pour_reading
from fenolite.backends.altium.read.pcb import PolygonRecord
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.polygon import keyhole_ring
from fenolite.geometry.predicates import Location, point_in_ring
from fenolite.geometry.thick import Thick, thick_closer_than, thick_gap_floor, thick_touch
from fenolite.model.board import Keepout, ZoneSettings
from fenolite.model.rules import Rule, Selector

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
ARC = round(0.5 * MIL)
"""The ``ARCRESOLUTION`` a polygon is written with (0.5 mil)."""


def _flip(point: Point) -> Point:
    """A point of the authored board in the frame of the reading: the writer places the board's
    lower-left corner at 1000 mil and the reader negates Y (``pcbdoc.Frame``)."""
    return Point(point.x + 1000 * MIL, -(30 * 1_000_000 - point.y) - 1000 * MIL)


def _covered(pour: PolygonPour, point: Point) -> bool:
    """Whether ``point`` (in the authored frame) lies in the copper of ``pour``."""
    target = _flip(point)
    for piece in pour.pieces:
        if point_in_ring(target, piece.outer) is Location.OUTSIDE:
            continue
        if not any(point_in_ring(target, hole) is Location.INSIDE for hole in piece.holes):
            return True
    return False


def _thick(piece: Polygon) -> Thick:
    return Thick(tuple(keyhole_ring(piece.outer, piece.holes).ring), 0, filled=True)


def _of(result: PourResult, net: str, layer: str = "F.Cu") -> PolygonPour:
    (found,) = [p for p in result.polygons if p.net == net and p.layer == layer]
    assert found.poured, found.reason
    return found


def _pad_shape(reading: PourReading, x: float, y: float) -> Thick:
    """The copper on ``F.Cu`` of the pad at (``x``, ``y``) of the authored frame, within the few nanometres
    of the document's unit (the import names pads by ids of its own)."""
    target = _flip(at(x, y))
    (found,) = [p for p in reading.pads if abs(p.position.x - target.x) + abs(p.position.y - target.y) <= 4]
    entry = next(e for e in found.copper if e.layer == "F.Cu")
    return Thick(entry.core, entry.width, entry.filled)


def _with_record(reading: PourReading, **values: str) -> PourReading:
    """``reading`` with the keys ``values`` set in every polygon record (a form the writer does not write)."""
    polygons: list[PolygonRecord] = []
    for polygon in reading.document.polygons:
        fields = tuple((key, values.get(key, value)) for key, value in polygon.record.fields)
        record = PropertyRecord(polygon.record.raw, fields, polygon.record.lead)
        polygons.append(dataclasses.replace(polygon, record=record))
    return dataclasses.replace(
        reading, document=dataclasses.replace(reading.document, polygons=tuple(polygons))
    )


# --- 3.1: the area ------------------------------------------------------------------------------------------


def test_clearance_around_a_pad_of_another_net() -> None:
    """Scenario "Clearance around a pad of another net"."""
    board = Board(zones=(zone("z1", "GND"),), pads=(pad("p1", "VIN", 10, 10, shape="circle", size=(1, 1)),),
                  vias=(via("v1", "GND", 30, 20),), rules=(clearance(0.3),))  # fmt: skip
    reading, result = board.pour()
    gnd = _of(result, "GND")
    (piece,) = gnd.pieces
    assert len(piece.holes) == 1
    vin = _pad_shape(reading, 10, 10)
    rule = mm(0.3) - 3  # the rule as it reads back from the document's unit
    assert not thick_closer_than(_thick(piece), vin, rule)
    assert thick_gap_floor(_thick(piece), vin) <= mm(0.3) + ARC


def test_board_edge_and_its_clearance() -> None:
    """Input I17: a polygon on the board's outline keeps the Board Outline Clearance from the edge."""
    edge = Rule(id="r_edge", name="edge", kind="edge_clearance", selector_a=Selector("all"), min=mm(0.5))
    board = Board(zones=(zone("z1", "GND", rect(-5, -5, 45, 35)),), vias=(via("v1", "GND", 20, 15),),
                  rules=(clearance(0.2), edge))  # fmt: skip
    _, result = board.pour()
    (piece,) = _of(result, "GND").pieces
    box = piece.bbox()
    corners = (_flip(at(0, 0)), _flip(at(40, 30)))
    x0, x1 = sorted(c.x for c in corners)
    y0, y1 = sorted(c.y for c in corners)
    inset = mm(0.5) - 3  # the rule as it reads back from the document's unit
    assert box.x0 - x0 >= inset and box.y0 - y0 >= inset and x1 - box.x1 >= inset and y1 - box.y1 >= inset
    assert box.x0 - x0 <= mm(0.5) + ARC


def test_keep_out_is_a_void() -> None:
    """Input I16: a keep-out of copper on the polygon's layer is a void at the governing clearance (a keep-out
    of tracks too, so the writer keeps it a keep-out region and no polygon cut-out, c0439)."""
    keepout = Keepout(
        id="k1", outline=rect(10, 10, 14, 14), layers=("F.Cu",), no_copper_pour=True, no_tracks=True
    )
    board = Board(zones=(zone("z1", "GND"),), vias=(via("v1", "GND", 30, 20),), keepouts=(keepout,),
                  rules=(clearance(0.2),))  # fmt: skip
    _, result = board.pour()
    gnd = _of(result, "GND")
    assert not _covered(gnd, at(12, 12))
    assert not _covered(gnd, at(14.1, 12))
    assert not _covered(gnd, at(14.1, 14.1))
    assert _covered(gnd, at(14.18, 14.18))
    assert _covered(gnd, at(14.5, 12))


def test_polygon_cutout_keeps_no_clearance() -> None:
    """A polygon cut-out (a region of ``KIND=1``, written for a rule area of poured copper alone, c0439) is
    taken out of the area with no clearance: Altium's repour of row -02 pours to its edge (S-2227)."""
    cutout = Keepout(id="k1", outline=rect(10, 10, 14, 14), layers=("F.Cu",), no_copper_pour=True)
    board = Board(zones=(zone("z1", "GND"),), vias=(via("v1", "GND", 30, 20),), keepouts=(cutout,),
                  rules=(clearance(0.2),))  # fmt: skip
    _, result = board.pour()
    gnd = _of(result, "GND")
    assert not _covered(gnd, at(12, 12))
    assert not _covered(gnd, at(13.95, 12))
    assert _covered(gnd, at(14.05, 12))


def test_a_via_without_a_pad_joins_its_polygon() -> None:
    """A via without a pad shape (diameter equal to its drill) is joined by a polygon of its net as a via, and
    keeps the clearance of its hole from a polygon of another net (S-2227, row -02;
    ``H-A-IMP-VIA-PADLESS``)."""
    padless = {"diameter": 0.3, "drill": 0.3}
    board = Board(zones=(zone("z1", "GND", rect(1, 1, 19, 29)), zone("z2", "VIN", rect(21, 1, 39, 29))),
                  vias=(via("v1", "GND", 10, 15, **padless), via("v2", "GND", 30, 15, **padless),
                        via("v3", "VIN", 35, 25)),
                  rules=(clearance(0.2),), full_drill=True)  # fmt: skip
    _, result = board.pour()
    assert _covered(_of(result, "GND"), at(10.2, 15))  # the GND pour reaches its own via
    assert not _covered(_of(result, "VIN"), at(30.3, 15))  # the VIN pour keeps 0.2 from the GND hole


# --- 3.2: the connections -----------------------------------------------------------------------------------


def _relief_board(settings: ZoneSettings) -> Board:
    return Board(
        zones=(zone("z1", "GND", settings=settings),),
        pads=(pad("p1", "GND", 20, 15, shape="circle", size=(1.6, 1.6), kind="thru_hole", drill=0.8),),
        rules=(clearance(0.2),),
    )


def test_relief_of_a_pad_of_the_polygons_net() -> None:
    """Scenario "Relief of a pad of the polygon's net": four conductors at 0°, 90°, 180° and 270° cross the
    air gap; at 45° the gap is empty; the pad touches the piece."""
    reading, result = _relief_board(ZoneSettings(thermal_gap=mm(0.25), thermal_spoke_width=mm(0.25))).pour()
    gnd = _of(result, "GND")
    middle = 0.8 + 0.125  # the pad's radius and half the air gap
    for dx, dy in ((middle, 0), (0, middle), (-middle, 0), (0, -middle)):
        assert _covered(gnd, at(20 + dx, 15 + dy)), (dx, dy)
    diagonal = middle / 2**0.5
    for dx, dy in (
        (diagonal, diagonal),
        (-diagonal, diagonal),
        (diagonal, -diagonal),
        (-diagonal, -diagonal),
    ):
        assert not _covered(gnd, at(20 + dx, 15 + dy)), (dx, dy)
    pad_shape = _pad_shape(reading, 20, 15)
    assert any(thick_touch(_thick(piece), pad_shape) for piece in gnd.pieces)


def test_relief_conductor_over_its_pad_outside_the_outline() -> None:
    """A conductor runs from the pad's centre over the part of its pad that lies outside the polygon's
    outline (S-2224, row -07: the outline cuts a pad of the polygon's net and Altium's conductor starts at
    the pad's centre, outside it)."""
    settings = ZoneSettings(thermal_gap=mm(0.25), thermal_spoke_width=mm(0.25))
    board = Board(
        zones=(zone("z1", "GND", rect(1, 1, 19.6, 29), settings=settings),),
        pads=(pad("p1", "GND", 20, 15, size=(2.0, 1.0)),),
        rules=(clearance(0.2),),
    )
    _, result = board.pour()
    gnd = _of(result, "GND")
    assert _covered(gnd, at(19.8, 15))  # on the pad, outside the outline (x = 19.6), on the conductor
    assert _covered(gnd, at(18.9, 15))  # the conductor across the air gap
    assert not _covered(gnd, at(19.8, 15.4))  # on the pad beside the conductor
    assert not _covered(gnd, at(20.5, 15))  # past the pad's centre


def test_direct_connect_and_no_connect() -> None:
    """Input I7: a solid zone joins the pad without a void; a zone without connection keeps the void of its
    clearance and no conductor, and the pad touches no copper of the pour."""
    reading, result = _relief_board(ZoneSettings(connection="solid")).pour()
    assert _covered(_of(result, "GND"), at(20 + 0.9, 15))
    reading, result = _relief_board(ZoneSettings(connection="none", clearance=mm(0.3))).pour()
    gnd = _of(result, "GND")
    for dx, dy in ((0.9, 0), (0, 0.9), (-0.9, 0), (0, -0.9)):
        assert not _covered(gnd, at(20 + dx, 15 + dy))
    pad_shape = _pad_shape(reading, 20, 15)
    assert not any(thick_touch(_thick(piece), pad_shape) for piece in gnd.pieces)


# --- 3.3: the net's own objects and the order ---------------------------------------------------------------


def test_pour_over_same_net_objects() -> None:
    """Input I8: style 1 covers a track of the polygon's net; styles 0 and 2 keep its clearance."""
    board = Board(zones=(zone("z1", "GND"),), tracks=(track("t1", "GND", (10, 15), (30, 15), width=0.5),),
                  vias=(via("v1", "GND", 5, 5),), rules=(clearance(0.3),))  # fmt: skip
    reading = board.base()
    beside = at(20, 15 + 0.25 + 0.15)  # inside the clearance of the track, outside the track
    assert _covered(_of(pour_reading(reading), "GND"), beside)
    for style in ("0", "2"):
        assert not _covered(_of(pour_reading(_with_record(reading, POUROVERSTYLE=style)), "GND"), beside)


def test_pour_order_on_a_layer() -> None:
    """Input I9: of two overlapping polygons of two nets, the one poured first takes the shared area and
    the later one keeps the clearance from its copper."""
    first = zone("a", "VIN", rect(1, 1, 25, 29), priority=2)
    later = zone("b", "GND", rect(15, 1, 39, 29), priority=1)
    board = Board(zones=(first, later), vias=(via("v1", "VIN", 5, 15), via("v2", "GND", 35, 15)),
                  rules=(clearance(0.3),))  # fmt: skip
    _, result = board.pour()
    vin, gnd = _of(result, "VIN"), _of(result, "GND")
    assert _covered(vin, at(20, 15)) and not _covered(gnd, at(20, 15))
    assert _covered(gnd, at(25.5, 15)) and not _covered(gnd, at(25.2, 15))
    for a in vin.pieces:
        for b in gnd.pieces:
            assert not thick_closer_than(_thick(a), _thick(b), mm(0.3) - 3)


# --- 3.4: necks, islands, dead copper -----------------------------------------------------------------------


def _neck_board(width_mil: float) -> Board:
    """Two VIN pads 4 mm tall whose voids leave a GND neck ``width_mil`` wide between them."""
    gap = 0.4 + width_mil * MIL / 1_000_000  # twice the clearance of 0.2 mm, then the neck
    return Board(
        zones=(zone("z1", "GND"),),
        pads=(pad("p1", "VIN", 15, 15, size=(1, 4)), pad("p2", "VIN", 15 + 1 + gap, 15, size=(1, 4))),
        vias=(via("v1", "GND", 30, 25),),
        rules=(clearance(0.2),),
    )


def test_necks_below_and_above_the_width() -> None:
    """Scenario "Necks below and above the width" (``NECKWIDTHTHRESHOLD=5mil``)."""
    for width, kept in ((4.5, False), (5.5, True)):
        _, result = _neck_board(width).pour()
        middle = 15 + 0.5 + 0.2 + width * MIL / 2_000_000
        assert _covered(_of(result, "GND"), at(middle, 15)) is kept, width


def test_a_pinch_the_opening_closes_again_is_parted() -> None:
    """Input I10 (S-2227): two discs of 300 µm whose waist is narrower than the neck width of 200 µm. The
    opening's discs, grown back, would join them again at the waist; the pour parts them there. A waist wider
    than the width stays one piece."""
    from fenolite.backends.altium.pour import _Geometry, disc  # pyright: ignore[reportPrivateUsage]
    from fenolite.geometry.boolean.clipper import ClipperBackend

    geometry = _Geometry(ClipperBackend())
    for apart, pieces in ((580_000, 2), (450_000, 1)):  # waists of 153 µm and 397 µm
        copper = geometry.union([disc(Point(0, 0), 300_000, 50), disc(Point(apart, 0), 300_000, 50)])
        assert len(copper) == 1
        opened = geometry.open(copper, 200_000, 50)
        assert len(opened) == pieces, apart
        assert sum(area(piece) for piece in opened) > area(copper[0]) * 9 // 10


def test_a_spike_of_almost_no_angle_is_opened() -> None:
    """Input I10: the tip of a spike of almost no angle (row -06) lies where the inscribed circle would
    touch its edges far beyond the board; the opening takes the spike off and stays in range."""
    from fenolite.backends.altium.pour import _Geometry  # pyright: ignore[reportPrivateUsage]
    from fenolite.geometry.boolean.clipper import ClipperBackend

    geometry = _Geometry(ClipperBackend())
    square = (Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 10_000_000))
    spike = (Point(5_000_010, 10_000_000), Point(5_000_000, 30_000_000), Point(4_999_990, 10_000_000))
    copper = (Polygon((*square, *spike, Point(0, 10_000_000))),)
    opened = geometry.open(copper, 200_000, 50)
    assert len(opened) == 1
    assert opened[0].bbox().y1 <= 10_000_000


def test_islands_below_the_area_whatever_they_connect() -> None:
    """Input I12: a piece below 2500 mil² is removed even with a GND via on it; one above is kept."""

    def ring(x: float, size: float) -> tuple[tuple[str, tuple[float, float], tuple[float, float]], ...]:
        return (
            (f"t{x}a", (x, 10), (x + size, 10)), (f"t{x}b", (x + size, 10), (x + size, 10 + size)),
            (f"t{x}c", (x + size, 10 + size), (x, 10 + size)), (f"t{x}d", (x, 10 + size), (x, 10)),
        )  # fmt: skip

    small, large = 1.6, 2.4  # the inside less the clearances: below and above 1.613 mm²
    tracks = tuple(track(i, "VIN", a, b, width=0.2) for i, a, b in (*ring(5, small), *ring(20, large)))
    board = Board(zones=(zone("z1", "GND"),), tracks=tracks,
                  vias=(via("v1", "GND", 5 + small / 2, 10 + small / 2, diameter=0.3, drill=0.15),
                        via("v2", "GND", 20 + large / 2, 10 + large / 2, diameter=0.3, drill=0.15),
                        via("v3", "GND", 35, 25)),
                  rules=(clearance(0.2),))  # fmt: skip
    _, result = board.pour()
    gnd = _of(result, "GND")
    assert not _covered(gnd, at(5 + small / 2 + 0.3, 10 + small / 2))
    assert _covered(gnd, at(20 + large / 2 + 0.4, 10 + large / 2))
    threshold = 2500 * MIL * MIL / 10**8  # 2500 mil² in nm² (``AREATHRESHOLD`` in square file units)
    assert all(area(piece) >= threshold for piece in gnd.pieces)


def test_dead_copper() -> None:
    """Scenario "Dead copper": an area enclosed by VIN tracks without a GND object is removed; with
    ``REMOVEDEAD=FALSE`` it stays."""
    ring = ((5, 10), (12, 10), (12, 17), (5, 17))
    tracks = tuple(track(f"t{k}", "VIN", ring[k], ring[(k + 1) % 4], width=0.3) for k in range(4))
    board = Board(zones=(zone("z1", "GND"),), tracks=tracks, vias=(via("v1", "GND", 30, 20),),
                  rules=(clearance(0.2),))  # fmt: skip
    reading, result = board.pour()
    assert not _covered(_of(result, "GND"), at(8.5, 13.5))
    assert _covered(_of(pour_reading(_with_record(reading, REMOVEDEAD="FALSE")), "GND"), at(8.5, 13.5))


def test_a_polygon_without_a_pad_of_its_net_pours_nothing() -> None:
    """Input I13: no object of the polygon's net, and no copper; without a net, nothing either."""
    _, result = Board(zones=(zone("z1", "GND"),), rules=(clearance(0.2),)).pour()
    (only,) = result.polygons
    assert only.poured and only.pieces == ()
    _, result = Board(
        zones=(zone("z1", None),), vias=(via("v1", "GND", 5, 5),), rules=(clearance(0.2),)
    ).pour()
    (only,) = result.polygons
    assert only.poured and only.pieces == ()


def test_repeatable() -> None:
    """Scenario "Repeatable"."""
    reading = _neck_board(5.5).base()
    assert pour_reading(reading) == pour_reading(reading)
