# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Custom pads and conservative supersets (capability board-frame, "Pad copper entries"; change c0028):
primitives by kind, trapezoids, chamfers, curves and padstack layers with unknown ratios. Hermetic."""

from __future__ import annotations

import dataclasses

from _placed import Part, definition, design_of, mm, pt

from fenolite.backends.base import PadCopper
from fenolite.backends.kicad.frame import CURVE_GROWTH, board_pads, find_pads
from fenolite.backends.kicad.slots import from_ext, to_ext
from fenolite.core.errors import Issue
from fenolite.geometry import DEFAULT_TOL, Location, Polygon
from fenolite.model.base import Opaque
from fenolite.model.board import Pad, Padstack, PadstackLayer, Size
from fenolite.model.design import Design


def _with_pad(design: Design, change: object) -> Design:
    """``design`` with ``change(pad) -> pad`` applied to the first pad of its first footprint."""
    board = design.board
    assert board is not None
    footprint = board.footprints[0]
    pad = change(footprint.pads[0])  # type: ignore[operator]
    footprint = dataclasses.replace(footprint, pads=(pad, *footprint.pads[1:]))
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=(footprint,)))


def _tokens(pad: Pad, *fragments: str, drop: tuple[str, ...] = ()) -> Pad:
    """``pad`` with opaque children appended (and those starting with a ``drop`` head removed)."""
    slots = [
        s
        for s in from_ext(pad.ext["kicad"])
        if not (isinstance(s, Opaque) and s.fragment.startswith(tuple(f"({d}" for d in drop)))
    ]
    slots += [Opaque(fragment, "20241229") for fragment in fragments]
    return dataclasses.replace(pad, ext={**pad.ext, "kicad": to_ext(slots)})


def _custom(*primitives: str, anchor: str = "rect") -> Design:
    """A lone custom pad of 0.4 mm at the origin with the given primitives."""
    design = design_of(Part("P1", "Frame_Shapes", 0, 0, library="Frame"))
    board = design.board
    assert board is not None
    footprint = board.footprints[0]
    pad = next(p for p in footprint.pads if p.number == "5")
    pad = dataclasses.replace(pad, position=pt(0, 0))
    body = " ".join(primitives)
    pad = _tokens(
        pad,
        f"(options (clearance outline) (anchor {anchor}))",
        f"(primitives {body})",
        drop=("options", "primitives"),
    )
    footprint = dataclasses.replace(footprint, pads=(pad,))
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=(footprint,)))


def _entries(design: Design, issues: list[Issue] | None = None) -> tuple[PadCopper, ...]:
    return board_pads(design, issues=issues)[0].copper


def test_bench_custom_pad_is_exact() -> None:
    design = design_of(Part("P1", "Frame_Shapes", 10, 10, library="Frame"))
    anchor, triangle = find_pads(design, "P1", 5)[0].copper
    assert anchor.core == (pt(11.3, 11.8), pt(11.7, 11.8), pt(11.7, 12.2), pt(11.3, 12.2)) and anchor.filled
    assert (
        triangle.core == (pt(11, 11.6), pt(12, 11.6), pt(11.5, 12.5)) and triangle.filled and triangle.exact
    )
    found: list[Issue] = []
    board_pads(design, issues=found)
    assert found == []


def test_trapezoid_flagged_as_a_superset() -> None:
    design = design_of(Part("T1", "Frame_Trapezoid", 0, 0, library="Frame"))
    found: list[Issue] = []
    (entry,) = board_pads(design, issues=found)[0].copper
    assert entry.core == (pt(-0.7, -0.7), pt(0.7, -0.7), pt(0.7, 0.7), pt(-0.7, 0.7))
    assert entry.filled and entry.width == 0 and entry.exact is False
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.frame.shape-approximated", "info")
    assert "T1" in issue.message and "'1'" in issue.message and issue.where == "T1:1"


def test_chamfered_pad_keeps_its_unchamfered_shape() -> None:
    plain = design_of(Part("R1", "Mini_R_0603", 0, 0))
    chamfered = _with_pad(plain, lambda pad: _tokens(pad, "(chamfer_ratio 0.2)", "(chamfer top_left)"))
    found: list[Issue] = []
    (entry,) = _entries(chamfered, found)
    (reference,) = _entries(plain)
    assert (entry.core, entry.width, entry.filled) == (reference.core, reference.width, reference.filled)
    assert (
        reference.exact and not entry.exact and [i.code for i in found] == ["kicad.frame.shape-approximated"]
    )
    # a ratio with an empty corner list chamfers nothing
    unchanged = _with_pad(plain, lambda pad: _tokens(pad, "(chamfer_ratio 0.2)"))
    assert _entries(unchanged)[0].exact


def test_roundrect_ratio_rules() -> None:
    plain = design_of(Part("R1", "Mini_R_0603", 0, 0))

    def ratio(text: str | None) -> PadCopper:
        fragments = () if text is None else (f"(roundrect_rratio {text})",)
        design = _with_pad(plain, lambda pad: _tokens(pad, *fragments, drop=("roundrect_rratio",)))
        return _entries(design)[0]

    assert ratio(None) == ratio("0.25")  # the default when the token is absent
    assert ratio("0.9") == ratio("0.5")  # clamped
    stadium = ratio("0.5")  # 0.9 x 0.95: r = 0.45, the inner box is 0 x 0.05, a vertical segment
    assert stadium.core == (pt(-0.8, -0.025), pt(-0.8, 0.025)) and stadium.width == mm(0.9)
    assert not stadium.filled and stadium.exact
    square = ratio("0")
    assert square.width == 0 and square.filled and len(square.core) == 4
    odd = _with_pad(plain, lambda pad: dataclasses.replace(pad, size=Size(900_001, 900_001)))
    disc = _with_pad(odd, lambda pad: _tokens(pad, "(roundrect_rratio 0.5)", drop=("roundrect_rratio",)))
    (entry,) = _entries(disc)
    assert entry.width == 900_000 and len(entry.core) == 4  # r rounds half to even: the inner box is 1 nm


def test_primitive_kinds() -> None:
    line, rect_filled, rect_open, disc = _entries(
        _custom(
            "(gr_line (start 0 0) (end 1 0) (width 0.2))",
            "(gr_rect (start -1 -1) (end 1 1) (width 0.1) (fill yes))",
            "(gr_rect (start -1 -1) (end 1 1) (width 0.1) (fill no))",
            "(gr_circle (center 0 0) (end 0.5 0) (width 0.1) (fill yes))",
        )
    )[1:]
    assert (line.core, line.width, line.filled) == ((pt(0, 0), pt(1, 0)), mm(0.2), False)
    assert rect_filled.core == (pt(-1, -1), pt(1, -1), pt(1, 1), pt(-1, 1)) and rect_filled.filled
    assert rect_filled.width == mm(0.1)
    assert rect_open.core == (pt(-1, -1), pt(1, -1), pt(1, 1), pt(-1, 1), pt(-1, -1)) and not rect_open.filled
    assert (disc.core, disc.width, disc.exact) == ((pt(0, 0),), mm(1.1), True)


def test_anchor_default_and_polygon_fill_default() -> None:
    entries = _entries(_custom("(gr_poly (pts (xy -1 -1) (xy 1 -1) (xy 0 1)) (width 0))", anchor="circle"))
    assert (entries[0].core, entries[0].width) == ((pt(0, 0),), mm(0.4))
    assert entries[1].filled  # a gr_poly without ``fill`` counts as filled
    open_poly = _entries(_custom("(gr_poly (pts (xy -1 -1) (xy 1 -1) (xy 0 1)) (width 0.1) (fill none))"))[1]
    assert not open_poly.filled and open_poly.core[0] == open_poly.core[-1] and len(open_poly.core) == 4
    design = _custom("(gr_line (start 0 0) (end 1 0) (width 0.2))")
    no_options = _with_pad(design, lambda pad: _tokens(pad, drop=("options",)))
    assert _entries(no_options)[0].filled and len(_entries(no_options)[0].core) == 4  # anchor rect


def test_irrational_circle_radius_is_a_superset() -> None:
    found: list[Issue] = []
    disc = _entries(_custom("(gr_circle (center 0 0) (end 0.3 0.3) (width 0) (fill yes))"), found)[1]
    assert disc.exact is False and disc.width == 2 * 424_265  # the ceiling of 0.3·√2 mm
    assert [i.code for i in found] == ["kicad.frame.shape-approximated"]


def test_curved_primitives_are_supersets() -> None:
    found: list[Issue] = []
    arc, ring, curve, mixed = _entries(
        _custom(
            "(gr_arc (start 1 0) (mid 0 1) (end -1 0) (width 0.1))",
            "(gr_circle (center 0 0) (end 1 0) (width 0.1) (fill no))",
            "(gr_curve (pts (xy 0 0) (xy 1 2) (xy 2 2) (xy 3 0)) (width 0.1))",
            "(gr_poly (pts (xy -1 0) (arc (start -1 0) (mid 0 -1) (end 1 0)) (xy 1 1) (xy -1 1))"
            " (width 0) (fill yes))",
        ),
        found,
    )[1:]
    assert len(found) == 1  # one info per pad, however many supersets it has
    assert arc.width == mm(0.1) + CURVE_GROWTH == mm(0.1) + 2 * DEFAULT_TOL + 2
    assert not arc.filled and arc.core[0] == pt(1, 0) and arc.core[-1] == pt(-1, 0) and len(arc.core) > 2
    for point in arc.core:  # the polyline follows the circle of radius 1 mm within the tolerance
        assert abs(point.x**2 + point.y**2 - mm(1) ** 2) <= 2 * mm(1) * (DEFAULT_TOL + 1)
    assert ring.core[0] == ring.core[-1] and not ring.filled and ring.width == mm(0.1) + CURVE_GROWTH
    assert curve.core == (pt(0, 0), pt(3, 0), pt(2, 2), pt(1, 2)) and curve.filled and curve.width == mm(0.1)
    assert mixed.filled and mixed.width == CURVE_GROWTH and len(mixed.core) > 4
    assert not any(entry.exact for entry in (arc, ring, curve, mixed))
    polygon = Polygon(mixed.core)
    assert (
        polygon.locate(pt(0, -0.9)) is Location.INSIDE and polygon.locate(pt(0.99, -0.99)) is Location.OUTSIDE
    )


def test_unknown_primitives_and_degenerate_shapes_are_left_out() -> None:
    entries = _entries(
        _custom(
            "(gr_bbox (start 0 0) (end 1 1))",
            "(gr_circle (center 0 0) (end 0 0) (width 0) (fill yes))",
            "(gr_poly (pts (xy 0 0) (xy 1 0)) (width 0) (fill yes))",
        )
    )
    assert len(entries) == 1  # the anchor alone


def test_padstack_layer_with_an_unknown_ratio_is_its_box() -> None:
    design = design_of(Part("D1", "Mini_LED_THT_3mm", 0, 0))

    def stack(pad: Pad) -> Pad:
        layers = (
            PadstackLayer("F.Cu", pad.shape, pad.size),
            PadstackLayer("B.Cu", "roundrect", Size(1_000_000, 600_000)),
        )
        return dataclasses.replace(
            pad, padstack=Padstack(id="pst_00000000-0000-4000-8000-000000000001", layers=layers)
        )

    found: list[Issue] = []
    front, back = _entries(_with_pad(design, stack), found)
    assert front.exact and front.layer == "F.Cu"
    assert back.core == (pt(-0.5, -0.3), pt(0.5, -0.3), pt(0.5, 0.3), pt(-0.5, 0.3)) and back.exact is False
    assert [i.code for i in found] == ["kicad.frame.shape-approximated"]


def test_bench_footprints_exist() -> None:
    for name in (
        "Frame_Shapes",
        "Frame_Round",
        "Frame_NoCourtyard",
        "Frame_OpenCourtyard",
        "Frame_Trapezoid",
    ):
        assert definition(name, "Frame").name == name
