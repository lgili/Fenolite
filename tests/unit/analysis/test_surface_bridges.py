# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Creepage and clearance over conductors (capability board-analyses, "Creepage over conductors" and the
bridges of "Creepage on the board surface"; ``H-G-AN-OVER``)."""

from __future__ import annotations

import dataclasses
import random

from _analysis import MM, at, box, edge_board, grid_shortest, with_outline
from _coppercheck import Copper, ident

from fenolite.analysis import analyze_distances, board_boundary
from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.copper import loose_copper, net_copper
from fenolite.analysis.report import AnalysisReport, DistanceRow
from fenolite.analysis.surface import BRIDGE_EVIDENCE, Terminal, surface_distance
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.geometry import Thick
from fenolite.model.board import Graphic

OUTER = box(-10, -10, 20, 10)
PAIR = (("A", "B"),)
STEP = 100_000


def tracks() -> Copper:
    """A 1 mm track of ``A`` from (−2 mm, 0) to (0, 0) and one of ``B`` from (10 mm, 0) to (12 mm, 0)."""
    made = Copper()
    made.track("A", at(-2, 0), at(0, 0), width=MM, locator="/a")
    made.track("B", at(10, 0), at(12, 0), width=MM, locator="/b")
    return made


def analysed(made: Copper) -> tuple[DistanceRow, AnalysisReport]:
    design = with_outline(made.build(), OUTER)
    assert design.board is not None
    report = analyze_distances(design, pads=None, boundary=board_boundary(design.board), pairs=PAIR)
    (row,) = report.rows
    assert isinstance(row, DistanceRow)
    return row, report


def test_a_conductor_is_crossed_at_no_length() -> None:
    """Scenario "A conductor is crossed at no length"."""
    boundary = BoardBoundary(OUTER, (), None, 0, "model")
    a = [Terminal(Thick((at(-2, 0), at(0, 0)), MM), "top")]
    b = [Terminal(Thick((at(10, 0), at(12, 0)), MM), "top")]
    bridge = Terminal(Thick((at(5, -2), at(5, 2)), MM), "top")
    plain = surface_distance(a, b, boundary)
    assert plain is not None and plain.length == 9 * MM and plain.over == ()
    path = surface_distance(a, b, boundary, bridges=[bridge])
    assert path is not None and path.length == 8 * MM and path.over == (0,) and path.ends == (0, 0)
    assert [point for point, _ in path.points] == [at(0, 0), at(5, 0), at(10, 0)]
    # a conductor beside the line does not help, and a limit still stops the search
    beside = Terminal(Thick((at(5, 6), at(5, 9)), MM), "top")
    away = surface_distance(a, b, boundary, bridges=[beside])
    assert away is not None and away.length == 9 * MM and away.over == ()
    assert surface_distance(a, b, boundary, bridges=[bridge], limit=8 * MM) is None
    # a conductor on the other face only is no bridge without a wall
    below = Terminal(Thick((at(5, -2), at(5, 2)), MM), "bottom")
    assert surface_distance(a, b, boundary, bridges=[below]) == plain
    assert BRIDGE_EVIDENCE.level is Level.INFERRED and BRIDGE_EVIDENCE.hypotheses == ("H-G-AN-OVER",)


def test_a_through_via_joins_the_faces() -> None:
    """Scenario "A through via joins the faces": 1.45 mm on each face to the pad of the via."""
    design, boundary = edge_board()
    assert design.board is not None
    plain = analyze_distances(design, pads=None, boundary=boundary, pairs=PAIR).rows[0]
    assert isinstance(plain, DistanceRow) and plain.creepage is not None and plain.creepage.low == 5_100_000
    made = Copper()
    made.track("A", at(5, 2), at(15, 2), width=500_000, layer="F.Cu")
    made.track("B", at(5, 2), at(15, 2), width=500_000, layer="B.Cu")
    made.via(None, at(10, 4), diameter=600_000, locator="/loose-via")
    joined = with_outline(made.build(), box(0, 0, 20, 10))
    report = analyze_distances(joined, pads=None, boundary=boundary, pairs=PAIR)
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None and row.clearance is not None
    assert row.creepage.low == 2_900_000 and row.creepage.over == ("/loose-via",)
    assert row.clearance.low == 2_900_000 and row.clearance.over == ("/loose-via",)
    assert row.creepage.layer == "F.Cu/B.Cu" and not report.issues
    # the same without a board thickness: the via is the only way from one face to the other
    thin = dataclasses.replace(boundary, thickness=None)
    alone = analyze_distances(joined, pads=None, boundary=thin, pairs=PAIR).rows[0]
    assert isinstance(alone, DistanceRow) and alone.creepage is not None and alone.creepage.low == 2_900_000


def test_floating_via_and_floating_track() -> None:
    """Scenarios "A floating via" and "A floating track shortens the clearance"."""
    made = tracks()
    made.via(None, at(5, 0), diameter=MM, locator="/via")
    row, report = analysed(made)
    assert row.creepage is not None and row.clearance is not None
    assert row.creepage.low == 8 * MM and row.creepage.over == ("/via",)
    assert row.clearance.low == 8 * MM and not report.issues
    assert "H-G-AN-OVER" in report.evidence.hypotheses and report.evidence.level is Level.INFERRED
    made = tracks()
    made.track(None, at(5, -2), at(5, 2), width=MM, locator="/floating")
    row, report = analysed(made)
    assert row.clearance is not None and row.creepage is not None
    (gap,) = row.gaps
    assert gap.layer == "F.Cu" and gap.low == 9 * MM
    assert (row.clearance.low, row.clearance.high) == (8 * MM, 8 * MM + 2)
    assert row.clearance.over == ("/floating",) and row.creepage.over == ("/floating",)
    assert len(loose_copper(made.build(), pads=None)) == 1
    assert all(
        shape.where != "/floating"
        for shapes in net_copper(made.build(), pads=None).by_net.values()
        for shape in shapes
    )


def test_a_third_net_is_named() -> None:
    """Scenario "A third net"."""
    made = tracks()
    made.track("C", at(5, -2), at(5, 2), width=MM, locator="/c")
    row, report = analysed(made)
    assert row.creepage is not None and row.creepage.low == 8 * MM and row.creepage.over == ("/c",)
    (found,) = report.issues
    assert (found.code, found.severity, found.where) == ("analysis.creepage-over", "info", "A, B")
    assert " C " in found.message and "A and C" in found.hint and "B and C" in found.hint
    assert report.evidence.level is Level.INFERRED
    # the pairs with the third net are measured without it
    design = with_outline(made.build(), OUTER)
    assert design.board is not None
    halves = analyze_distances(
        design, pads=None, boundary=board_boundary(design.board), pairs=(("A", "C"), ("B", "C"))
    )
    assert [r.creepage.low for r in halves.rows if isinstance(r, DistanceRow) and r.creepage] == [
        4 * MM,
        4 * MM,
    ]
    assert not halves.issues


def test_a_copper_graphic_is_counted() -> None:
    design = with_outline(tracks().build(), OUTER)
    assert design.board is not None
    line = Graphic(id=ident("gra", 1), kind="line", layer="F.Cu", points=(at(5, -2), at(5, 2)), width=MM)
    drawn = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=(line,)))
    report = analyze_distances(drawn, pads=None, boundary=board_boundary(design.board), pairs=PAIR)
    (found,) = report.issues
    assert (found.code, found.where) == (
        "analysis.item-unsupported",
        "graphic",
    ) and "1 graphic" in found.message
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None and row.creepage.low == 9 * MM
    assert report.evidence.level is Level.UNVERIFIED


def test_grid_agreement_over_conductors() -> None:
    """Scenario "Agreement with a grid search over conductors": the conductors' cells cost nothing."""
    compared = crossed = 0
    for seed in range(200):
        rng = random.Random(seed)
        width, height = rng.randint(30, 60), rng.randint(20, 40)
        outer = (Point(0, 0), Point(width * STEP, height * STEP))
        rects: list[tuple[Point, Point]] = []
        for _ in range(rng.randint(1, 5)):
            x0, y0 = rng.randint(1, width - 6), rng.randint(1, height - 6)
            x1, y1 = (
                rng.randint(x0 + 1, min(width - 1, x0 + 20)),
                rng.randint(y0 + 1, min(height - 1, y0 + 20)),
            )
            candidate = (Point(x0 * STEP, y0 * STEP), Point(x1 * STEP, y1 * STEP))
            if all(
                candidate[1].x < low.x - STEP or high.x + STEP < candidate[0].x
                or candidate[1].y < low.y - STEP or high.y + STEP < candidate[0].y
                for low, high in rects
            ):  # fmt: skip
                rects.append(candidate)
        holes, conductors = rects[: len(rects) // 2 + 1][:3], rects[len(rects) // 2 + 1 :][:2]

        ends: list[Point] = []
        while len(ends) < 2:
            point = Point(rng.randint(0, width) * STEP, rng.randint(0, height) * STEP)
            if not any(low.x <= point.x <= high.x and low.y <= point.y <= high.y for low, high in rects):
                ends.append(point)
        start, goal = ends
        ring = (outer[0], Point(outer[1].x, outer[0].y), outer[1], Point(outer[0].x, outer[1].y))
        cutouts = tuple((low, Point(high.x, low.y), high, Point(low.x, high.y)) for low, high in holes)
        boundary = BoardBoundary(ring, cutouts, None, 0, "model")
        a, b = [Terminal(Thick((start,), 2), "top")], [Terminal(Thick((goal,), 2), "top")]
        bridges = [
            Terminal(Thick((low, Point(high.x, low.y), high, Point(low.x, high.y)), 0, filled=True), "top")
            for low, high in conductors
        ]
        path = surface_distance(a, b, boundary, bridges=bridges)
        grid = grid_shortest(start, goal, outer, holes, STEP, conductors)
        assert (path is None) == (grid is None), seed
        if path is None or grid is None:
            continue
        length = path.length + 2  # the two half widths of the discs
        assert length <= grid + 1, (seed, length, grid)
        assert length * 100 >= grid * 92, (seed, length, grid)
        compared += 1
        crossed += bool(path.over)
    assert compared > 150 and crossed > 10
