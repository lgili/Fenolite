# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed extents and copper polygons (capability board-frame: "Placed extents", "Copper polygons"; change
c0028). Hermetic."""

from __future__ import annotations

import dataclasses
import random

import pytest
from _placed import DEG, Part, definition, design_of, mm, pt

from fenolite.backends.base import PadCopper
from fenolite.backends.kicad.frame import copper_polygon, find_pads, placed_extent, placed_extents
from fenolite.backends.kicad.slots import from_ext, to_ext
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.geometry import DEFAULT_TOL, Location, Polygon, convex_hull
from fenolite.model.base import Opaque
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design

SQUARE = (pt(9.25, 18.5), pt(10.75, 18.5), pt(10.75, 21.5), pt(9.25, 21.5))


def _footprint(design: Design, index: int = 0) -> FootprintInstance:
    assert design.board is not None
    return design.board.footprints[index]


def _with_children(footprint: FootprintInstance, *fragments: str) -> FootprintInstance:
    """``footprint`` with its courtyard children replaced by ``fragments``."""
    slots = [
        s for s in from_ext(footprint.ext["kicad"]) if not (isinstance(s, Opaque) and "CrtYd" in s.fragment)
    ]
    slots += [Opaque(fragment, "20241229") for fragment in fragments]
    return dataclasses.replace(footprint, ext={**footprint.ext, "kicad": to_ext(slots)})


@pytest.mark.parametrize("rotation", [90, 270])
def test_rotated_courtyard(rotation: int) -> None:
    extent = placed_extent(_footprint(design_of(Part("R1", "Mini_R_0603", 10, 20, rotation))))
    assert extent.front == (SQUARE,) and extent.back == ()
    assert extent.source == "courtyard" and extent.exact and extent.own == extent.front


def test_bottom_courtyard_is_mirrored() -> None:
    design = design_of(Part("P1", "Frame_Shapes", 50, 50, 0, "bottom", library="Frame"))
    extent = placed_extent(_footprint(design))
    assert extent.back == ((pt(47, 46), pt(53, 46), pt(53, 52), pt(47, 52)),)
    assert extent.front == () and extent.own == extent.back and extent.side == "bottom"


def test_definition_for_an_instance_without_slots() -> None:
    bare = FootprintInstance(
        id="fp_00000000-0000-4000-8000-000000000001",
        component_id="cmp_00000000-0000-4000-8000-000000000001",
        lib_ref="Frame:Frame_Shapes",
        position=pt(50, 50),
        side="bottom",
    )
    extent = placed_extent(bare, definition=definition("Frame_Shapes", "Frame"))
    assert extent.back == ((pt(47, 46), pt(53, 46), pt(53, 52), pt(47, 52)),)
    assert extent.front == () and extent.source == "definition"
    top = placed_extent(dataclasses.replace(bare, side="top"), definition=definition("Frame_Shapes", "Frame"))
    assert top.front == ((pt(47, 48), pt(53, 48), pt(53, 54), pt(47, 54)),) and top.back == ()
    turned = dataclasses.replace(bare, side="top", rotation=90 * DEG)
    quarter = placed_extent(turned, definition=definition("Frame_Shapes", "Frame"))
    assert quarter.front == ((pt(48, 47), pt(54, 47), pt(54, 53), pt(48, 53)),)


def test_circle_courtyard() -> None:
    design = design_of(Part("P1", "Frame_Round", 20, 20, library="Frame"))
    extent = placed_extent(_footprint(design))
    (ring,) = extent.front
    assert extent.exact is False and extent.source == "courtyard"
    centre, radius = pt(20, 20), mm(2)
    for vertex in ring:
        distance2 = (vertex.x - centre.x) ** 2 + (vertex.y - centre.y) ** 2
        assert (radius + DEFAULT_TOL) ** 2 <= distance2 <= (radius + DEFAULT_TOL + 2) ** 2
    polygon = Polygon(ring)
    rng = random.Random(28)
    checked = 0
    while checked < 500:
        point = Point(centre.x + rng.randint(-radius, radius), centre.y + rng.randint(-radius, radius))
        if (point.x - centre.x) ** 2 + (point.y - centre.y) ** 2 <= radius**2:
            assert polygon.locate(point) in (Location.INSIDE, Location.BOUNDARY)
            checked += 1


def test_line_loop_and_arc_courtyard() -> None:
    footprint = _footprint(design_of(Part("P1", "Frame_OpenCourtyard", 10, 10, library="Frame")))
    closed = _with_children(
        footprint,
        *(
            f'(fp_line (start {a}) (end {b}) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))'
            for a, b in (("-2 -2", "2 -2"), ("2 -2", "2 2"), ("2 2", "-2 2"), ("-2 2", "-2 -2"))
        ),
    )
    extent = placed_extent(closed)
    assert extent.front == ((pt(8, 8), pt(12, 8), pt(12, 12), pt(8, 12)),) and extent.exact
    rounded = _with_children(
        footprint,
        '(fp_line (start -2 0) (end 2 0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))',
        '(fp_arc (start 2 0) (mid 0 2) (end -2 0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))',
    )
    half = placed_extent(rounded)
    assert half.exact is False and len(half.front) == 1 and len(half.front[0]) > 4
    assert pt(8, 10) in half.front[0] and pt(12, 10) in half.front[0]


def test_polygon_courtyard_with_an_arc_in_pts() -> None:
    footprint = _footprint(design_of(Part("P1", "Frame_OpenCourtyard", 0, 0, library="Frame")))
    poly = _with_children(
        footprint,
        "(fp_poly (pts (xy -2 0) (arc (start -2 0) (mid 0 -2) (end 2 0)) (xy 2 2) (xy -2 2))"
        ' (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))',
    )
    extent = placed_extent(poly)
    (ring,) = extent.front
    assert extent.exact is False and pt(2, 2) in ring and pt(-2, 2) in ring and len(ring) > 5
    assert Polygon(ring).locate(pt(0, -1.9)) is Location.INSIDE


def test_no_courtyard_uses_the_pad_hull() -> None:
    design = design_of(Part("P1", "Frame_NoCourtyard", 0, 0, library="Frame"))
    found: list[Issue] = []
    extent = placed_extent(_footprint(design), issues=found)
    assert extent.source == "pads" and extent.exact is False
    assert (
        extent.front == ((pt(-2.5, -0.5), pt(2.5, -0.5), pt(2.5, 0.5), pt(-2.5, 0.5)),) and extent.back == ()
    )
    assert [(i.code, i.severity) for i in found] == [("kicad.frame.no-courtyard", "info")]
    bottom = placed_extent(
        _footprint(design_of(Part("P1", "Frame_NoCourtyard", 0, 0, 0, "bottom", library="Frame")))
    )
    assert bottom.front == () and len(bottom.back) == 1 and bottom.own == bottom.back


def test_no_courtyard_and_no_copper_is_empty() -> None:
    footprint = _footprint(design_of(Part("P1", "Frame_NoCourtyard", 0, 0, library="Frame")))
    found: list[Issue] = []
    extent = placed_extent(dataclasses.replace(footprint, pads=()), issues=found)
    assert (extent.source, extent.front, extent.back, extent.exact) == ("none", (), (), True)
    assert [i.code for i in found] == ["kicad.frame.no-courtyard"]


def test_open_courtyard_is_its_hull() -> None:
    design = design_of(Part("P1", "Frame_OpenCourtyard", 0, 0, library="Frame"))
    found: list[Issue] = []
    extent = placed_extent(_footprint(design), issues=found)
    ends = [pt(-2, -2), pt(2, -2), pt(2, -2), pt(2, 2), pt(2, 2), pt(-2, 2)]
    assert extent.front == (convex_hull(ends),) and extent.exact is False and extent.source == "courtyard"
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.frame.courtyard-malformed", "warning")
    assert "Frame_OpenCourtyard" in issue.message and "F.CrtYd" in issue.message


def test_placed_extents_in_board_order() -> None:
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 20, 90),
        Part("P1", "Frame_NoCourtyard", 0, 0, library="Frame"),
        Part("U1", "Mini_QFP-32_7x7mm_P0.8mm", 50, 50, 0, "bottom"),
    )
    found: list[Issue] = []
    extents = placed_extents(design, issues=found)
    assert [e.footprint_id for e in extents] == [fp.id for fp in design.board.footprints]  # type: ignore[union-attr]
    assert [e.source for e in extents] == ["courtyard", "pads", "courtyard"]
    assert extents[0].front == (SQUARE,) and extents[2].front == () and len(extents[2].back) == 1
    assert [i.code for i in found] == ["kicad.frame.no-courtyard"]
    assert placed_extents(design) == extents  # pure


# -- polygons


def test_rounded_and_square_entries() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 20), Part("D1", "Mini_LED_THT_3mm", 30, 20))
    rounded = find_pads(design, "R1", 1)[0].copper[0]
    polygon = copper_polygon(rounded)
    half = mm(0.225)
    x0, y0, x1, y1 = mm(8.975), mm(19.75), mm(9.425), mm(20.25)
    rng = random.Random(28)
    checked = 0
    while checked < 500:
        point = Point(rng.randint(x0 - half, x1 + half), rng.randint(y0 - half, y1 + half))
        dx, dy = max(x0 - point.x, 0, point.x - x1), max(y0 - point.y, 0, point.y - y1)
        if dx * dx + dy * dy <= half * half:
            assert polygon.locate(point) in (Location.INSIDE, Location.BOUNDARY)
            checked += 1
    for vertex in polygon.outer:
        dx, dy = max(x0 - vertex.x, 0, vertex.x - x1), max(y0 - vertex.y, 0, vertex.y - y1)
        assert dx * dx + dy * dy <= (half + DEFAULT_TOL + 2) ** 2
    square = find_pads(design, "D1", 1)[0].copper[0]
    assert copper_polygon(square) == Polygon(square.core)


def test_disc_and_segment_polygons() -> None:
    disc = copper_polygon(PadCopper("F.Cu", (pt(0, 0),), mm(1)))
    assert all(mm(0.5) ** 2 <= v.x**2 + v.y**2 <= (mm(0.5) + DEFAULT_TOL + 2) ** 2 for v in disc.outer)
    stadium = copper_polygon(PadCopper("F.Cu", (pt(0, 0), pt(2, 0)), mm(1)))
    assert stadium.locate(pt(-0.49, 0)) is Location.INSIDE and stadium.locate(pt(1, 0.49)) is Location.INSIDE
    assert stadium.locate(pt(-0.6, 0)) is Location.OUTSIDE and stadium.is_convex()


def test_entries_without_a_convex_outer_polygon_are_refused() -> None:
    notch = (pt(0, 0), pt(4, 0), pt(4, 4), pt(2, 1), pt(0, 4))
    for entry, word in (
        (PadCopper("F.Cu", (pt(0, 0), pt(1, 0), pt(1, 1)), mm(0.1)), "polyline"),
        (PadCopper("F.Cu", notch, mm(0.1), filled=True), "non-convex"),
        (PadCopper("F.Cu", (pt(0, 0), pt(1, 0)), 0), "width 0"),
    ):
        with pytest.raises(ValueError, match=word):
            copper_polygon(entry)
    assert copper_polygon(PadCopper("F.Cu", notch, 0, filled=True)) == Polygon(notch)
