# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Relative placements in the DSL (change c0255; capability design-dsl, "Relative placements in the DSL",
"Placement references", "Axis determination" and "Locked relative placements")."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, mm, placements
from fenolite.dsl.relative import BoardRef, EdgeExpr, RefKey, relative_requests, turns


def _design() -> Design:
    design = Design("rel")
    design.board(mm(40), mm(30))
    return design


def _part(design: Design, ref: str):  # type: ignore[no-untyped-def]
    return design.part(ref, "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")


def test_a_request_is_recorded_not_resolved() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1.pad("VDD"), gap=mm("0.5"), by=c5.pad(1))
    assert list(placements(design)) == ["U1"]
    requests = relative_requests(design)
    assert list(requests) == ["C5"]
    request = requests["C5"]
    assert request.x.kind == "relation" and request.x.key == "right_of"
    assert request.x.ref == RefKey("pad", "U1", "VDD") and request.x.value == 500_000
    assert request.y.kind == "align" and request.y.key == "center"
    assert (request.by, request.by_index) == ("1", None)
    assert request.text() == "right_of=U1.pad(VDD) gap=0.5mm by=pad(1)"


def test_an_edge_expression() -> None:
    design = Design("edge")
    board = design.board(mm(40), mm(30))
    assert isinstance(board, BoardRef)
    j1 = _part(design, "J1")
    j1.place(left=board.left + mm(2), center_y=board.center_y, rot=90)
    request = relative_requests(design)["J1"]
    assert (request.x.kind, request.x.key, request.x.value) == ("edge", "left", 2_000_000)
    assert request.x.ref == RefKey("board") and request.x.ref_edge == "left"
    assert (request.y.key, request.y.ref_edge, request.y.value) == ("center_y", "center_y", 0)
    assert request.text() == "left=board.left+2mm center_y=board.center_y rot=90"
    with pytest.raises(DslError, match="scaled"):
        _part(design, "J2").place(left=board.left * 2)  # type: ignore[operator]
    with pytest.raises(DslError, match="two edges"):
        _part(design, "J3").place(left=board.left + board.right)  # type: ignore[operator]
    assert isinstance(board.right - mm(1), EdgeExpr)


def test_edges_of_parts_pads_and_board() -> None:
    design = _design()
    u1 = _part(design, "U1")
    assert u1.right.edge == "right" and u1.pad(2).center_y.target == u1.pad(2)
    assert design.board_ref.top.edge == "top"


@pytest.mark.parametrize(
    "call, words",
    [
        (lambda c, u, v: c.place(mm(1), right_of=u), "X axis is set twice"),
        (lambda c, u, v: c.place(right_of=u, left_of=v), "one relation"),
        (lambda c, u, v: c.place(left=mm(1)), "nothing sets the Y axis"),
        (lambda c, u, v: c.place(mm(1), mm(1), gap=mm(1)), "gap belongs to a relation"),
        (lambda c, u, v: c.place(left=mm(1), top=mm(1), align="start"), "align belongs to a relation"),
        (lambda c, u, v: c.place(mm(1), left=mm(2), top=mm(1)), "X axis is set twice"),
        (lambda c, u, v: c.place(right_of=u, by=u.pad(1)), "by must be a pad of the placed part"),
        (lambda c, u, v: c.place(right_of=u, gap=mm(-1)), "negative"),
        (lambda c, u, v: c.place(right_of=3), "takes a part, a pad"),
        (lambda c, u, v: c.place(mm(1)), "nothing sets the Y axis"),
    ],
)
def test_axis_conflicting_sources(call, words: str) -> None:  # type: ignore[no-untyped-def]
    design = _design()
    c5, u1, u2 = _part(design, "C5"), _part(design, "U1"), _part(design, "U2")
    with pytest.raises(DslError, match=words):
        call(c5, u1, u2)


def test_axis_explicit_cross_axis_wins() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(10), mm(10))
    c5.place(right_of=u1, top=mm(3))
    request = relative_requests(design)["C5"]
    assert (request.y.kind, request.y.key, request.y.value) == ("edge", "top", 3_000_000)
    assert request.text() == "right_of=U1 top=3mm"


def test_a_part_is_placed_once() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    c5.place(right_of=u1)
    with pytest.raises(DslError, match="already placed"):
        c5.place(mm(1), mm(1))


def test_a_turn_without_position() -> None:
    design = _design()
    r1 = _part(design, "R1")
    r1.place(rot=90)
    assert dict(turns(design)) == {"R1": (90_000_000, "top")}
    assert not placements(design) and not relative_requests(design)
    with pytest.raises(DslError, match="needs a position"):
        _part(design, "R2").place(locked=True)


def test_locked_part_next_to_an_unlocked_one() -> None:
    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1, locked=True)
    with pytest.raises(DslError, match=r"C5.*U1 is not locked"):
        relative_requests(design)


def test_locked_relative_chain_and_board() -> None:
    design = _design()
    u1, c5, c6 = _part(design, "U1"), _part(design, "C5"), _part(design, "C6")
    u1.place(mm(14), mm(15), locked=True)
    c5.place(right_of=u1, locked=True)
    c6.place(below=c5.pad(1), locked=True)
    _part(design, "J1").place(left=design.board_ref.left, top=mm(1), locked=True)
    assert all(request.locked for request in relative_requests(design).values())


def test_an_anchor_belongs_to_an_absolute_placement() -> None:
    from fenolite.model.board import MechanicalIntent

    design = _design()
    u1, c5 = _part(design, "U1"), _part(design, "C5")
    with pytest.raises(DslError, match="anchor"):
        c5.place(right_of=u1, locked=True, anchor=MechanicalIntent("x"))
