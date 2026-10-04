# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored boards and the grid search of the board-analyses tests (change c0047).

``slot_board`` and ``edge_board`` are the boards of the scenarios "Around a slot" and "Track above track":
round numbers chosen for Fenolite, no value of any standard. ``grid_shortest`` is an eight-neighbour
search on a grid, test code only: it bounds the surface search from above and, within the error of the
eight-neighbour metric, from below.
"""

from __future__ import annotations

import dataclasses
import heapq
from collections.abc import Sequence

from _coppercheck import Copper, ident

from fenolite.analysis.boundary import BoardBoundary, board_boundary
from fenolite.core.coords import Point
from fenolite.model.board import Outline
from fenolite.model.design import Design

MM = 1_000_000
Ring = tuple[Point, ...]


def at(x: float, y: float) -> Point:
    """A point given in millimetres."""
    return Point(round(x * MM), round(y * MM))


def box(x0: float, y0: float, x1: float, y1: float) -> Ring:
    return (at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1))


def with_outline(design: Design, outer: Ring, cutouts: Sequence[Ring] = ()) -> Design:
    """``design`` with a model outline."""
    assert design.board is not None
    outline = Outline(id=ident("out", 1), points=tuple(outer), cutouts=tuple(tuple(c) for c in cutouts))
    return dataclasses.replace(design, board=dataclasses.replace(design.board, outline=outline))


SLOT = box(4, -3, 6, 3)
SLOT_OUTER = box(-10, -10, 20, 10)
NOTCH_OUTER: Ring = (
    at(-10, -10), at(4, -10), at(4, 3), at(6, 3), at(6, -10), at(20, -10), at(20, 10), at(-10, 10),
)  # fmt: skip


def discs(layers: int = 2) -> Copper:
    """Two through vias of diameter 1 mm: net ``A`` at (0, 0) and net ``B`` at (10 mm, 0)."""
    made = Copper(layers=4 if layers == 4 else 2)
    made.via("A", at(0, 0), diameter=MM)
    made.via("B", at(10, 0), diameter=MM)
    return made


def slot_board(*, notch: bool = False, thickness: int | None = None) -> tuple[Design, BoardBoundary]:
    """The two discs in a 30 mm × 20 mm outline centred on (5 mm, 0), with a cut-out from (4 mm, −3 mm)
    to (6 mm, 3 mm) between them; with ``notch`` the cut-out is a notch open at the lower edge."""
    design = discs().build()
    design = with_outline(design, NOTCH_OUTER) if notch else with_outline(design, SLOT_OUTER, (SLOT,))
    assert design.board is not None
    return design, board_boundary(design.board, thickness=thickness)


def edge_board(*, thickness: int | None = 1_600_000) -> tuple[Design, BoardBoundary]:
    """A 20 mm × 10 mm board from (0, 0): a 0.5 mm track of net ``A`` on ``F.Cu`` and one of net ``B`` on
    ``B.Cu``, both from (5 mm, 2 mm) to (15 mm, 2 mm)."""
    made = Copper()
    made.track("A", at(5, 2), at(15, 2), width=500_000, layer="F.Cu")
    made.track("B", at(5, 2), at(15, 2), width=500_000, layer="B.Cu")
    design = with_outline(made.build(), box(0, 0, 20, 10))
    assert design.board is not None
    return design, board_boundary(design.board, thickness=thickness)


def grid_shortest(
    start: Point, goal: Point, outer: tuple[Point, Point], holes: Sequence[tuple[Point, Point]], step: int
) -> int | None:
    """The length in nanometres of a shortest eight-neighbour path on a grid of pitch ``step`` from
    ``start`` to ``goal`` inside the rectangle ``outer``, never strictly inside a rectangle of ``holes``;
    every point is a grid point. Diagonal steps cost ``step · 1.41421356``, rounded up to an integer."""
    diagonal = (step * 141_421_357 + 99_999_999) // 100_000_000

    def blocked(x: int, y: int) -> bool:
        if not (outer[0].x <= x <= outer[1].x and outer[0].y <= y <= outer[1].y):
            return True
        return any(low.x < x < high.x and low.y < y < high.y for low, high in holes)

    def crosses(x: int, y: int, dx: int, dy: int) -> bool:
        """Whether a diagonal step cuts the corner of a hole: its middle lies strictly inside one."""
        mx2, my2 = 2 * x + dx, 2 * y + dy
        return any(2 * low.x < mx2 < 2 * high.x and 2 * low.y < my2 < 2 * high.y for low, high in holes)

    best: dict[tuple[int, int], int] = {(start.x, start.y): 0}
    heap = [(0, start.x, start.y)]
    while heap:
        dist, x, y = heapq.heappop(heap)
        if (x, y) == (goal.x, goal.y):
            return dist
        if dist > best.get((x, y), dist):
            continue
        for dx in (-step, 0, step):
            for dy in (-step, 0, step):
                if (dx, dy) == (0, 0):
                    continue
                nx, ny = x + dx, y + dy
                if blocked(nx, ny) or crosses(x, y, dx, dy):
                    continue
                total = dist + (diagonal if dx and dy else step)
                if total < best.get((nx, ny), total + 1):
                    best[(nx, ny)] = total
                    heapq.heappush(heap, (total, nx, ny))
    return None


# --- benches of the recorded KiCad bracket (written boards) ----------------------------------------

CANARY_NETS = ("CANARY_A", "CANARY_B")
CANARY_RULE = "(rule canary\n\t(constraint clearance (min 3mm))\n)\n"
BRACKET_NM = 50_000
"""The bracket of the recorded KiCad probe: a rule this far below Fenolite's value must pass and one this
far above must fail."""
BENCH_THICKNESS = 1_600_000
SHIFT = 20
"""Benches are shifted by 20 mm on both axes, so every coordinate of the written board is positive."""


@dataclasses.dataclass(frozen=True)
class CreepBench:
    """A written-ready board for the bracket: the design, the creepage Fenolite expects between the nets
    ``A`` and ``B``, and the board thickness the analysis needs for it (``None`` on one face)."""

    name: str
    design: Design
    creepage: int
    thickness: int | None

    def rules(self, minimum: int) -> str:
        """A rules text with the canary and one ``creepage`` rule on the two probe nets."""
        from fenolite.core.units import format_length

        return (
            "(version 1)\n"
            + CANARY_RULE
            + "(rule fenolite_creepage\n"
            + "\t(condition \"A.NetName == 'A' && B.NetName == 'B'\")\n"
            + f"\t(constraint creepage (min {format_length(minimum)}))\n)\n"
        )


def _shifted(x: float, y: float) -> Point:
    return at(x + SHIFT, y + SHIFT)


def _canary(made: Copper, x: float, y: float) -> None:
    for index, name in enumerate(CANARY_NETS):
        made.track(name, _shifted(x, y + index), _shifted(x + 2, y + index), width=250_000)


def creep_bench(name: str) -> CreepBench:
    """``slot``: two 1 mm tracks on ``F.Cu`` whose round ends lie at (0, 0) and (10 mm, 0), with the slot
    of "Around a slot" between them: 11 mm. ``edge``: the tracks of "Track above track": 5.1 mm."""
    made = Copper()
    if name == "slot":
        made.track("A", _shifted(-2, 0), _shifted(0, 0), width=MM)
        made.track("B", _shifted(10, 0), _shifted(12, 0), width=MM)
        _canary(made, -8, 7)
        outer = tuple(_shifted(p.x / MM, p.y / MM) for p in SLOT_OUTER)
        slot = tuple(_shifted(p.x / MM, p.y / MM) for p in SLOT)
        return CreepBench(name, with_outline(made.build(), outer, (slot,)), 11 * MM, None)
    if name == "edge":
        made.track("A", _shifted(5, 2), _shifted(15, 2), width=500_000, layer="F.Cu")
        made.track("B", _shifted(5, 2), _shifted(15, 2), width=500_000, layer="B.Cu")
        _canary(made, 2, 7)
        outer = tuple(_shifted(p.x / MM, p.y / MM) for p in box(0, 0, 20, 10))
        return CreepBench(name, with_outline(made.build(), outer), 5_100_000, BENCH_THICKNESS)
    raise KeyError(name)
