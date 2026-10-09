# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board outline as rings (capability kicad-file-backend, "Board outline as rings"; changes c0022 and
c0074: endpoints closer than ``CHAIN_GAP`` are joined, and footprint edge items are part of the outline)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _buildhelp import blink, build
from _layout_edit import add_items, add_to_footprint

from fenolite.backends.kicad.frame import footprint_edges
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import CHAIN_GAP, EVIDENCE, PROBLEMS, BoardOutline, board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import Location, area2, point_in_ring
from fenolite.model.board import Board, Graphic, GraphicKind, Outline
from fenolite.model.design import Design

FIXTURE = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def graphic(n: int, kind: GraphicKind, *points: Point, layer: str = "Edge.Cuts") -> Graphic:
    return Graphic(id=derived_id("gfx", "outline", str(n)), kind=kind, layer=layer, points=points)


def design_with(*graphics: Graphic, outline: Outline | None = None) -> Design:
    design = Design.new("outline", seed=0)
    board = Board(
        id=derived_id("brd", "outline", "board"), layers=created_layers(2), graphics=graphics, outline=outline
    )
    return dataclasses.replace(design, board=board)


RECT = (mm(0, 0), mm(50, 0), mm(50, 30), mm(0, 30))


def rect_lines(first: int = 0) -> list[Graphic]:
    ends = (*RECT[1:], RECT[0])
    return [graphic(first + n, "line", a, b) for n, (a, b) in enumerate(zip(RECT, ends, strict=True))]


def test_model_outline() -> None:
    output = build(blink(), 10)
    found = board_outline(output.design)
    assert output.design.board is not None and output.design.board.outline is not None
    assert found.source == "model" and found.problem == "" and found.exact
    assert found.rings == (tuple(output.design.board.outline.points),)


def test_model_outline_with_cutouts() -> None:
    hole = (mm(10, 10), mm(20, 10), mm(20, 20), mm(10, 20))
    outline = Outline(id=derived_id("out", "outline", "o"), points=RECT, cutouts=(hole,))
    found = board_outline(design_with(outline=outline))
    assert found == BoardOutline((RECT, hole), "model")


def test_edge_graphics_with_a_cutout() -> None:
    circle = graphic(9, "circle", mm(10, 15), mm(12, 15))
    found = board_outline(design_with(*rect_lines(), circle))
    assert found.source == "edge" and found.problem == "" and not found.exact
    assert len(found.rings) == 2
    assert set(found.rings[0]) == set(RECT) and area2(found.rings[0]) > 0
    hole = found.rings[1]
    assert len(hole) > 8 and all(
        abs((p.x - 10 * MM) ** 2 + (p.y - 15 * MM) ** 2 - (2 * MM) ** 2) < 10 * MM for p in hole
    )
    assert all(point_in_ring(p, found.rings[0]) is Location.INSIDE for p in hole)


def test_built_board_read_back_gives_edge_rings() -> None:
    output = build(blink(), 10)
    design = read_board(output.files["blink.kicad_pcb"].decode("utf-8"), file="blink.kicad_pcb")
    found = board_outline(design)
    assert found.source == "edge" and found.exact and len(found.rings) == 1
    assert output.design.board is not None and output.design.board.outline is not None
    assert set(found.rings[0]) == set(output.design.board.outline.points)


def test_open_contour_named() -> None:
    found = board_outline(design_with(*rect_lines()[:3], graphic(9, "circle", mm(10, 15), mm(12, 15))))
    assert found.rings == () and found.problem == "open-contour"


def test_branching_contour_named() -> None:
    extra = graphic(8, "line", mm(0, 0), mm(50, 30))
    found = board_outline(design_with(*rect_lines(), extra))
    assert found.rings == () and found.problem == "branching-contour"


def test_arcs_are_approximated() -> None:
    """A stadium: two lines and two half circles."""
    pieces = (
        graphic(0, "line", mm(10, 0), mm(30, 0)),
        graphic(1, "arc", mm(30, 0), mm(35, 5), mm(30, 10)),
        graphic(2, "line", mm(30, 10), mm(10, 10)),
        graphic(3, "arc", mm(10, 10), mm(5, 5), mm(10, 0)),
    )
    found = board_outline(design_with(*pieces))
    assert found.problem == "" and not found.exact and len(found.rings) == 1
    ring = found.rings[0]
    assert {mm(10, 0), mm(30, 0), mm(30, 10), mm(10, 10), mm(35, 5), mm(5, 5)} <= set(ring)
    assert len(ring) > 20 and area2(ring) > 0


def test_rect_and_polygon_items() -> None:
    rect = graphic(0, "rect", mm(0, 0), mm(50, 30))
    slot = graphic(1, "polygon", mm(5, 5), mm(8, 5), mm(8, 9))
    found = board_outline(design_with(rect, slot))
    assert found.exact and found.source == "edge"
    assert set(found.rings[0]) == set(RECT)
    assert set(found.rings[1]) == {mm(5, 5), mm(8, 5), mm(8, 9)}


def test_other_layers_and_zero_length_lines_are_ignored() -> None:
    silk = graphic(7, "line", mm(0, 0), mm(9, 9), layer="F.SilkS")
    dot = graphic(8, "line", mm(3, 3), mm(3, 3))
    found = board_outline(design_with(*rect_lines(), silk, dot))
    assert found.problem == "" and len(found.rings) == 1


def test_no_edge_content() -> None:
    assert board_outline(design_with()).problem == "no-edge-content"
    assert board_outline(design_with(graphic(0, "line", mm(0, 0), mm(1, 1), layer="F.Fab"))).rings == ()
    assert (
        board_outline(dataclasses.replace(Design.new("x", seed=0), board=None)).problem == "no-edge-content"
    )


def test_footprint_edges_only() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    design = read_board(text, file=FIXTURE.name)
    assert design.board is not None
    assert board_outline(design).source == "edge" and len(board_outline(design).rings) == 1
    line = (
        "\t\t(fp_line\n\t\t\t(start -1 -1)\n\t\t\t(end 1 -1)\n\t\t\t(stroke\n\t\t\t\t(width 0.05)\n"
        '\t\t\t\t(type solid)\n\t\t\t)\n\t\t\t(layer "Edge.Cuts")\n'
        '\t\t\t(uuid "0e0e0e0e-0000-4000-8000-000000000001")\n\t\t)\n'
    )
    marker = '\t\t(pad "1" smd rect'
    assert marker in text
    edited = read_board(text.replace(marker, line + marker, 1), file=FIXTURE.name)
    assert edited.board is not None
    edge = {layer.name for layer in edited.board.layers if layer.kind == "edge"}
    bare = dataclasses.replace(
        edited.board, graphics=tuple(g for g in edited.board.graphics if g.layer not in edge)
    )
    # c0074: the footprint's line is edge content now, and one line alone is an open contour
    assert board_outline(dataclasses.replace(edited, board=bare)).problem == "open-contour"
    plain = dataclasses.replace(
        design.board, graphics=tuple(g for g in design.board.graphics if g.layer not in edge)
    )
    assert board_outline(dataclasses.replace(design, board=plain)).problem == "no-edge-content"


def test_outline_holds_rings_or_a_problem() -> None:
    with pytest.raises(ValueError, match="rings or a problem"):
        BoardOutline()
    with pytest.raises(ValueError, match="rings or a problem"):
        BoardOutline((RECT,), problem="open-contour")
    assert set(PROBLEMS) == {"open-contour", "branching-contour", "no-edge-content"}
    assert EVIDENCE.hypotheses == ("H-G-PLACE-OUTLINE", "H-K-OUTLINE-CHAIN", "H-K-OUTLINE-FPEDGE")


# -- endpoints closer than CHAIN_GAP are joined (c0074; H-K-OUTLINE-CHAIN)


def gapped(gap: int) -> list[Graphic]:
    """The rectangle whose last line stops ``gap`` nm short of the first corner."""
    lines = rect_lines()
    last = lines[-1]
    short = Point(RECT[0].x, RECT[0].y + gap)
    return [*lines[:-1], dataclasses.replace(last, points=(last.points[0], short))]


def test_gap_below_the_chaining_distance() -> None:
    assert CHAIN_GAP == 10_000
    found = board_outline(design_with(*gapped(9_999)))
    assert found.problem == "" and found.joined == 1 and len(found.rings) == 1
    assert set(found.rings[0]) == set(RECT) and found.exact
    assert board_outline(design_with(*gapped(10_000))).problem == "open-contour"
    assert board_outline(design_with(*gapped(10_001))).problem == "open-contour"
    exact = board_outline(design_with(*rect_lines()))
    assert exact.joined == 0 and set(exact.rings[0]) == set(RECT)


def test_diagonal_gap_is_measured_exactly() -> None:
    lines = rect_lines()
    last = lines[-1]
    near = dataclasses.replace(last, points=(last.points[0], Point(RECT[0].x + 7_071, RECT[0].y + 7_071)))
    far = dataclasses.replace(last, points=(last.points[0], Point(RECT[0].x + 7_072, RECT[0].y + 7_072)))
    assert board_outline(design_with(*lines[:-1], near)).joined == 1  # 7071² + 7071² < 10 000²
    assert board_outline(design_with(*lines[:-1], far)).problem == "open-contour"


def test_joined_point_is_the_smallest_of_its_group() -> None:
    found = board_outline(design_with(*gapped(5_000)))
    assert RECT[0] in found.rings[0] and Point(RECT[0].x, RECT[0].y + 5_000) not in found.rings[0]


def test_three_ends_within_the_gap_branch() -> None:
    spur = graphic(9, "line", Point(RECT[0].x + 3_000, RECT[0].y + 3_000), mm(-5, -5))
    assert board_outline(design_with(*rect_lines(), spur)).problem == "branching-contour"


def test_a_piece_shorter_than_the_gap_is_dropped() -> None:
    sliver = graphic(9, "line", RECT[0], Point(RECT[0].x + 2_000, RECT[0].y))
    found = board_outline(design_with(*gapped(0)[:-1], rect_lines()[-1], sliver))
    assert found.problem == "" and found.joined == 1 and set(found.rings[0]) == set(RECT)


def test_arc_ends_are_joined() -> None:
    arc = graphic(1, "arc", Point(50 * MM, 5_000), mm(55, 15), mm(50, 30))
    lines = [graphic(0, "line", mm(0, 0), mm(50, 0)), graphic(2, "line", mm(50, 30), mm(0, 30))]
    close = graphic(3, "line", mm(0, 30), mm(0, 0))
    found = board_outline(design_with(*lines, arc, close))
    assert found.problem == "" and found.joined == 1 and not found.exact


# -- edge items inside footprints (c0074; H-K-OUTLINE-FPEDGE)

EDGE = '(stroke (width 0.05) (type solid)) (layer "Edge.Cuts")'


def blink_with(*items: str, drop_top: bool = False, rotate: bool = False) -> Design:
    """The built blink read back, with ``items`` inside the footprint of ``R1`` (at (132, 109) mm). With
    ``drop_top`` the top edge line is replaced by two lines that leave an opening from x = 120 to 125 mm;
    with ``rotate`` the footprint is turned 90 degrees."""
    text = build(blink(), 10).files["blink.kicad_pcb"].decode("utf-8")
    for n, item in enumerate(items):
        text = add_to_footprint(text, "R1", item.replace("UUID", f"0e0e0e0e-0000-4000-8000-00000000000{n}"))
    if rotate:
        assert text.count("(at 132 109)") == 1
        text = text.replace("(at 132 109)", "(at 132 109 90)")
    if drop_top:
        top = "(gr_line\n\t\t(start 100 100)\n\t\t(end 150 100)"
        assert text.count(top) == 1
        text = text.replace(top, "(gr_line\n\t\t(start 100 100)\n\t\t(end 120 100)")
        text = add_items(
            text,
            f'(gr_line (start 125 100) (end 150 100) {EDGE} (uuid "0e0e0e0e-0000-4000-8000-0000000000a0"))',
        )
    return read_board(text)


def test_edge_closed_by_a_footprint() -> None:
    assert board_outline(blink_with(drop_top=True)).problem == "open-contour"
    line = f'(fp_line (start -12 -9) (end -7 -9) {EDGE} (uuid "UUID"))'
    design = blink_with(line, drop_top=True)
    found = board_outline(design)
    assert found.problem == "" and found.source == "edge" and len(found.rings) == 1
    assert {mm(120, 100), mm(125, 100)} <= set(found.rings[0]) and found.joined == 0
    assert design.board is not None
    (item,) = footprint_edges(design.board, {"Edge.Cuts"})
    assert (item.kind, item.points, item.layer) == ("line", (mm(120, 100), mm(125, 100)), "Edge.Cuts")
    assert footprint_edges(design.board, {"F.SilkS"}) != () and footprint_edges(design.board, set()) == ()


def test_footprint_circle_is_a_cut_out() -> None:
    circle = f'(fp_circle (center 0 4) (end 1 4) {EDGE} (fill no) (uuid "UUID"))'
    found = board_outline(blink_with(circle))
    assert found.problem == "" and len(found.rings) == 2 and not found.exact
    board, hole = found.rings
    assert abs(area2(board)) > abs(area2(hole))
    assert point_in_ring(mm(132, 113), hole) is Location.INSIDE
    assert point_in_ring(mm(132, 109), hole) is Location.OUTSIDE


def test_footprint_rect_and_polygon_follow_the_rotation() -> None:
    rect = f'(fp_rect (start 2 -1) (end 4 1) {EDGE} (fill no) (uuid "UUID"))'
    poly = f'(fp_poly (pts (xy -4 -1) (xy -2 -1) (xy -3 1)) {EDGE} (fill no) (uuid "UUID"))'
    plain = blink_with(rect, poly)
    turned = blink_with(rect, poly, rotate=True)
    assert plain.board is not None and turned.board is not None
    square, triangle = footprint_edges(plain.board, {"Edge.Cuts"})
    assert square.kind == triangle.kind == "polygon"
    assert set(square.points) == {mm(134, 108), mm(136, 108), mm(136, 110), mm(134, 110)}
    assert set(triangle.points) == {mm(128, 108), mm(130, 108), mm(129, 110)}
    # stored angles are counter-clockwise on a Y-down frame: (x, y) of the footprint goes to (y, -x)
    square_90, triangle_90 = footprint_edges(turned.board, {"Edge.Cuts"})
    assert set(square_90.points) == {mm(131, 107), mm(131, 105), mm(133, 105), mm(133, 107)}
    assert set(triangle_90.points) == {mm(131, 113), mm(131, 111), mm(133, 112)}
    assert len(board_outline(plain).rings) == 3 and len(board_outline(turned).rings) == 3


def test_texts_and_other_layers_are_not_edge_items() -> None:
    silk = (
        '(fp_line (start -1 -2) (end 1 -2) (stroke (width 0.1) (type solid)) (layer "F.SilkS") (uuid "UUID"))'
    )
    design = blink_with(silk)
    assert design.board is not None
    assert footprint_edges(design.board, {"Edge.Cuts"}) == ()
    assert board_outline(design).rings == board_outline(blink_with()).rings


# --- model outlines with arcs, the box and the build's check (change c0102) --------------------------


def script_model(board: str, *cutouts: str, zone: bool = False) -> Design:
    """The model of a script with one ``board()`` call, its cut-outs and, with ``zone``, a ``GND`` pour
    declared without an outline."""
    from fenolite import dsl
    from fenolite.dsl import arc_to, mm, shape

    d = dsl.Design("outline")
    scope = {"d": d, "mm": mm, "shape": shape, "arc_to": arc_to}
    exec(f"d.board({board})", scope)  # noqa: S102 - the scenario's own call
    for cutout in cutouts:
        exec(f"d.cutout({cutout})", scope)  # noqa: S102
    if zone:
        d.zone(dsl.Net("GND"), layers=("B.Cu",))
    return dsl.to_model(d)


ROUNDED = "outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3))"
HOLE = "shape.circle(mm(10), mm(10), mm(3.2))"


def test_model_outline_with_arcs() -> None:
    found = board_outline(script_model(ROUNDED, HOLE))
    assert found.source == "model" and not found.exact and len(found.rings) == 2
    centre, radius = mm(110, 110), 1_600_000
    for point in found.rings[1]:
        distance2 = (point.x - centre.x) ** 2 + (point.y - centre.y) ** 2
        assert (radius - 5_000) ** 2 <= distance2 <= (radius + 5_000) ** 2
    assert len(found.rings[1]) > 8 and len(found.rings[0]) > 8
    # the corners are cut: the corner point of the box is outside the ring
    assert point_in_ring(mm(100.1, 100.1), found.rings[0]) is Location.OUTSIDE
    assert point_in_ring(mm(101, 101), found.rings[0]) is Location.INSIDE


def test_box_of_a_round_board() -> None:
    from fenolite.backends.kicad.outline import outline_box

    design = script_model("outline=shape.circle(mm(20), mm(20), mm(40))")
    assert outline_box(design) == (100 * MM, 100 * MM, 140 * MM, 140 * MM)
    assert design.board is not None and design.board.outline is not None
    points = design.board.outline.points
    assert (min(p.y for p in points), max(p.y for p in points)) == (120 * MM, 120 * MM)
    assert outline_box(script_model("mm(50), mm(30)")) == (100 * MM, 100 * MM, 150 * MM, 130 * MM)
    assert outline_box(Design.new("none", seed=0)) is None
    # without a model outline: the rings of the edge content
    assert outline_box(design_with(*rect_lines())) == (0, 0, 50 * MM, 30 * MM)
    assert outline_box(design_with(*rect_lines()[:3])) is None


def check_codes(design: Design) -> list[str]:
    from fenolite.backends.kicad.outline import check_outline

    return [found.code for found in check_outline(design)]


def test_check_a_clean_outline() -> None:
    slot = "shape.slot((mm(19), mm(30)), (mm(31), mm(30)), mm(2))"
    assert check_codes(script_model(ROUNDED, HOLE, slot)) == []
    assert check_codes(script_model("mm(50), mm(30)")) == []
    assert check_codes(Design.new("none", seed=0)) == []
    assert check_codes(design_with(*rect_lines())) == []  # no model outline: nothing to judge


def test_check_rings_that_cross_touch_or_nest() -> None:
    from fenolite.backends.kicad.outline import CHECK_ISSUE_CODES, check_outline

    def circle(x: float, y: float, d: float) -> str:
        return f"shape.circle(mm({x}), mm({y}), mm({d}))"

    cases = (
        (circle(39, 15, 4),),  # across the right edge
        (circle(38, 15, 4),),  # touching it at one point
        (circle(18, 15, 4), circle(21, 15, 4)),  # two that overlap
        (circle(20, 15, 6), circle(20, 15, 2)),  # one inside the other
    )
    for index, cutouts in enumerate(cases):
        issues = check_outline(script_model("mm(40), mm(30)", *cutouts))
        assert [(i.code, i.severity) for i in issues] == [("kicad.outline.invalid", "error")], index
        if index < 2:
            assert "board" in issues[0].message and "cut-out 1" in issues[0].message
        else:
            assert "cut-out 1" in issues[0].message and "cut-out 2" in issues[0].message
    assert check_codes(script_model("mm(40), mm(30)", circle(20, 15, 4))) == []
    assert dict(CHECK_ISSUE_CODES) == {
        "kicad.outline.invalid": "error",
        "kicad.outline.zone-short": "warning",
    }


def test_check_a_cutout_outside_the_board_and_a_ring_that_crosses_itself() -> None:
    from fenolite.backends.kicad.outline import check_outline

    outside = check_outline(script_model("mm(40), mm(30)", "shape.circle(mm(60), mm(15), mm(4))"))
    assert [i.code for i in outside] == ["kicad.outline.invalid"] and "outside" in outside[0].message
    bow = "outline=((mm(0), mm(0)), (mm(30), mm(20)), (mm(30), mm(0)), (mm(0), mm(20)))"
    crossed = check_outline(script_model(bow))
    assert [i.code for i in crossed] == ["kicad.outline.invalid"]
    assert "board" in crossed[0].message and "itself" in crossed[0].message


def test_check_the_form_of_the_model() -> None:
    from fenolite.backends.kicad.outline import check_outline
    from fenolite.model.board import OutlineArc

    def with_outline(**changes: object) -> Design:
        base = Outline(id=derived_id("out", "outline", "o"), points=RECT)
        return design_with(outline=dataclasses.replace(base, **changes))  # type: ignore[arg-type]

    mid = mm(25, -5)
    bad = (
        with_outline(arcs=(OutlineArc(0, 1, mm(55, 15)), OutlineArc(0, 0, mid))),  # not sorted
        with_outline(arcs=(OutlineArc(0, 0, mid), OutlineArc(0, 0, mid))),  # twice
        with_outline(arcs=(OutlineArc(2, 0, mid),)),  # no such ring
        with_outline(arcs=(OutlineArc(0, 4, mid),)),  # no such edge
        with_outline(arcs=(OutlineArc(0, 0, mm(25, 0)),)),  # mid on the line
        with_outline(arcs=(OutlineArc(0, 0, mm(0, 0)),)),  # mid on a vertex
        with_outline(cutouts=((mm(10, 10), mm(20, 10)),)),  # two vertices and no arc
        with_outline(cutouts=((mm(10, 10),),)),  # one vertex
    )
    for index, design in enumerate(bad):
        issues = check_outline(design)
        assert issues and {i.code for i in issues} == {"kicad.outline.invalid"}, index
    named = check_outline(bad[4])[0].message
    assert "board" in named and "edge 0" in named


def test_check_a_zone_short_of_an_arc() -> None:
    from fenolite.backends.kicad.outline import check_outline, outline_box

    bulge = "arc_to((mm(45), mm(25)), (mm(40), mm(30)))"
    path = f"outline=((mm(0), mm(0)), (mm(40), mm(0)), {bulge}, (mm(0), mm(30)))"
    design = script_model(path, zone=True)
    box = outline_box(design)
    assert box is not None and 148 * MM < box[2] < 148_100_000  # the arc reaches x = 48.03 mm
    (issue,) = check_outline(design)
    assert (issue.code, issue.severity) == ("kicad.outline.zone-short", "warning") and "GND" in issue.message
    assert check_codes(script_model(path)) == []  # no zone, nothing to name
    assert check_codes(script_model(ROUNDED, zone=True)) == []  # the helpers put a point on every extreme
