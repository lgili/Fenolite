# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A milled slot gives the creepage of the same stadium drawn as a cut-out, and two overlapping slots that
of their merged ring drawn by hand (capability board-analyses, "Slots in creepage"; change c0169). The
boards are copies of the shared slot fixture of change c0167 with two conductors added."""

from __future__ import annotations

import dataclasses
import importlib.util
import math
from pathlib import Path

import pytest
from _analysis import MM, discs

from fenolite import dsl
from fenolite.analysis import analyze_distances, board_boundary
from fenolite.analysis.report import DistanceRow
from fenolite.core.coords import Point
from fenolite.model.board import Outline
from fenolite.model.design import Design

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="the union needs pyclipper of the geo extra")
FIXTURE = Path(__file__).resolve().parents[2] / "data" / "slots" / "design.py"
S1 = 'design.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=30, name="S1")'
S1_RING = "design.cutout(shape.stadium(mm(15), mm(10), mm(12), mm(2), rot=30))"
ELL = (
    'design.slot(mm(40), mm(10), length=mm(12), width=mm(2), name="S2")\n'
    'design.slot(mm(45), mm(15), length=mm(12), width=mm(2), rot=90, name="S3")'
)
ELL_RING = (
    "design.cutout(((mm(35), mm(9)), (mm(45), mm(9)),"
    " arc_to((mm(45.707107), mm(9.292893)), (mm(46), mm(10))), (mm(46), mm(20)),"
    " arc_to((mm(45), mm(21)), (mm(44), mm(20))), (mm(44), mm(11)), (mm(35), mm(11)),"
    " arc_to((mm(34), mm(10)), (mm(35), mm(9)))))"
)
"""The L of ``S2`` and ``S3`` drawn by hand as its merged ring: seven vertices, three arcs."""
PAIR = (("A", "B"),)


def fixture(*swaps: tuple[str, str]) -> Outline:
    """The outline of the shared fixture, each ``(old, new)`` line of ``swaps`` replaced first."""
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "from fenolite.dsl import Design, mm, shape", "from fenolite.dsl import Design, arc_to, mm, shape"
    )
    for old, new in swaps:
        assert old in text, old
        text = text.replace(old, new)
    scope: dict[str, object] = {"__name__": "fixture"}
    exec(compile(text, str(FIXTURE), "exec"), scope)  # noqa: S102 - the fixture authored for Fenolite
    design = scope["design"]
    assert isinstance(design, dsl.Design)
    board = dsl.to_model(design).board
    assert board is not None and board.outline is not None
    return board.outline


def with_conductors(outline: Outline, a: Point, b: Point) -> Design:
    """Two round conductors of 1 mm, net ``A`` at ``a`` and net ``B`` at ``b``, inside ``outline``."""
    made = discs()
    made.vias.clear()
    made.via("A", a, diameter=MM)
    made.via("B", b, diameter=MM)
    design = made.build()
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, outline=outline))


def creepage(design: Design, groove: int | None = None) -> int:
    assert design.board is not None
    boundary = board_boundary(design.board)
    assert not boundary.problem, boundary.problem
    report = analyze_distances(design, pads=None, boundary=boundary, pairs=PAIR, groove=groove)
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None
    return row.creepage.low


def across_s1() -> tuple[Point, Point]:
    """Two points 3 mm from the axis of ``S1`` (about (115, 110) mm, turned 30°), one on either side."""
    turn = math.radians(30)
    nx, ny = math.sin(turn) * 3 * MM, math.cos(turn) * 3 * MM  # the axis runs along (cos, −sin)
    return Point(round(115 * MM + nx), round(110 * MM + ny)), Point(
        round(115 * MM - nx), round(110 * MM - ny)
    )


def lone(outline: Outline) -> Outline:
    """``outline`` without the slots ``S2`` and ``S3``, so that no union is needed."""
    return dataclasses.replace(outline, slots=tuple(s for s in outline.slots if s.name not in ("S2", "S3")))


def test_slot_and_ring_are_equal() -> None:
    """Scenario "Slot and ring are equal"."""
    slot = lone(fixture())
    ring = lone(fixture((S1, S1_RING)))
    assert [s.name for s in slot.slots] == ["S1"] and ring.slots == ()
    a, b = across_s1()
    first, second = with_conductors(slot, a, b), with_conductors(ring, a, b)
    assert creepage(first) == creepage(second)
    assert creepage(first) > 6 * MM - 2 * MM // 2  # the path goes round a round end of the slot
    # a groove width above the slot's 2 mm bridges both alike; 1 µm below it neither (the sides of the
    # turned slot are rounded to the nanometre, so its width is 2 mm within 1 nm)
    narrow = 2 * MM - 1_000
    assert creepage(first, narrow) == creepage(second, narrow) == creepage(first)
    bridged = creepage(first, 2 * MM + 1)
    assert bridged == creepage(second, 2 * MM + 1) < creepage(first)
    assert 0 <= 5 * MM - bridged <= 2  # straight across, from conductor edge to conductor edge


@needs_geo
def test_whole_fixture_slot_and_ring_are_equal() -> None:
    a, b = across_s1()
    first = with_conductors(fixture(), a, b)
    second = with_conductors(fixture((S1, S1_RING)), a, b)
    assert creepage(first) == creepage(second)
    assert creepage(first, 2 * MM + 1) == creepage(second, 2 * MM + 1)


@needs_geo
def test_ell_of_two_slots_and_its_merged_ring_are_equal() -> None:
    merged = fixture()
    drawn = fixture((ELL, ELL_RING))
    assert len(drawn.cutouts) == 2 and [s.name for s in drawn.slots] == ["S1"]
    # inside the corner of the L and outside it: the path goes round an end of the L
    a, b = Point(141 * MM, 114 * MM), Point(148 * MM, 107 * MM)
    first, second = with_conductors(merged, a, b), with_conductors(drawn, a, b)
    assert creepage(first) == creepage(second)
    assert creepage(first, 2 * MM + 1) == creepage(second, 2 * MM + 1) < creepage(first)
