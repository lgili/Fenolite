# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed paths for the board and its cut-outs (capability design-dsl, "Outline shapes in the DSL", "Board
and placements in the DSL" and "DSL to model"; change c0102)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.dsl import Design, DslError, arc_to, mm, nm, outline_locked, shape, to_model
from fenolite.model.board import OutlineArc

MM = 1_000_000


def at(x: float, y: float) -> Point:
    return Point(round((100 + x) * MM), round((100 + y) * MM))


def board(**kwargs: object) -> Design:
    design = Design("paths")
    design.board(**kwargs)  # type: ignore[arg-type]
    return design


def rect_board() -> Design:
    design = Design("paths")
    design.board(mm(50), mm(30))
    return design


# --- Board and placements in the DSL -----------------------------------------------------------------


def test_a_board_given_by_a_path() -> None:
    design = board(
        outline=((mm(0), mm(0)), (mm(40), mm(0)), (mm(40), mm(30)), (mm(10), mm(30))), copper=4, locked=True
    )
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None
    assert outline.points == (at(0, 0), at(40, 0), at(40, 30), at(10, 30))
    assert outline.arcs == () and outline.cutouts == ()
    assert outline_locked(design) is True and design.copper == 4 and design.size is None


def test_the_lock_is_false_by_default_and_before_board() -> None:
    assert outline_locked(Design("paths")) is False
    assert outline_locked(rect_board()) is False
    with pytest.raises(DslError, match="locked"):
        Design("paths").board(mm(50), mm(30), locked=1)  # type: ignore[arg-type]


def test_one_form_only() -> None:
    for call in (
        lambda d: d.board(mm(50), mm(30), outline=shape.circle(mm(20), mm(20), mm(40))),
        lambda d: d.board(),
        lambda d: d.board(mm(50)),
        lambda d: d.board(height=mm(30)),
    ):
        with pytest.raises(DslError, match="width and height"):
            call(Design("paths"))


def test_the_rectangle_form_is_unchanged() -> None:
    design = rect_board()
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None
    assert outline.points == (at(0, 0), at(50, 0), at(50, 30), at(0, 30))
    assert outline.arcs == () and design.size == (50 * MM, 30 * MM)
    with pytest.raises(DslError, match="once"):
        design.board(mm(50), mm(30))


# --- Outline shapes in the DSL -----------------------------------------------------------------------


def test_a_last_pair_on_the_first_point_closes_the_ring() -> None:
    design = board(outline=((mm(0), mm(0)), (mm(10), mm(0)), (mm(10), mm(10)), (mm(0), mm(0))))
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None and outline.points == (at(0, 0), at(10, 0), at(10, 10))


def test_a_last_arc_on_the_first_point_is_the_closing_edge() -> None:
    design = board(outline=((mm(0), mm(0)), (mm(10), mm(0)), arc_to((mm(5), mm(5)), (mm(0), mm(0)))))
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None and outline.points == (at(0, 0), at(10, 0))
    assert outline.arcs == (OutlineArc(0, 1, at(5, 5)),)


def test_lists_are_paths_too() -> None:
    design = board(outline=[[mm(0), mm(0)], [mm(10), mm(0)], [mm(10), mm(10)]])
    assert len(to_model(design).board.outline.points) == 3  # type: ignore[union-attr]


def test_refused_paths() -> None:
    design = rect_board()
    with pytest.raises(DslError, match=r"cutout\(\).*empty"):
        design.cutout(())
    with pytest.raises(DslError, match=r"cutout\(\): element 1 "):
        design.cutout(((mm(1), mm(1)), (mm(1), mm(1)), (mm(2), mm(5))))
    with pytest.raises(DslError, match=r"cutout\(\): element 1: the arc step"):
        design.cutout(((mm(0), mm(0)), arc_to((mm(1), mm(0)), (mm(2), mm(0)))))
    with pytest.raises(DslError, match="diameter"):
        shape.circle(mm(5), mm(5), nm(3))
    with pytest.raises(DslError, match="same point"):
        shape.slot((mm(1), mm(1)), (mm(1), mm(1)), mm(1))
    with pytest.raises(DslError, match=r"call board\(\) first"):
        Design("paths").cutout(shape.circle(mm(5), mm(5), mm(2)))
    assert design.cutout_paths == []


@pytest.mark.parametrize(
    ("path", "words"),
    [
        ("text", "sequence"),
        (5, "sequence"),
        ((arc_to((mm(1), mm(1)), (mm(2), mm(0))), (mm(0), mm(0))), "element 0"),
        (((mm(0), mm(0)), "x"), "element 1"),
        (((mm(0), mm(0)), (mm(1), mm(0)), 7), "element 2"),
        (((mm(0), mm(0)), (1, 2)), "element 1"),
        (((mm(0), mm(0)),), "three vertices"),
        (((mm(0), mm(0)), (mm(5), mm(0))), "three vertices"),
        (((mm(0), mm(0)), (mm(5), mm(0)), (mm(0), mm(0))), "three vertices"),
        (((mm(0), mm(0)), arc_to((mm(1), mm(1)), (mm(0), mm(0)))), "element 1"),
        (((mm(0), mm(0)), (mm(5), mm(0)), arc_to((mm(6), mm(1)), (mm(5), mm(0)))), "element 2"),
    ],
)
def test_malformed_paths_name_the_call_and_the_element(path: object, words: str) -> None:
    design = rect_board()
    with pytest.raises(DslError, match=r"cutout\(\)") as info:
        design.cutout(path)
    assert words in str(info.value)


def test_a_ring_of_two_vertices_with_one_arc() -> None:
    design = rect_board()
    design.cutout(((mm(10), mm(10)), arc_to((mm(12), mm(8)), (mm(14), mm(10)))))
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None and outline.cutouts == ((at(10, 10), at(14, 10)),)
    assert outline.arcs == (OutlineArc(1, 0, at(12, 8)),)


# --- DSL to model --------------------------------------------------------------------------------------


def test_cutouts_in_call_order() -> None:
    design = rect_board()
    design.cutout(((mm(5), mm(5)), (mm(10), mm(5)), (mm(10), mm(8))))
    design.cutout(shape.circle(mm(40), mm(15), mm(4)))
    outline = to_model(design).board.outline  # type: ignore[union-attr]
    assert outline is not None
    assert outline.cutouts == ((at(5, 5), at(10, 5), at(10, 8)), (at(42, 15), at(38, 15)))
    assert [(arc.ring, arc.edge) for arc in outline.arcs] == [(2, 0), (2, 1)]


def test_to_model_does_not_change_the_design_and_adds_no_hole() -> None:
    design = rect_board()
    design.cutout(shape.circle(mm(40), mm(15), mm(4)))
    design.hole("H1", mm(3), mm(3), drill=mm(3.2))
    first = to_model(design)
    assert to_model(design) == first and len(design.cutout_paths) == 1
    assert first.board is not None and first.board.holes == ()
