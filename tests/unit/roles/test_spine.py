# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The spine trees of the role copper (change c0243, decision 3): rectilinear paths at a band's width around
obstacles, the grid search for narrow channels, trees in Prim's order with given edges first."""

from __future__ import annotations

from fenolite.core.coords import Point
from fenolite.geometry import Thick
from fenolite.roles.spine import (
    Edge,
    Obstacles,
    Terminal,
    chain,
    ends_hold,
    free_path,
    route,
    search,
    slab,
    tree,
)

MM = 1_000_000


def _at(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def _box(x0: float, y0: float, x1: float, y1: float) -> Thick:
    return Thick((_at(x0, y0), _at(x1, y0), _at(x1, y1), _at(x0, y1)), 0, filled=True)


def test_a_straight_run_when_nothing_is_in_the_way() -> None:
    path = route(
        Terminal("a", _at(0, 0)), Terminal("b", _at(10, 0)), width=MM, step=MM // 2, obstacles=Obstacles([])
    )
    assert path == (_at(-0.5, 0), _at(10.5, 0))  # ends without copper reach half a width past the points


def test_an_l_around_a_block() -> None:
    wall = Obstacles([(_box(4, -3, 6, 3), 300_000)])
    path = route(Terminal("a", _at(0, 0)), Terminal("b", _at(10, 6)), width=MM, step=MM // 2, obstacles=wall)
    assert path is not None and len(path) == 3
    assert free_path(path, MM, wall)


def test_the_grid_search_finds_a_narrow_channel() -> None:
    """Two blocks leave a 1.8 mm channel from x = 4.5 mm: only there a band 1 mm wide keeps 0.3 mm gaps."""
    walls = Obstacles([(_box(-20, 2, 4.5, 4), 300_000), (_box(6.3, 2, 30, 4), 300_000)])
    found = search(
        Terminal("a", _at(0, 0)),
        Terminal("b", _at(10, 8)),
        width=MM,
        step=MM // 2,
        obstacles=walls,
        turn=2 * MM,
    )
    assert found is not None and free_path(found, MM, walls)
    assert any(4_800_000 <= p.x <= 5_500_000 for p in found)


def test_no_path_is_none() -> None:
    walls = Obstacles([(_box(-30, 2, 30, 4), 300_000)])
    found = route(
        Terminal("a", _at(0, 0)),
        Terminal("b", _at(0, 8)),
        width=MM,
        step=MM // 2,
        obstacles=walls,
        bounds=None,
    )
    assert found is None


def test_a_tree_keeps_its_given_edges_and_reports_a_blocked_terminal() -> None:
    walls = Obstacles([(_box(18, -30, 22, 30), 300_000)])
    terminals = [
        Terminal("a", _at(0, 0)),
        Terminal("b", _at(5, 0)),
        Terminal("c", _at(5, 5)),
        Terminal("d", _at(30, 0)),
    ]
    given = [Edge("a", "b", (_at(0, 0), _at(5, 0)))]

    def edge(a: Terminal, b: Terminal) -> tuple[Point, ...] | None:
        return route(a, b, width=MM, step=MM // 2, obstacles=walls)

    built = tree(terminals, edge, given=given)
    assert built.edges[0] == given[0]
    assert {(e.a, e.b) for e in built.edges[1:]} == {("b", "c")}
    assert [pair[1] for pair in built.blocked] == ["d"]


def test_chains_and_ends() -> None:
    joined = chain([Edge("a", "b", (_at(0, 0), _at(5, 0))), Edge("b", "c", (_at(5, 0), _at(5, 5)))])
    assert joined == (_at(0, 0), _at(5, 0), _at(5, 5))
    star = [
        Edge("a", "b", (_at(0, 0), _at(5, 0))),
        Edge("a", "c", (_at(0, 0), _at(0, 5))),
        Edge("a", "d", (_at(0, 0), _at(-5, 0))),
    ]
    assert chain(star) is None
    assert not ends_hold((_at(0, 0), _at(0, 0.3), _at(5, 0.3)), MM)
    assert ends_hold((_at(0, 0), _at(0, 3), _at(5, 3)), MM)


def test_a_slab_reaches_past_a_joint_not_past_an_end() -> None:
    inner = slab(_at(0, 0), _at(4, 0), MM)
    end = slab(_at(0, 0), _at(4, 0), MM, start=False, end=False)
    assert {p.x for p in inner.core} == {-500_000, 4_500_000}
    assert {p.x for p in end.core} == {0, 4_000_000}
