# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The written form of a computed pour (change c0215; capability altium-pcb-writer, "Poured regions";
``docs/formats/altium/pcb-pour.md``, "Saved poured regions" and "Fenolite's choices")."""

from __future__ import annotations

import importlib.util

import pytest
from _altium_pour import FILENAME, Board, clearance, pad, rect, via, zone

from fenolite.analysis.fills import unfracture
from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pour import area, pour_reading, read_pour
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
BOARD = Board(
    zones=(zone("z1", "GND"),),
    pads=(pad("p1", "VIN", 10, 10, shape="circle", size=(1, 1)),),
    vias=(via("v1", "GND", 30, 20),),
    rules=(clearance(0.3),),
)


def test_polygon_region_record() -> None:
    """``pcbrecords.polygon_region``: the keys of a saved poured region, no net, the polygon's index, the
    piece's number, the holes after the outline in both forms."""
    outer = [(0, 0), (0, 1000), (1000, 1000), (1000, 0)]  # clockwise in the file's frame
    hole = [(200, 200), (800, 200), (800, 800), (200, 800)]  # anticlockwise
    plain = rec.polygon_region(1, outer, [hole], polygon=3, piece=2, arc_resolution="0.5mil")
    shape = rec.polygon_region(
        1, outer, [hole], polygon=3, piece=2, arc_resolution="0.5mil", shape_based=True
    )
    for data in (plain, shape):
        assert data[0] == 11  # a region
    keys = (
        "V7_LAYER=TOP|NAME= |KIND=0|SUBPOLYINDEX=2|UNIONINDEX=0|ARCRESOLUTION=0.5mil|ISSHAPEBASED=FALSE|"
        "CAVITYHEIGHT=0mil"
    )
    assert keys.encode("ascii") in plain and keys.encode("ascii") in shape
    with pytest.raises(ValueError):
        rec.polygon_region(1, outer[:2], [], polygon=0, piece=0, arc_resolution="0.5mil")


def test_a_piece_with_a_hole_read_back() -> None:
    """Scenario "A piece with a hole read back"."""
    base = BOARD.base()
    (pour,) = pour_reading(base).polygons
    (piece,) = pour.pieces
    data = pcbdoc.write_pcbdoc(BOARD.spec(), filename=FILENAME, pour="computed")
    document = read_pcbdoc(data)
    regions = [r for r in document.regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None]
    twins = [
        r for r in document.shape_regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None
    ]
    assert len(regions) == len(twins) == 1
    (region,) = regions
    assert region.prefix.polygon == 0 and region.prefix.net is None and region.prefix.component is None
    assert region.hole_count == 1 and twins[0].hole_count == 1
    assert dict(region.properties.fields)["SUBPOLYINDEX"] == "0"
    reading = read_pour(data, file=FILENAME)
    board = reading.design.board
    assert board is not None
    (filled,) = [z for z in board.zones if z.fills]
    (fill,) = filled.fills
    found = unfracture(fill.polygon)
    assert found is not None and len(found[1]) == 1
    back = Polygon(found[0], found[1])
    clipper = ClipperBackend()
    difference = sum(area(p) for p in clipper.xor([back], [piece]))
    perimeter = sum(
        abs(a.x - b.x) + abs(a.y - b.y)
        for ring in piece.rings()
        for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
    )
    assert difference <= 2 * perimeter  # within one unit (2.54 nm) of the written piece everywhere


def test_regions_come_after_every_other_region() -> None:
    """``pcb-pour.md``, "Fenolite's choices": the poured regions follow the regions of the keep-outs and the
    graphics, which keep their positions."""
    from fenolite.model.board import Keepout

    keepout = Keepout(id="k1", outline=rect(3, 3, 5, 5), layers=("F.Cu",), no_tracks=True)
    board = Board(zones=BOARD.zones, pads=BOARD.pads, vias=BOARD.vias, keepouts=(keepout,), rules=BOARD.rules)
    computed = read_pcbdoc(pcbdoc.write_pcbdoc(board.spec(), filename=FILENAME, pour="computed")).regions
    outline = read_pcbdoc(pcbdoc.write_pcbdoc(board.spec(), filename=FILENAME)).regions
    assert [r.raw for r in computed[: len(outline)]] == [r.raw for r in outline]
    assert all(isinstance(r, RegionRecord) and r.prefix.polygon is not None for r in computed[len(outline) :])
