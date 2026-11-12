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

from fenolite.backends.altium import pcbdoc, pcbrecords
from fenolite.backends.altium import pour as engine
from fenolite.backends.altium.adapter.copper import is_keepout, record_restrictions
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.pour import PolygonPour, PourReading, PourResult, area, pour_reading, read_pour
from fenolite.backends.altium.pourcompare import pour_pieces
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import PolygonRecord
from fenolite.backends.altium.read.pcbprims import FillRecord, PadRecord
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.core.coords import Point, Size
from fenolite.geometry import Polygon
from fenolite.geometry.polygon import keyhole_ring
from fenolite.geometry.predicates import Location, point_in_ring
from fenolite.geometry.thick import Thick, thick_closer_than, thick_gap_floor, thick_touch
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Graphic, Keepout, Padstack, PadstackLayer, ZoneSettings
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


@pytest.mark.parametrize("intrudes", [False, True])
def test_solid_pour_void_of_a_simple_octagonal_smd_pad(
    monkeypatch: pytest.MonkeyPatch, intrudes: bool
) -> None:
    """The pad dimensions grow by clearance before its corners are cut (S-2314)."""
    board = Board(
        zones=(zone("z1", "GND"),),
        pads=(
            pad("octagon", "OTHER", 10, 10, size=(1.5, 0.75)),
            pad("rectangle", "OTHER", 20, 10, size=(1.5, 0.75)),
        ),  # fmt: skip
        vias=(via("tie", "GND", 30, 20),),
        rules=(clearance(0.2),),
    )
    spec = board.spec()
    first = board.base().document.pads[0]
    assert isinstance(first, PadRecord) and first.prefix.net is not None
    octagon = pcbrecords.pad_record(
        name=first.name, layer=first.prefix.layer, x=first.x, y=first.y, size=first.size_top,
        shape=3, rotation=first.rotation, net=first.prefix.net,
    )  # fmt: skip
    write = pcbdoc._write

    def authored_write(*args, **kwargs):
        # Inject the authored raw pad on both passes, leaving the normal writer/self-check in place.
        source = open_compound(write(*args, **kwargs))
        streams = {key: source.read(key) for key in source.streams()}
        assert streams["Pads6/Data"].count(first.raw) == 1
        streams["Pads6/Data"] = streams["Pads6/Data"].replace(first.raw, octagon, 1)
        return write_compound(storage_from_paths(streams))

    def with_intrusion(reading, **options):
        result = pour_reading(reading, **options)
        intrusion = Polygon(tuple(_flip(p) for p in rect(10.78, 10.41, 10.8, 10.43)))
        return PourResult(
            tuple(
                dataclasses.replace(p, pieces=(*p.pieces, intrusion)) if p.poured else p
                for p in result.polygons
            )
        )

    monkeypatch.setattr(pcbdoc, "_write", authored_write)
    if intrudes:
        monkeypatch.setattr(engine, "pour_reading", with_intrusion)
    data = pcbdoc.write_pcbdoc_result(spec, filename="pour.PcbDoc", pour="computed")
    reading = read_pour(data.data)
    assert isinstance(reading.document.pads[0], PadRecord) and reading.document.pads[0].shape_top == 3
    assert data.pour is not None
    if intrudes:
        assert data.pour.refused == (("copper-check", "z1", "F.Cu"),)
        assert not pour_pieces(reading, 0)
        return
    assert data.pour.poured == 1 and not data.pour.refused
    copper = dataclasses.replace(_of(pour_reading(reading), "GND"), pieces=pour_pieces(reading, 0))
    assert _covered(copper, at(10.87, 10.5))
    assert not _covered(copper, at(20.87, 10.5))
    assert not _covered(copper, at(10.8, 10.429))
    assert _covered(copper, at(10.97, 10))


def _round_drill_board(diameter: float, *, own: bool, th: int, hole: int) -> pcbdoc.PcbDocSpec:
    layer = "In1.Cu"
    stack = ("F.Cu", layer, "In2.Cu", "B.Cu")
    drilled = pad("p1", "GND" if own else "VIN", 20, 15, shape="circle", size=(3.4, 3.4),
                  kind="thru_hole", drill=2)  # fmt: skip
    sizes = (3.4, diameter, 3.4, 3.4)
    parts = tuple(
        PadstackLayer(name, "circle", Size(mm(size), mm(size)))
        for name, size in zip(stack, sizes, strict=True)
    )
    drilled = dataclasses.replace(
        drilled,
        pad=dataclasses.replace(drilled.pad, layers=stack, padstack=Padstack(id="stack", layers=parts)),
    )
    settings = ZoneSettings(thermal_gap=mm(0.25), thermal_spoke_width=mm(0.25), min_thickness=mm(0.15))
    board = Board(
        zones=(zone("z1", "GND", layer=layer, settings=settings),),
        pads=(drilled,),
        vias=(via("v1", "GND", 30, 20),),
        rules=(clearance(0.1524),),
    ).spec()
    (rule,) = board.design_rules
    matrix = (
        f"ClearanceObj_THPad-ClearanceObj_Poly:{th * 10_000};"
        f"ClearanceObj_Hole-ClearanceObj_Poly:{hole * 10_000}"
    )
    keys = tuple((k, matrix if k == "OBJECTCLEARANCES" else v) for k, v in rule.keys)
    return dataclasses.replace(
        board, copper_layers=stack, design_rules=(dataclasses.replace(rule, keys=keys),)
    )


def _round_drill_pour(diameter: float, *, own: bool, th: int = 6, hole: int = 6) -> PolygonPour:
    board = _round_drill_board(diameter, own=own, th=th, hole=hole)
    data = pcbdoc.write_pcbdoc_result(
        board, filename="round-drill.PcbDoc", pour="computed", pour_regions=False
    )
    return _of(pour_reading(read_pour(data.data)), "GND", "In1.Cu")


@pytest.mark.parametrize(
    ("diameter", "th", "hole", "radius"),
    [(1.6, 6, 6, 1.1524), (2, 16, 6, 1.1524), (2.4, 6, 16, 1.4064), (2.4, 16, 6, 1.6064)],
)
def test_clearance_of_a_concentric_round_plated_drill(
    diameter: float, th: int, hole: int, radius: float
) -> None:
    """S-2312: a pad with no annular ring takes the hole cell. A pad with a ring keeps both clearances."""
    pour = _round_drill_pour(diameter, own=False, th=th, hole=hole)
    assert not _covered(pour, at(20 + radius - 0.03, 15))
    assert _covered(pour, at(20 + radius + 0.03, 15))


def test_relief_air_gap_reaches_a_concentric_round_plated_drill() -> None:
    """S-2312: the own-net relief of a pad below drill size matches the pad equal to drill size."""
    below = _round_drill_pour(1.6, own=True)
    equal = _round_drill_pour(2, own=True)
    above = _round_drill_pour(2.4, own=True)
    assert below.pieces == equal.pieces
    assert above.pieces != equal.pieces


def test_written_pour_keeps_the_hole_cell_for_a_plated_pad_without_an_annular_ring() -> None:
    """A correctly poured 6 mil Hole void survives the writer self-check even with a 16 mil TH Pad cell."""
    board = _round_drill_board(2, own=False, th=16, hole=6)
    written = pcbdoc.write_pcbdoc_result(board, filename="round-drill.PcbDoc", pour="computed")
    assert written.pour is not None and not written.pour.refused
    document = read_pour(written.data).document
    (polygon,) = document.polygons
    assert polygon.layer == "MID1"
    assert document.regions


@pytest.mark.parametrize(("diameter", "hole"), [(1.6, 6), (2.4, 16)])
def test_written_pour_refuses_copper_too_close_to_the_drill(
    monkeypatch: pytest.MonkeyPatch, diameter: float, hole: int
) -> None:
    """The checker reads the real drill even if the test engine made its void with a smaller drill."""
    from fenolite.backends.altium import pour as engine

    real = engine.pour_reading

    def smaller(reading: PourReading, **options: object) -> PourResult:
        pads = tuple(dataclasses.replace(pad, drill=mm(1.5)) if pad.drill else pad for pad in reading.pads)
        return real(dataclasses.replace(reading, pads=pads), **options)  # type: ignore[arg-type]

    monkeypatch.setattr(engine, "pour_reading", smaller)
    board = _round_drill_board(diameter, own=False, th=6, hole=hole)
    written = pcbdoc.write_pcbdoc_result(board, filename="round-drill.PcbDoc", pour="computed")
    assert written.pour is not None
    assert written.pour.refused == (("copper-check", "z1", "In1.Cu"),)


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


@pytest.mark.parametrize("cutout", [False, True])
def test_generic_clearance_keeps_outer_overhang_and_board_cutout(cutout: bool) -> None:
    """An ordinary clearance does not clip the outer board shape. A real cut-out still excludes copper."""
    board = Board(
        zones=(zone("z1", "GND", rect(-2, 4, 12, 14)),),
        vias=(via("v1", "GND", 8, 9),),
        rules=(clearance(0.15),),
    )
    spec = dataclasses.replace(board.spec(), cutouts=(rect(4, 6, 6, 11),) if cutout else ())
    data = pcbdoc.write_pcbdoc_result(spec, filename="pour.PcbDoc", pour="computed", pour_regions=False)
    result = pour_reading(read_pour(data.data))
    copper = _of(result, "GND")
    assert _covered(copper, at(-1, 9))
    assert _covered(copper, at(0.05, 9))
    assert _covered(copper, at(5, 8)) is not cutout
    assert _covered(copper, at(6.05, 8)) is not cutout
    assert _covered(copper, at(6.25, 8))


def test_no_net_copper_border_still_keeps_generic_clearance() -> None:
    """A copper track on the board outline keeps its ordinary clearance, independently of that outline."""
    settings = ZoneSettings(island_removal="never")
    board = Board(
        zones=(zone("z1", "GND", rect(-2, 4, 12, 14), settings=settings),),
        vias=(via("v1", "GND", 8, 9),),
        tracks=(track("border", None, (0, 0), (0, 30), width=0.2),),
        rules=(clearance(0.3),),
    )
    _, result = board.pour()
    copper = _of(result, "GND")
    assert not _covered(copper, at(0.2, 9))
    assert _covered(copper, at(0.5, 9))
    assert _covered(copper, at(-1, 9))


@pytest.mark.parametrize("restrictions", [None, 0, 4])
def test_keepout_layer_strokes_restrict_copper_on_every_layer(restrictions: int | None) -> None:
    """A free Keep-Out track and arc affect all copper layers with the pour bit or in the legacy form."""
    layer = "Altium.KeepOut"
    line = Graphic(id="kl", kind="line", layer=layer, points=(at(0, 0), at(0, 30)), width=mm(0.2))
    arc = Graphic(id="ka", kind="arc", layer=layer, points=(at(4, 5), at(5, 9), at(4, 13)), width=mm(0.2))
    shape = rect(-2, 4, 12, 14)
    board = Board(
        zones=(zone("z1", "GND", shape), zone("z2", "GND", shape, layer="B.Cu")),
        vias=(via("v1", "GND", 8, 9),),
        rules=(clearance(0.15),),
    )
    spec = dataclasses.replace(
        board.spec(),
        graphics=(line, arc),
        keepout_strokes={} if restrictions is None else {line.id: restrictions, arc.id: restrictions},
        layer_ids={layer: pcbrecords.KEEPOUT_LAYER},
    )
    data = pcbdoc.write_pcbdoc_result(spec, filename="pour.PcbDoc", pour="computed", pour_regions=False)
    result = pour_reading(read_pour(data.data))
    for side in ("F.Cu", "B.Cu"):
        copper = _of(result, "GND", layer=side)
        assert _covered(copper, at(-1, 9)) is (restrictions == 0)
        assert _covered(copper, at(0.1, 9)) is (restrictions == 0)
        assert _covered(copper, at(5.1, 9)) is (restrictions == 0)
        assert _covered(copper, at(6, 9))


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


@pytest.mark.parametrize(("restrictions", "pours_inside"), [(0, True), (24, True), (4, False)])
def test_a_keepout_fill_applies_only_its_pour_restriction(restrictions: int, pours_inside: bool) -> None:
    """A keep-out fill is a rule area. Only its copper-pour bit can remove copper (S-1711)."""
    graphic = Graphic(id="k1", kind="rect", layer="F.Cu", points=(at(10, 10), at(14, 14)), filled=True)
    board = Board(
        zones=(zone("z1", "GND"),),
        vias=(via("v1", "GND", 30, 20),),
        rules=(clearance(0.2),),
    )
    spec = dataclasses.replace(board.spec(), graphics=(graphic,), keepout_strokes={graphic.id: restrictions})
    written = pcbdoc.write_pcbdoc_result(
        spec, filename="keepout-fill.PcbDoc", pour="computed", pour_regions=False
    )
    reading = read_pour(written.data)
    (fill,) = reading.document.fills
    assert isinstance(fill, FillRecord) and is_keepout(fill) and record_restrictions(fill) == restrictions
    gnd = _of(pour_reading(reading), "GND")
    assert _covered(gnd, at(12, 12)) is pours_inside
    assert _covered(gnd, at(14.1, 12)) is pours_inside
    assert _covered(gnd, at(14.5, 12))


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


@pytest.mark.parametrize(
    ("peer_x", "lateral", "neck", "east_spoke"),
    (
        (None, False, True, True),
        (21.75, False, True, False),
        (22.5, False, True, True),
        (20.0, True, True, True),
        (21.75, False, False, True),
    ),
)
def test_solid_smd_relief_avoids_the_gap_of_a_facing_smd_pad(
    peer_x: float | None, lateral: bool, neck: bool, east_spoke: bool
) -> None:
    """A forward peer gap can suppress a conductor when neck removal narrows its receiver."""
    pads = [pad("main", "GND", 20, 15, size=(1.72, 0.48))]
    if lateral:
        pads.append(pad("peer", "GND", 20, 15.54, size=(1.2, 0.42)))
    elif peer_x is not None:
        pads.append(pad("peer", "GND", peer_x, 14.64, shape="circle", size=(0.51, 0.51)))
    settings = ZoneSettings(thermal_gap=mm(0.3), thermal_spoke_width=mm(0.2), min_thickness=mm(0.15))
    board = Board(
        zones=(zone("z1", "GND", settings=settings),),
        pads=tuple(pads),
        tracks=(
            track("trunk", "GND", (20, 15), (21.15, 15), 0.2),
            track("up", "GND", (21.15, 15), (21.15, 15.6), 0.2),
            track("down", "GND", (21.15, 15), (21.15, 14.64), 0.2),
        ),
        rules=(clearance(0.3),),
    )
    reading = board.base()
    if not neck:
        reading = _with_record(reading, REMOVENECKS="FALSE")
    poured = _of(pour_reading(reading), "GND")
    assert _covered(poured, at(21, 15)) is east_spoke
    assert _covered(poured, at(19, 15))


@pytest.mark.parametrize("rotation", (0, 90_000_000))
def test_solid_angled_relief_starts_at_the_end_of_a_plated_capsule(rotation: int) -> None:
    """The plated capsule reaches toward each spoke from its own end (S-2308)."""
    slot = pad("slot", "GND", 10, 15, shape="oval", size=(1.6, 0.8), kind="thru_hole", drill=0.4,
               rotation=rotation)  # fmt: skip
    slot = dataclasses.replace(
        slot,
        pad=dataclasses.replace(
            slot.pad,
            padstack=Padstack(id="slot-stack", hole_shape="slot", hole_length=mm(1.2)),
        ),
    )
    control = pad("round-hole", "GND", 30, 15, shape="oval", size=(1.6, 0.8), kind="thru_hole", drill=0.4)
    settings = ZoneSettings(thermal_gap=mm(0.3), thermal_spoke_width=mm(0.3))
    reading = Board(
        zones=(zone("z", "GND", settings=settings),), pads=(slot, control), rules=(clearance(0.3),)
    ).base()
    rules = tuple(
        dataclasses.replace(
            rule,
            record=dataclasses.replace(
                rule.record,
                fields=tuple(
                    (key, "45 Angle" if key.endswith("POLYGONRELIEFANGLE") else value)
                    for key, value in rule.record.fields
                ),
            ),
        )
        for rule in reading.document.rules
    )
    reading = dataclasses.replace(reading, document=dataclasses.replace(reading.document, rules=rules))
    gnd = _of(pour_reading(reading), "GND")
    x, y = (0.82, 0.42) if rotation == 0 else (0.42, 0.82)
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        assert _covered(gnd, at(10 + sx * x, 15 + sy * y))
    assert not _covered(gnd, at(10.18, 15.18))
    assert _covered(gnd, at(30.82, 15.42))  # the same copper shape around a round hole uses its end
    assert not _covered(gnd, at(30.18, 15.18))


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


def test_a_short_neck_between_round_clearance_rims_is_cut_by_chords() -> None:
    """The two narrow copper lobes beside the severed kit P3 neck are removed, and the wider neck stays."""
    board = Board(
        zones=(zone("z1", "GND", rect(1, 1.5, 39, 28.5)),),
        tracks=(
            track("a", "VIN", (16, 1), (16, 6), width=0.3),
            track("b", "VIN", (16, 6.8143), (16, 12), width=0.3),
            track("c", "VIN", (16, 12.8397), (16, 29), width=0.3),
        ),
        vias=(via("v1", "GND", 30, 25),),
        rules=(clearance(0.2),),
    )
    reading = _with_record(board.base(), ARCRESOLUTION="0.125mil")
    gnd = _of(pour_reading(reading), "GND")
    assert not _covered(gnd, at(15.952, 6.40715))
    assert not _covered(gnd, at(16.048, 6.40715))
    assert _covered(gnd, at(16, 12.41985))


@pytest.mark.parametrize(
    ("angle", "rotation", "chord_reach"),
    [(30, 17, 245_346), (45, 0, 165_935), (45, 17, 165_935),
     (60, 17, 127_001), (75, 0, 104_312), (85, 17, 93_993)],
)  # fmt: skip
def test_an_acute_corner_chord_meets_both_long_sides(angle: int, rotation: int, chord_reach: int) -> None:
    """S-2322 measures the same length to the native chord on each of two straight sides."""
    apex = at(10, 10)

    def offset(length: int, degrees: int) -> Point:
        return rotate_point(Point(length, 0), (degrees + rotation) * 1_000_000)

    def translated(*points: Point) -> Point:
        return Point(apex.x + sum(p.x for p in points), apex.y + sum(p.y for p in points))

    ray_a = offset(3_500_000, 180)
    ray_b = offset(3_500_000, 180 - angle)
    back = offset(1_000_000, 180 - angle // 2)
    outline = (
        translated(ray_a), apex, translated(ray_b), translated(ray_b, back), translated(ray_a, back),
    )  # fmt: skip
    anchor = translated(offset(2_600_000, 180 - angle // 2))
    settings = ZoneSettings(connection="solid", min_thickness=127_000)
    board = Board(
        zones=(zone("z1", "GND", outline, settings=settings),),
        vias=(via("v1", "GND", anchor.x / 1_000_000, anchor.y / 1_000_000),),
        rules=(clearance(0.1524),),
    )
    _, result = board.pour()
    copper = _of(result, "GND")
    inset = offset(1_000, 180 - angle // 2)
    for ray in (180, 180 - angle):
        assert not _covered(copper, translated(offset(chord_reach - 5_000, ray), inset))
        assert _covered(copper, translated(offset(chord_reach + 5_000, ray), inset))


def test_an_acute_corner_cut_cannot_cross_a_void(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.altium import pour
    from fenolite.geometry.boolean.clipper import ClipperBackend

    apex = Point(0, 0)
    side_a, side_b = Point(3_500_000, 0), Point(3_500_000, 3_500_000)
    hole = (Point(80_000, 10_000), Point(80_000, 65_000), Point(220_000, 65_000), Point(220_000, 10_000))
    copper = Polygon((apex, side_a, Point(4_000_000, 500_000), side_b), (hole,))
    geometry = pour._Geometry(ClipperBackend())  # pyright: ignore[reportPrivateUsage]
    chord = pour._acute_chord  # pyright: ignore[reportPrivateUsage]
    candidate = chord(apex, side_b, side_a, 153_303)
    assert candidate is not None and geometry.minus((candidate,), (copper,))

    checked: list[Point] = []

    def without_target(point: Point, before: Point, after: Point, reach: int) -> Polygon | None:
        checked.append(point)
        return None if point == apex else chord(point, before, after, reach)

    opened = geometry.open((copper,), 127_000, ARC // 4)
    monkeypatch.setattr(pour, "_acute_chord", without_target)
    assert opened == geometry.open((copper,), 127_000, ARC // 4)
    assert apex in checked


def test_neck_removal_preserves_rotated_right_angle_corners() -> None:
    from fenolite.backends.altium.pour import _Geometry  # pyright: ignore[reportPrivateUsage]
    from fenolite.geometry.boolean.clipper import ClipperBackend

    radius = 2_540_000
    diamond = Polygon((Point(0, -radius), Point(radius, 0), Point(0, radius), Point(-radius, 0)))
    geometry = _Geometry(ClipperBackend())
    (copper,) = geometry.open((diamond,), 127_000, ARC // 4)
    assert all(copper.locate(apex) is Location.BOUNDARY for apex in diamond.outer)


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


def test_a_dense_neck_cut_retries_with_smaller_exact_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.altium.pour import _certified_neck_cut  # pyright: ignore[reportPrivateUsage]
    from fenolite.geometry.boolean import _exact_noding
    from fenolite.geometry.boolean._exact_cut import exact_difference
    from fenolite.geometry.boolean._exact_noding import Budget, Limits
    from fenolite.geometry.errors import GeometryError

    def rectangle(x0: int, y0: int, x1: int, y1: int) -> Polygon:
        return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))

    subject = (rectangle(0, 0, 100_000, 25_000),)
    cut = tuple(rectangle(x, 7_000, x + 5_000, 18_000) for x in range(10_000, 90_000, 10_000))
    expected = exact_difference(subject, cut, Budget()).polygons
    limits = Limits(input_edges=72, comparisons=75)
    with pytest.raises(GeometryError, match="index-comparison budget exceeded"):
        exact_difference(subject, cut, Budget(limits))
    budget = Budget(limits)
    monkeypatch.setattr(_exact_noding, "Budget", lambda: budget)
    assert _certified_neck_cut(subject, cut, 1) == expected
    assert budget.work > limits.comparisons


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


@pytest.mark.parametrize(
    ("large", "cutoff", "kept"), [(False, False, True), (False, True, False), (True, True, True)]
)
def test_solid_area_cutoff_precedes_thermal_spokes(large: bool, cutoff: bool, kept: bool) -> None:
    """A sub-threshold receiver stays removed even if its thermal spoke could attach it (S-2321)."""
    x, y = 20.0, 15.0
    half_height, end = (1.45, 2.50) if large else (0.58, 1.50)
    outline = tuple(
        at(x + dx, y + dy)
        for dx, dy in (
            (-3, -2), (-0.8, -2), (-0.8, -0.3), (0.75, -0.3), (0.75, -half_height),
            (end, -half_height), (end, half_height), (0.75, half_height), (0.75, 0.3),
            (-0.8, 0.3), (-0.8, 2), (-3, 2),
        )
    )  # fmt: skip
    settings = ZoneSettings(
        thermal_gap=mm(0.254),
        thermal_spoke_width=mm(0.508),
        min_thickness=mm(0.127),
        island_removal="below_area" if cutoff else "never",
        min_island_area=1_600_000_000_000,
    )
    board = Board(
        zones=(zone("z1", "GND", outline, settings=settings),),
        pads=(pad("p1", "GND", x, y, size=(0.8, 1.0)),),
        rules=(clearance(0.1524),),
    )
    reading = _with_record(board.base(), REMOVEDEAD="FALSE")
    gnd = _of(pour_reading(reading), "GND")
    assert _covered(gnd, at(x - 2, y))
    assert _covered(gnd, at(x + 0.5, y)) is kept
    assert _covered(gnd, at(x + 1.2, y)) is kept
    written = pcbdoc.write_pcbdoc_result(board.spec(), filename="thermal-island.PcbDoc", pour="computed")
    assert written.pour is not None and not written.pour.refused


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
