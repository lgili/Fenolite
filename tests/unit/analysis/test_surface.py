# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The surface search: hand-computed cases and the comparison with a grid search (capability
board-analyses, "Creepage on the board surface" and "Clearance across the board edge"; change c0047)."""

from __future__ import annotations

import random

from _analysis import MM, NOTCH_OUTER, SLOT, SLOT_OUTER, at, box, edge_board, grid_shortest

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.report import DistanceRow
from fenolite.analysis.surface import Terminal, boundary_distance, surface_distance, usable_terminals
from fenolite.core.coords import Point
from fenolite.geometry import Thick

STEP = 100_000


def disc(x: float, y: float, face: str = "top", width: int = MM) -> Terminal:
    return Terminal(Thick((at(x, y),), width), face)  # type: ignore[arg-type]


def slotted(thickness: int | None = None) -> BoardBoundary:
    return BoardBoundary(SLOT_OUTER, (SLOT,), thickness, 0, "model")


def test_around_a_slot() -> None:
    path = surface_distance([disc(0, 0)], [disc(10, 0)], slotted())
    assert path is not None and (path.length, path.band) == (11_000_000, 0)
    assert [point for point, _ in path.points] == [at(0, 0), at(4, 3), at(6, 3), at(10, 0)]
    assert {face for _, face in path.points} == {"top"}


def test_slot_orientation_and_ring_start_do_not_matter() -> None:
    for outer in (SLOT_OUTER, tuple(reversed(SLOT_OUTER))):
        for slot in (SLOT, tuple(reversed(SLOT)), (*SLOT[2:], *SLOT[:2])):
            path = surface_distance(
                [disc(0, 0)], [disc(10, 0)], BoardBoundary(outer, (slot,), None, 0, "model")
            )
            assert path is not None and path.length == 11_000_000


def test_notch_open_to_the_board_edge() -> None:
    path = surface_distance([disc(0, 0)], [disc(10, 0)], BoardBoundary(NOTCH_OUTER, (), None, 0, "model"))
    assert path is not None and path.length == 11_000_000
    assert [point for point, _ in path.points][1:3] == [at(4, 3), at(6, 3)]


def test_limit_stops_the_search() -> None:
    assert surface_distance([disc(0, 0)], [disc(10, 0)], slotted(), limit=10_000_000) is None
    assert surface_distance([disc(0, 0)], [disc(10, 0)], slotted(), limit=11_000_000) is None
    path = surface_distance([disc(0, 0)], [disc(10, 0)], slotted(), limit=11_000_001)
    assert path is not None and path.length == 11_000_000


def test_unbounded_plane_without_a_boundary() -> None:
    for boundary in (None, BoardBoundary()):
        path = surface_distance([disc(0, 0)], [disc(10, 0)], boundary)
        assert path is not None and path.length == 9_000_000
        assert surface_distance([disc(0, 0)], [disc(10, 0, "bottom")], boundary) is None


def test_overlapping_conductors_have_no_path_length() -> None:
    path = surface_distance([disc(0, 0)], [disc(0.5, 0)], slotted())
    assert path is not None and path.length == 0
    filled = Terminal(Thick(box(-1, -1, 1, 1), 0, filled=True), "top")
    inside = surface_distance([filled], [disc(0, 0, width=2)], slotted())
    assert inside is not None and inside.length == 0


def test_the_nearest_terminal_is_named() -> None:
    a = [disc(-5, 5), disc(0, 0)]
    b = [disc(10, 0), disc(15, 5)]
    path = surface_distance(a, b, slotted())
    assert path is not None and path.ends == (1, 0)


def test_bands_are_carried() -> None:
    banded = BoardBoundary(SLOT_OUTER, (SLOT,), None, 5_001, "edge")
    a = [Terminal(Thick((at(0, 0),), MM), "top", 1_001)]
    path = surface_distance(a, [disc(10, 0)], banded)
    assert path is not None and path.band == 2 * 5_001 + 1_001


def test_terminal_outside_the_board_is_left_out() -> None:
    kept, lost = usable_terminals([disc(0, 0), disc(5, 0), disc(40, 0)], slotted())
    assert lost == 2 and [t.shape.core for t in kept] == [(at(0, 0),)]
    assert surface_distance([disc(5, 0)], [disc(10, 0)], slotted()) is None
    assert usable_terminals([disc(40, 0)], None) == ((disc(40, 0),), 0)


# --- walls ------------------------------------------------------------------------------------------


def test_edge_track_above_track() -> None:
    design, boundary = edge_board()
    report = analyze_distances(design, pads=None, boundary=boundary, pairs=(("A", "B"),))
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None and row.clearance is not None
    assert row.creepage.low == 5_100_000
    assert (row.clearance.low, row.clearance.high, row.clearance.layer) == (5_100_000, 5_100_002, "F.Cu/B.Cu")
    assert row.gaps == () and report.issues == ()
    assert row.creepage.points == (at(5, 2), at(5, 0), at(5, 0), at(5, 2))


def test_edge_thickness_unknown() -> None:
    design, boundary = edge_board(thickness=None)
    report = analyze_distances(design, pads=None, boundary=boundary, pairs=(("A", "B"),))
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.clearance is None and row.creepage is None
    (found,) = report.issues
    assert found.code == "analysis.input-missing" and found.where == "board thickness"


def test_edge_outline_unknown() -> None:
    design, _ = edge_board()
    report = analyze_distances(design, pads=None, boundary=None, pairs=(("A", "B"),))
    (found,) = report.issues
    assert found.code == "analysis.input-missing" and found.where == "board outline"


def test_edge_drop_at_a_vertex_and_crossing_of_an_edge() -> None:
    rect = BoardBoundary(box(0, 0, 20, 10), (), 1_600_000, 0, "model")
    # the same point on both faces, 2 mm from two edges: straight to the nearer edge and back
    path = surface_distance([disc(2, 3, width=2)], [disc(2, 3, "bottom", 2)], rect)
    assert path is not None and path.length == 2 * 2 * MM + 1_600_000 - 2
    # conductors on the corner: the drop at the vertex is the whole path
    corner = surface_distance([disc(0, 0, width=2)], [disc(0, 0, "bottom", 2)], rect)
    assert corner is not None and corner.length == 1_600_000
    # a slanted path through the edge, straight in the unfolded plane: a 3-4-5 triangle
    slanted = surface_distance([disc(4, 1.2, width=2)], [disc(7, 1.2, "bottom", 2)], rect)
    assert slanted is not None and slanted.length == 5 * MM - 2


def test_edge_slot_wall_does_not_bridge_the_slot() -> None:
    """Copper on opposite faces on the two sides of a slot. A wall of the slot joins the two faces on one
    side of it, so the path still goes around the slot: 11 mm, plus one drop of the thickness."""
    path = surface_distance([disc(0, 0)], [disc(10, 0, "bottom")], slotted(1_600_000))
    assert path is not None and path.length == 11_000_000 + 1_600_000
    faces = [face for _, face in path.points]
    assert faces[0] == "top" and faces[-1] == "bottom"


def test_edge_on_a_slanted_boundary() -> None:
    """A diamond-shaped board: the normal of every edge is irrational, and the result stays within 2 nm of
    the hand value."""
    diamond = BoardBoundary((at(0, -10), at(10, 0), at(0, 10), at(-10, 0)), (), 1_000_000, 0, "model")
    path = surface_distance([disc(0, 0, width=2)], [disc(0, 0, "bottom", 2)], diamond)
    assert path is not None
    # the centre is 10/√2 mm from every edge: twice that, plus the thickness
    exact = 2 * 7_071_067.811865475 + 1_000_000 - 2
    assert exact - 2 <= path.length <= exact


def test_boundary_distance() -> None:
    rect = BoardBoundary(box(0, 0, 20, 10), (), None, 0, "model")
    assert boundary_distance(Thick((at(5, 2), at(15, 2)), 500_000), rect) == 1_750_000
    assert boundary_distance(Thick((at(5, 2),), 6 * MM), rect) == 0
    assert boundary_distance(Thick(box(-1, -1, 30, 30), 0, filled=True), rect) == 0


# --- the grid comparison ----------------------------------------------------------------------------


def generated(seed: int) -> tuple[tuple[Point, Point], list[tuple[Point, Point]], Point, Point]:
    """A rectangular board with up to three rectangular cut-outs and two points, all on a 0.1 mm grid."""
    rng = random.Random(seed)
    width, height = rng.randint(30, 60), rng.randint(20, 40)
    outer = (Point(0, 0), Point(width * STEP, height * STEP))
    holes: list[tuple[Point, Point]] = []
    for _ in range(rng.randint(0, 3)):
        x0, y0 = rng.randint(1, width - 6), rng.randint(1, height - 6)
        x1, y1 = rng.randint(x0 + 1, min(width - 1, x0 + 25)), rng.randint(y0 + 1, min(height - 1, y0 + 25))
        holes.append((Point(x0 * STEP, y0 * STEP), Point(x1 * STEP, y1 * STEP)))

    def free() -> Point:
        while True:
            point = Point(rng.randint(0, width) * STEP, rng.randint(0, height) * STEP)
            if not any(low.x < point.x < high.x and low.y < point.y < high.y for low, high in holes):
                return point

    return outer, holes, free(), free()


def test_grid_agreement_on_generated_boards() -> None:
    compared = bent = 0
    for seed in range(120):
        outer, holes, start, goal = generated(seed)
        if start == goal:
            continue
        ring = (outer[0], Point(outer[1].x, outer[0].y), outer[1], Point(outer[0].x, outer[1].y))
        cutouts = tuple((low, Point(high.x, low.y), high, Point(low.x, high.y)) for low, high in holes)
        boundary = BoardBoundary(ring, cutouts, None, 0, "model")
        a, b = [Terminal(Thick((start,), 2), "top")], [Terminal(Thick((goal,), 2), "top")]
        path = surface_distance(a, b, boundary)
        grid = grid_shortest(start, goal, outer, holes, STEP)
        assert (path is None) == (grid is None), seed
        if path is None or grid is None:
            continue
        length = path.length + 2  # the two half widths of the discs
        assert length <= grid + 1, (seed, length, grid)
        assert length * 100 >= grid * 92, (seed, length, grid)
        compared += 1
        bent += len(path.points) > 2
    assert compared > 100 and bent > 20


def test_walls_are_symmetric_on_generated_boards() -> None:
    """With walls: swapping the two conductors, or the two faces, gives the same length; a limit just above
    the length changes nothing; and a path across the faces is never shorter than the thickness."""
    thickness = 800_000
    crossed = 0
    for seed in range(60):
        outer, holes, start, goal = generated(seed)
        ring = (outer[0], Point(outer[1].x, outer[0].y), outer[1], Point(outer[0].x, outer[1].y))
        cutouts = tuple((low, Point(high.x, low.y), high, Point(low.x, high.y)) for low, high in holes)
        boundary = BoardBoundary(ring, cutouts, thickness, 0, "model")

        def terminal(point: Point, face: str) -> list[Terminal]:
            return [Terminal(Thick((point,), 2), face)]  # type: ignore[arg-type]

        forward = surface_distance(terminal(start, "top"), terminal(goal, "bottom"), boundary)
        assert forward is not None, seed
        backward = surface_distance(terminal(goal, "bottom"), terminal(start, "top"), boundary)
        mirrored = surface_distance(terminal(start, "bottom"), terminal(goal, "top"), boundary)
        assert backward is not None and mirrored is not None
        assert forward.length == backward.length == mirrored.length, seed
        assert forward.length >= thickness - 2
        limited = surface_distance(
            terminal(start, "top"), terminal(goal, "bottom"), boundary, limit=forward.length + 1
        )
        assert limited is not None and limited.length == forward.length, seed
        assert (
            surface_distance(terminal(start, "top"), terminal(goal, "bottom"), boundary, limit=forward.length)
            is None
        ), seed
        points = forward.points
        crossed += len(points) == 4 and points[1][0] != points[2][0]  # through an edge, not at a vertex
    assert crossed > 5


def test_round_board_is_searched_in_seconds() -> None:
    """A round board with a round hole has about 190 boundary vertices; the search prunes by the distance
    in plan view and stays fast."""
    import time

    from fenolite.geometry import Circle

    ring = tuple(Circle.from_radius(at(5, 0), 15 * MM).polygonize(5_000))
    hole = tuple(Circle.from_radius(at(5, 0), 2 * MM).polygonize(5_000))
    boundary = BoardBoundary(ring, (hole,), 1_600_000, 5_001, "edge")
    a = [disc(0, 0), disc(0, 0, "bottom")]
    b = [disc(10, 0), disc(10, 0, "bottom")]
    started = time.perf_counter()
    path = surface_distance(a, b, boundary)
    assert time.perf_counter() - started < 30
    # around the hole of radius 2 mm: two tangents of √21 mm and an arc, less the two half widths
    assert path is not None and 9_800_000 < path.length < 9_820_000
    assert path.band == 5_001 * (len(path.points) - 2)
