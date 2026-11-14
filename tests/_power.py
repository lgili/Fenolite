# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored regions, boards and oracles of the power-path tests (change c0115).

Every shape is authored for Fenolite with round, illustrative numbers: no value of any standard or
product. ``grid_cut`` and ``fdm_resistance`` are test code only (floats allowed): a minimum cut and a
finite-difference solution on a grid, the oracles of the narrowest section and of the region bounds.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence

from _analysis import MM, at, box
from _coppercheck import Copper, disc_entry, ident, rect_entry

from fenolite.analysis.copper import ARC_TOL_NM
from fenolite.analysis.fills import FillRegion
from fenolite.backends.base import BoardPad, PadCopper
from fenolite.core.coords import Point, Size
from fenolite.geometry import area2, keyhole_ring
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.design import Design
from fenolite.model.presentation import TitleBlock

Ring = tuple[Point, ...]


def neck_outer(width: float) -> Ring:
    """Two 10 mm squares joined by a neck 3 mm long and ``width`` mm wide, centred on ``y`` = 5 mm."""
    low, high = 5 - width / 2, 5 + width / 2
    return (
        at(0, 0), at(10, 0), at(10, low), at(13, low), at(13, 0), at(23, 0),
        at(23, 10), at(13, 10), at(13, high), at(10, high), at(10, 10), at(0, 10),
    )  # fmt: skip


DUMBBELL = neck_outer(2)
SPLIT4 = neck_outer(4)
SPLIT4_HOLE = box(10.7, 4.2, 12.3, 5.8)
"""A 1.6 mm square hole at the centre of the 4 mm neck: a strip of 1.2 mm on each side."""
SQUARE20 = box(0, 0, 20, 20)
SPOKE_HOLES: tuple[Ring, ...] = (
    box(8.5, 8.5, 9.75, 9.75), box(10.25, 8.5, 11.5, 9.75),
    box(8.5, 10.25, 9.75, 11.5), box(10.25, 10.25, 11.5, 11.5),
)  # fmt: skip
"""The 3 mm square at the centre of ``SQUARE20`` less four spokes 0.5 mm wide along the axes."""


def stored(outer: Sequence[Point], holes: Sequence[Sequence[Point]] = ()) -> Ring:
    """The ring a fill stores: ``outer`` with its holes joined by slits."""
    return keyhole_ring(outer, holes).ring if holes else tuple(outer)


def region(
    outer: Sequence[Point],
    holes: Sequence[Sequence[Point]] = (),
    *,
    net: str = "P",
    layer: str = "F.Cu",
    where: str = "zone#0",
) -> FillRegion:
    twice = abs(area2(outer)) - sum(abs(area2(hole)) for hole in holes)
    return FillRegion("zone", net, layer, where, tuple(outer), tuple(tuple(h) for h in holes), twice)


def dumbbell() -> FillRegion:
    return region(DUMBBELL)


def split4() -> FillRegion:
    return region(SPLIT4, (SPLIT4_HOLE,))


def spokes() -> FillRegion:
    return region(SQUARE20, SPOKE_HOLES)


def pour_board(outer: Sequence[Point], holes: Sequence[Sequence[Point]] = (), *, net: str = "P") -> Design:
    """A two-layer board with one zone of ``net`` on ``F.Cu`` whose one fill is the stored ring."""
    made = Copper()
    made.zone(net, outer, fills=(stored(outer, holes),))
    return made.build()


# --- authored boards of the power-path tests --------------------------------------------------------

Bench = tuple[Design, tuple[BoardPad, ...]]
STRIP = box(0, 0, 20, 5)
"""A strip 20 mm × 5 mm; the pads of ``strip`` and ``two_strips`` cover its two 5 mm ends 1 mm deep."""


def _rect(x0: float, y0: float, x1: float, y1: float, layer: str = "F.Cu") -> PadCopper:
    return rect_entry(round(x0 * MM), round(y0 * MM), round(x1 * MM), round(y1 * MM), layer)


def branch(*, main: int = MM, side: int = 250_000) -> Bench:
    """Net ``VBUS``: a 1 mm track on ``F.Cu`` from pad ``J1-1`` at (0, 0) to pad ``U1-1`` at (20 mm, 0),
    and a 0.25 mm track from (10 mm, 0) on the first track's body to pad ``C1-1`` at (10 mm, 5 mm)."""
    made = Copper()
    made.track("VBUS", at(0, 0), at(20, 0), width=main, locator="/main")
    made.track("VBUS", at(10, 0), at(10, 5), width=side, locator="/side")
    made.pad("J1", "1", "VBUS", disc_entry(0, 0, 1_500_000))
    made.pad("U1", "1", "VBUS", disc_entry(20 * MM, 0, 1_500_000))
    made.pad("C1", "1", "VBUS", disc_entry(10 * MM, 5 * MM, 1_500_000))
    return made.build(), tuple(made.pads)


def strip(*, net: str = "VBUS") -> Bench:
    """A region 20 mm × 5 mm on ``F.Cu`` between the pads ``J1-1`` and ``U1-1``, which cover its ends."""
    made = Copper()
    made.zone(net, STRIP, fills=(STRIP,), locator="/strip")
    made.pad("J1", "1", net, _rect(0, 0, 1, 5))
    made.pad("U1", "1", net, _rect(19, 0, 20, 5))
    return made.build(), tuple(made.pads)


def two_strips(*, net: str = "VBUS") -> Bench:
    """Through-hole pads ``J1-1`` and ``U1-1`` joined by the strip on ``F.Cu`` and by one on ``B.Cu``."""
    made = Copper()
    for layer in ("F.Cu", "B.Cu"):
        made.zone(net, STRIP, layer=layer, fills=(STRIP,), locator=f"/strip-{layer}")
    both = ("F.Cu", "B.Cu")
    made.pad("J1", "1", net, *(_rect(0, 0, 1, 5, layer) for layer in both), kind="thru_hole", layers=both)
    made.pad("U1", "1", net, *(_rect(19, 0, 20, 5, layer) for layer in both), kind="thru_hole", layers=both)
    return made.build(), tuple(made.pads)


def via_array(count: int = 8, *, net: str = "VBUS") -> Bench:
    """A region on ``F.Cu`` holding pad ``J1-1``, a region on ``B.Cu`` holding pad ``U1-1`` of a part on
    the bottom side, ``count`` through vias (0.6 mm, drill 0.3 mm) joined to both regions, and the pads
    ``C1-1`` and ``C2-1`` of decoupling parts joined to the ``F.Cu`` region only."""
    made = Copper()
    top, bottom = box(0, 0, 20, 10), box(10, 0, 30, 10)
    made.zone(net, top, fills=(top,), locator="/top")
    made.zone(net, bottom, layer="B.Cu", fills=(bottom,), locator="/bottom")
    for index in range(count):
        made.via(net, at(12 + 2 * (index % 4), 3 + 2 * (index // 4)), locator=f"/via[{index}]")
    made.pad("J1", "1", net, _rect(1, 4, 3, 6))
    made.pad("U1", "1", net, _rect(27, 4, 29, 6, "B.Cu"), layers=("B.Cu",))
    made.pad("C1", "1", net, _rect(5, 1, 6, 2))
    made.pad("C2", "1", net, _rect(5, 8, 6, 9))
    return made.build(), tuple(made.pads)


def written_strip(shift: float = 20.0) -> Design:
    """The board ``strip`` in a form a backend writes and reads back: the pads ``J1-1`` and ``U1-1`` are
    rectangular pads of 1 mm × 5 mm of two footprints, the strip is the stored fill of a zone, and all
    of it is moved by ``shift`` mm on both axes. ``tests/data/analysis/strip_10.kicad_pcb`` is this
    design written for target 10."""
    made = Copper()
    ring = tuple(Point(p.x + round(shift * MM), p.y + round(shift * MM)) for p in STRIP)
    made.zone("VBUS", ring, fills=(ring,))
    for ref, x in (("J1", 0.5), ("U1", 19.5)):
        made.pad(ref, "1", "VBUS")
        footprint = made.footprints[ref]
        pad = dataclasses.replace(footprint.pads[0], size=Size(MM, 5 * MM), position=Point(0, 0))
        made.footprints[ref] = dataclasses.replace(
            footprint, position=at(x + shift, 2.5 + shift), pads=(pad,)
        )
    design = made.build()
    assert design.board is not None
    title = TitleBlock(title="strip_10: authored for Fenolite, illustrative values")
    return dataclasses.replace(design, board=dataclasses.replace(design.board, title_block=title))


def neck_board(outer: Sequence[Point], holes: Sequence[Sequence[Point]] = (), *, net: str = "VBUS") -> Bench:
    """A pour of the neck family with a 2 mm × 2 mm pad ``J1-1`` in its left square and ``U1-1`` in its
    right one."""
    made = Copper()
    made.zone(net, outer, fills=(stored(outer, holes),), locator="/pour")
    made.pad("J1", "1", net, _rect(4, 4, 6, 6))
    made.pad("U1", "1", net, _rect(17, 4, 19, 6))
    return made.build(), tuple(made.pads)


PLANE = box(0, 0, 100, 80)
"""The outline of ``plane_board``: 100 mm × 80 mm."""


def _round_hole(x: float, y: float, radius: int) -> Ring:
    """A hole of ``radius`` nm at ``(x, y)`` mm, polygonised so that no chord leaves the circle by more than
    ``ARC_TOL_NM``, in the turn of ``box``."""
    count = max(8, math.ceil(math.pi / math.acos(1 - ARC_TOL_NM / radius)))
    cx, cy = round(x * MM), round(y * MM)
    return tuple(
        Point(
            cx + round(radius * math.cos(2 * math.pi * k / count)),
            cy + round(radius * math.sin(2 * math.pi * k / count)),
        )
        for k in range(count)
    )


def plane_board(holes: int, *, round: bool = False, net: str = "GND") -> Bench:  # noqa: A002
    """The plane bench of change c0503 (design D1): a 100 mm × 80 mm board, a zone of ``net`` filled on
    ``F.Cu`` and on ``B.Cu`` with ``holes`` clearance holes of 2 mm (squares, or circles with ``round``) in a
    grid over the middle 80 mm × 60 mm, 30 through vias and 20 SMD pads on ``F.Cu`` in the hole-free margin,
    and the through-hole pads ``J1-1`` at (3, 3) mm and ``U1-1`` at (97, 77) mm, 2 mm squares on both layers;
    a stack-up of 35 µm of copper on each side of 1.53 mm of laminate.
    Every number is illustrative, authored for Fenolite."""
    columns = math.ceil(math.sqrt(holes * 100 / 80))
    rows = math.ceil(holes / columns)
    rings: list[Ring] = []
    for index in range(holes):
        x = 10 + (index % columns + 0.5) * 80 / columns
        y = 10 + (index // columns + 0.5) * 60 / rows
        rings.append(_round_hole(x, y, MM) if round else box(x - 1, y - 1, x + 1, y + 1))
    made = Copper()
    both = ("F.Cu", "B.Cu")
    for layer in both:
        made.zone(net, PLANE, layer=layer, fills=(stored(PLANE, rings),), locator=f"/plane-{layer}")
    spots = [(15 + 8 * k, 6) for k in range(10)] + [(15 + 8 * k, 74) for k in range(10)]
    spots += [(6, 20 + 10 * k) for k in range(5)] + [(94, 20 + 10 * k) for k in range(5)]
    for index, (x, y) in enumerate(spots):
        made.via(net, at(x, y), locator=f"/via[{index}]")
    for index in range(20):
        x, y = 19 + 8 * (index % 10), (8.5 if index < 10 else 71.5)
        made.pad(f"C{index + 1}", "1", net, _rect(x - 0.5, y - 0.5, x + 0.5, y + 0.5))
    for ref, (x, y) in (("J1", (3, 3)), ("U1", (97, 77))):
        made.pad(
            ref,
            "1",
            net,
            *(_rect(x - 1, y - 1, x + 1, y + 1, layer) for layer in both),
            kind="thru_hole",
            layers=both,
        )
    design = made.build()
    assert design.board is not None
    entries = (("F.Cu", "copper", 35_000), ("core", "dielectric", 1_530_000), ("B.Cu", "copper", 35_000))
    layers = tuple(
        StackLayer(id=ident("stk", n), name=name, kind=kind, thickness=thickness)  # type: ignore[arg-type]
        for n, (name, kind, thickness) in enumerate(entries)
    )
    board = dataclasses.replace(design.board, stackup=Stackup(id=ident("stu", 1), layers=layers))
    return dataclasses.replace(design, board=board), tuple(made.pads)


# --- the grid cut: the oracle of the narrowest section (test code) ---------------------------------

CELL = 50_000
"""The pitch of the grid oracles: 0.05 mm."""
Cells = tuple[int, int, int, int]
"""A rectangle of grid cells: ``x0, y0, x1, y1`` in cells, the upper bounds excluded."""


def cells_ring(rect: Cells) -> Ring:
    x0, y0, x1, y1 = rect
    return (
        Point(x0 * CELL, y0 * CELL),
        Point(x1 * CELL, y0 * CELL),
        Point(x1 * CELL, y1 * CELL),
        Point(x0 * CELL, y1 * CELL),
    )


def _inside(cell: tuple[int, int], rect: Cells) -> bool:
    return rect[0] <= cell[0] < rect[2] and rect[1] <= cell[1] < rect[3]


def grid_cut(size: tuple[int, int], holes: Sequence[Cells], first: Cells, second: Cells) -> int:
    """The minimum cut, in cell edges, of the four-neighbour graph of the copper cells of a rectangle of
    ``size`` cells less ``holes``, between the cells of the port ``first`` and those of ``second``: the
    largest number of edge-disjoint paths, found by breadth-first augmentation."""
    copper = {
        (x, y)
        for x in range(size[0])
        for y in range(size[1])
        if not any(_inside((x, y), hole) for hole in holes)
    }
    sources = [cell for cell in sorted(copper) if _inside(cell, first)]
    sinks = {cell for cell in copper if _inside(cell, second)}
    flow: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
    total = 0
    while True:
        before: dict[tuple[int, int], tuple[int, int] | None] = dict.fromkeys(sources)
        queue = list(sources)
        reached: tuple[int, int] | None = None
        for cell in queue:
            if cell in sinks:
                reached = cell
                break
            x, y = cell
            for other in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if other in copper and other not in before and flow.get((cell, other), 0) < 1:
                    before[other] = cell
                    queue.append(other)
        if reached is None:
            return total
        total += 1
        while before[reached] is not None:
            previous = before[reached]
            assert previous is not None
            flow[(previous, reached)] = flow.get((previous, reached), 0) + 1
            flow[(reached, previous)] = flow.get((reached, previous), 0) - 1
            reached = previous


# --- the finite-difference solution: the oracle of the region bounds (test code, floats) -----------

Box = tuple[float, float, float, float]
"""A rectangle in millimetres: ``x0, y0, x1, y1``."""
FDM_PITCHES = (0.4, 0.2, 0.1, 0.05)
"""The grids of the solution, coarse to fine: each one starts from the one before it."""


def _fdm_level(
    pitch: float,
    copper: Sequence[Box],
    holes: Sequence[Box],
    first: Box,
    second: Box,
    guess: dict[tuple[int, int], float],
) -> tuple[float, dict[tuple[int, int], float]]:
    """Laplace's equation on the cells of pitch ``pitch`` whose centres lie in ``copper`` and in no hole,
    the cells of ``first`` held at 1 and those of ``second`` at 0: conjugate gradients from ``guess``.
    Returns the resistance in squares and the potential per cell."""

    def within(x: float, y: float, rect: Box) -> bool:
        return rect[0] < x < rect[2] and rect[1] < y < rect[3]

    x1 = max(rect[2] for rect in copper)
    y1 = max(rect[3] for rect in copper)
    cells: dict[tuple[int, int], int] = {}  # cell -> index of a free cell, −1 at 1 V, −2 at 0 V
    for i in range(round(x1 / pitch)):
        for j in range(round(y1 / pitch)):
            x, y = (i + 0.5) * pitch, (j + 0.5) * pitch
            if not any(within(x, y, rect) for rect in copper) or any(within(x, y, rect) for rect in holes):
                continue
            if within(x, y, first):
                cells[(i, j)] = -1
            elif within(x, y, second):
                cells[(i, j)] = -2
            else:
                cells[(i, j)] = 0
    free = [cell for cell, value in cells.items() if value == 0]
    for index, cell in enumerate(free):
        cells[cell] = index
    count = len(free)
    links: list[list[int]] = [[] for _ in range(count)]
    diagonal = [0.0] * count
    rhs = [0.0] * count
    for index, (i, j) in enumerate(free):
        for other in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            kind = cells.get(other)
            if kind is None:
                continue
            if kind >= 0:
                links[index].append(kind)
                diagonal[index] += 1.0
            else:  # a held cell: its face lies half a cell away, so the link conducts twice as well
                diagonal[index] += 2.0
                if kind == -1:
                    rhs[index] += 2.0
    v = [guess.get(cell, 0.5) for cell in free]

    def apply(vector: list[float]) -> list[float]:
        return [diagonal[k] * vector[k] - sum([vector[m] for m in links[k]]) for k in range(count)]

    product = apply(v)
    r = [rhs[k] - product[k] for k in range(count)]
    z = [r[k] / diagonal[k] for k in range(count)]
    d = z[:]
    rz = sum(a * b for a, b in zip(r, z, strict=True))
    start = rz
    for _ in range(4 * count):
        if rz <= 1e-8 * start or rz == 0.0:
            break
        product = apply(d)
        alpha = rz / sum(a * b for a, b in zip(d, product, strict=True))
        v = [a + alpha * b for a, b in zip(v, d, strict=True)]
        r = [a - alpha * b for a, b in zip(r, product, strict=True)]
        z = [r[k] / diagonal[k] for k in range(count)]
        new = sum(a * b for a, b in zip(r, z, strict=True))
        d = [a + (new / rz) * b for a, b in zip(z, d, strict=True)]
        rz = new
    potential = {cell: v[index] for index, cell in enumerate(free)}
    current = 0.0
    for (i, j), kind in cells.items():
        if kind != -1:
            continue
        for other in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if cells.get(other, -1) >= 0:
                current += 2.0 * (1.0 - potential[other])
            elif cells.get(other) == -2:
                current += 1.0
    return (1.0 / current if current else float("inf")), potential


def fdm_resistance(copper: Sequence[Box], holes: Sequence[Box], first: Box, second: Box) -> float:
    """The resistance, in squares (multiply by the sheet resistance), of the copper made of the
    rectangles ``copper`` less ``holes`` between the pads ``first`` and ``second`` held at one potential
    each: Laplace's equation on a 0.05 mm grid, each grid started from the coarser one."""
    guess: dict[tuple[int, int], float] = {}
    squares = float("inf")
    for pitch in FDM_PITCHES:
        squares, potential = _fdm_level(pitch, copper, holes, first, second, guess)
        guess = {
            (2 * i + di, 2 * j + dj): value
            for (i, j), value in potential.items()
            for di in (0, 1)
            for dj in (0, 1)
        }
    return squares


__all__ = [
    "fdm_resistance",
    "CELL",
    "Cells",
    "cells_ring",
    "grid_cut",
    "DUMBBELL",
    "MM",
    "SPLIT4",
    "SPLIT4_HOLE",
    "SPOKE_HOLES",
    "SQUARE20",
    "STRIP",
    "Bench",
    "branch",
    "neck_board",
    "plane_board",
    "strip",
    "two_strips",
    "via_array",
    "written_strip",
    "dumbbell",
    "neck_outer",
    "pour_board",
    "region",
    "split4",
    "spokes",
    "stored",
]
