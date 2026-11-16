# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A footprint imported from Altium gets a derived courtyard (change c0489; capability altium-import,
"Derived courtyard of an imported footprint"). The documents are records authored here
(``tests/_altium_records.py``): two pads 2 mm apart and, for some, an extruded body of 6 mm by 3 mm."""

from __future__ import annotations

import math

import _altium_records as rec

from fenolite.backends.altium import frame
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.courtyard import (
    DERIVED_COURTYARD_MARGIN,
    HYPOTHESIS,
    grown_hull,
    pad_corners,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.board import FootprintInstance, Graphic
from fenolite.model.design import Design
from fenolite.placement import legality

MM_MIL = 1 / 0.0254  # mil per mm
PAD = (40 * rec.MIL, 40 * rec.MIL)


def _document(*xs_mm: float, body: bool = True) -> Design:
    """One footprint per entry of ``xs_mm`` at that x (mm), two pads at ±1 mm, and with ``body`` a 6 mm by
    3 mm body around them."""
    components, pads, bodies = [], [], b""
    for index, x in enumerate(xs_mm):
        cx, cy = 2000 + x * MM_MIL, 1500.0
        components.append(rec.component(f"R{index + 1}", x=f"{cx}mil", y=f"{cy}mil"))
        for name, dx in (("1", -1.0), ("2", 1.0)):
            at = (round((cx + dx * MM_MIL) * rec.MIL), round(cy * rec.MIL))
            pads.append(rec.pad(name, at, size=PAD, component=index))
        if body:
            w, h = 3 * MM_MIL, 1.5 * MM_MIL
            box = ((cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h))
            bodies += rec.body_bytes(box, component=index)
    storages = {"ComponentBodies6": {"Data": bodies}} if bodies else None
    return import_board(
        rec.document(components=components, pads=pads, storages=storages),
        file="authored.PcbDoc",
        sha256=rec.SHA,
    )


def _courtyard(fp: FootprintInstance) -> Graphic:
    (found,) = [g for g in fp.graphics if g.layer.endswith("CrtYd")]
    return found


def _inside(point: tuple[float, float], ring: tuple[Point, ...]) -> bool:
    signs = {
        math.copysign(1, (b.x - a.x) * (point[1] - a.y) - (b.y - a.y) * (point[0] - a.x))
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True)
        if (b.x - a.x) * (point[1] - a.y) - (b.y - a.y) * (point[0] - a.x) != 0
    }
    return len(signs) <= 1


def _holds_grown(ring: tuple[Point, ...], points: list[Point], margin: int) -> bool:
    return all(
        _inside((p.x + margin * math.cos(k * math.pi / 16), p.y + margin * math.sin(k * math.pi / 16)), ring)
        for p in points
        for k in range(32)
    )


def test_body_larger_than_the_pads() -> None:
    """Scenario "Body larger than the pads"."""
    design = _document(0.0)
    assert design.board is not None
    (fp,) = design.board.footprints
    courtyard = _courtyard(fp)
    assert courtyard.layer == "F.CrtYd" and courtyard.kind == "polygon"
    assert ("derived", "courtyard") in courtyard.ext["altium"].payload
    assert courtyard.provenance is not None
    assert courtyard.provenance.evidence.level is Level.INFERRED
    assert courtyard.provenance.evidence.hypotheses == (HYPOTHESIS,)
    (body,) = fp.bodies
    assert _holds_grown(courtyard.points, list(body.outline), max(DERIVED_COURTYARD_MARGIN - 1, 0))
    xs = [p.x for p in courtyard.points]
    assert max(xs) - min(xs) == 6_000_000 + 2 * DERIVED_COURTYARD_MARGIN  # within 1 nm of the mil body
    (extent,) = frame.placed_extents(design)
    assert extent.source == "derived" and not extent.exact and len(extent.front) == 1


def test_a_footprint_without_a_body() -> None:
    """Scenario "A footprint without a body": the hull of the pads' copper grown by the margin."""
    design = _document(0.0, body=False)
    assert design.board is not None
    (fp,) = design.board.footprints
    assert fp.bodies == ()
    assert _courtyard(fp).points == grown_hull(pad_corners(fp.pads))
    xs, ys = [p.x for p in _courtyard(fp).points], [p.y for p in _courtyard(fp).points]
    # two 40 mil square pads 2 mm apart: 2 mm + 1.016 mm across, 1.016 mm high, each grown by the margin
    grow = 2 * DERIVED_COURTYARD_MARGIN
    assert abs(max(xs) - min(xs) - 3_016_000 - grow) <= 2 and abs(max(ys) - min(ys) - 1_016_000 - grow) <= 2
    assert _holds_grown(_courtyard(fp).points, pad_corners(fp.pads), max(DERIVED_COURTYARD_MARGIN - 1, 0))


def test_ids_are_stable_and_a_courtyard_is_not_derived_twice() -> None:
    first, second = _document(0.0), _document(0.0)
    assert first.board is not None and second.board is not None
    assert _courtyard(first.board.footprints[0]).id == _courtyard(second.board.footprints[0]).id
    assert not [i for i in first.validate() if i.severity == "error"]


def test_two_bodies_that_overlap() -> None:
    """Scenario "Two bodies that overlap": bodies 6 mm wide 5 mm apart overlap by 1 mm; the pads, 3 mm
    apart, do not touch. Legality reports the overlap of the derived courtyards, as approximate."""
    design = _document(0.0, 5.0)
    assert design.board is not None
    extents = frame.placed_extents(design)
    assert [e.source for e in extents] == ["derived", "derived"]
    names = {fp.id: f"R{i + 1}" for i, fp in enumerate(design.board.footprints)}
    issues = legality.check(extents, (), names=names)
    (overlap,) = [i for i in issues if i.code == "place.courtyard-overlap"]
    assert overlap.message.endswith(legality.APPROXIMATE)
    # without the bodies, only the pads' hulls: no overlap
    bare = _document(0.0, 5.0, body=False)
    assert not [
        i for i in legality.check(frame.placed_extents(bare), (), names=names) if i.code.endswith("overlap")
    ]


Box = tuple[tuple[float, float, float, float], float]


def _board(*parts: tuple[list[tuple[float, float]], list[Box]]) -> Design:
    """One footprint per part: its pads (centres in mm, ``PAD`` square) and its bodies (a box ``x0, y0,
    x1, y1`` in mm and a standoff in mil), all in board millimetres from (2000, 1500) mil."""
    components, pads, bodies = [], [], b""
    for index, (centres, boxes) in enumerate(parts):
        components.append(rec.component(f"U{index + 1}", x="2000mil", y="1500mil"))
        for number, (x, y) in enumerate(centres, 1):
            at = (round((2000 + x * MM_MIL) * rec.MIL), round((1500 + y * MM_MIL) * rec.MIL))
            pads.append(rec.pad(str(number), at, size=PAD, component=index))
        for (x0, y0, x1, y1), standoff in boxes:
            corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
            box = [(2000 + x * MM_MIL, 1500 + y * MM_MIL) for x, y in corners]
            fields = {"STANDOFFHEIGHT": f"{standoff}mil", "OVERALLHEIGHT": f"{standoff + 40}mil"}
            bodies += rec.body_bytes(box, component=index, fields=fields)
    storages = {"ComponentBodies6": {"Data": bodies}} if bodies else None
    return import_board(
        rec.document(components=components, pads=pads, storages=storages),
        file="authored.PcbDoc",
        sha256=rec.SHA,
    )


def _overlaps(design: Design) -> int:
    assert design.board is not None
    names = {fp.id: f"U{i + 1}" for i, fp in enumerate(design.board.footprints)}
    issues = legality.check(frame.placed_extents(design), (), names=names)
    return len([i for i in issues if i.code == "place.courtyard-overlap"])


def test_a_raised_body_over_a_small_part_is_no_overlap() -> None:
    """A 10 mm body 2 mm above the board (pads at its edges) over a small part under it: Altium's Specified
    clearance accepts the overhang, so the raised body is no part of the courtyard (task 3.2)."""
    small = ([(-0.5, 3.0), (0.5, 3.0)], [((-1.0, 2.5, 1.0, 3.5), 0)])
    for standoff, expected in ((80, 0), (0, 1)):
        large = ([(-6.0, 0.0), (6.0, 0.0)], [((-5.0, -5.0, 5.0, 5.0), standoff)])
        assert _overlaps(_board(large, small)) == expected


def test_an_l_shaped_part() -> None:
    """Pads on an L (two along x, one up y): a part 0.3 mm beside its hull is no overlap (the old 0.25 mm
    margin on each side made one), and a part in the notch of the L is, as the convex hull covers it."""
    ell = ([(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)], [])
    beside = ([(-1.32, 2.0), (-1.32, 3.0)], [])  # the pads' right edge 0.3 mm left of the L's left edge
    notch = ([(2.5, 2.5), (3.0, 2.5)], [])
    assert _overlaps(_board(ell, beside)) == 0
    assert _overlaps(_board(ell, notch)) == 1


def test_two_parts_that_really_overlap_are_still_reported() -> None:
    """Two parts whose bodies on the board overlap by 0.5 mm are reported, with the margin of 0."""
    first = ([(-1.0, 0.0), (1.0, 0.0)], [((-2.0, -1.0, 2.0, 1.0), 0)])
    second = ([(2.5, 0.0), (4.5, 0.0)], [((1.5, -1.0, 5.5, 1.0), 0)])
    assert _overlaps(_board(first, second)) == 1
