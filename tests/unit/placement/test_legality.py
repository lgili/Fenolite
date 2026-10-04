# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement legality on authored rings (capability placement, "Placement legality"; change c0022)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.base import PlacedExtent
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.frame import placed_extent
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point
from fenolite.geometry import Polygon, polygons_intersect
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector
from fenolite.placement import TOUCHING_OVERLAPS, check
from fenolite.placement.legality import (
    edge_clearance,
    interiors_intersect,
    ring_enters,
    ring_inside,
    rings_overlap,
)

ROOT = Path(__file__).resolve().parents[3]
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
LIBS = ROOT / "tests" / "data" / "libs"
MM = 1_000_000
Ring = tuple[Point, ...]


def rect(x0: float, y0: float, x1: float, y1: float) -> Ring:
    a, b, c, d = round(x0 * MM), round(y0 * MM), round(x1 * MM), round(y1 * MM)
    return (Point(a, b), Point(c, b), Point(c, d), Point(a, d))


def extent(name: str, *front: Ring, back: tuple[Ring, ...] = (), exact: bool = True) -> PlacedExtent:
    side = "top" if front or not back else "bottom"
    return PlacedExtent(name, side, front=tuple(front), back=back, source="courtyard", exact=exact)


BOARD = rect(0, 0, 50, 30)
EVERY = Selector("all")
NAMES = {"a": "R1", "b": "D1", "c": "U1"}


def codes(issues: tuple[object, ...]) -> list[tuple[str, str]]:
    return [(i.code, i.where) for i in issues]  # type: ignore[attr-defined]


# --- the predicates -----------------------------------------------------------------------------------


def test_legality_interiors_of_touching_rings_do_not_intersect() -> None:
    a = rect(0, 0, 6, 6)
    assert not interiors_intersect(a, rect(6, 0, 12, 6))  # a shared edge
    assert not interiors_intersect(a, rect(6, 6, 12, 12))  # a shared corner
    assert not interiors_intersect(a, rect(6, 2, 12, 4))  # a part of an edge
    assert not interiors_intersect(a, rect(7, 0, 9, 6))  # apart
    assert interiors_intersect(a, rect(5.98, 0, 12, 6))  # 20 µm
    assert interiors_intersect(a, rect(2, 2, 4, 4)) and interiors_intersect(rect(2, 2, 4, 4), a)  # nested
    assert interiors_intersect(a, a)  # the same region
    assert interiors_intersect(a, rect(0, 0, 3, 6))  # inside, sharing three edges
    assert interiors_intersect(a, rect(3, 0, 6, 6)) and interiors_intersect(a, rect(0, 2, 6, 4))


def test_legality_crossing_through_vertices_is_an_overlap() -> None:
    """A diamond whose corners lie on the square's edges: no edge crosses properly."""
    square = rect(0, 0, 4, 4)
    diamond = (Point(2 * MM, 0), Point(4 * MM, 2 * MM), Point(2 * MM, 4 * MM), Point(0, 2 * MM))
    assert interiors_intersect(square, diamond) and interiors_intersect(diamond, square)
    wedge = (Point(4 * MM, 4 * MM), Point(8 * MM, 2 * MM), Point(8 * MM, 6 * MM))  # touches one corner
    assert not interiors_intersect(square, wedge)
    through = (Point(2 * MM, 2 * MM), Point(4 * MM, 4 * MM), Point(6 * MM, 2 * MM))  # an edge ends inside
    assert interiors_intersect(square, through)
    concave = (Point(0, 0), Point(6 * MM, 0), Point(6 * MM, 6 * MM), Point(3 * MM, 2 * MM), Point(0, 6 * MM))
    assert not interiors_intersect(concave, rect(2, 4, 4, 6))  # in the notch, touching nothing
    notch = (Point(3 * MM, 2 * MM), Point(5 * MM, 6 * MM), Point(1 * MM, 6 * MM))  # its tip on the vertex
    assert not interiors_intersect(concave, notch)


def test_legality_touching_can_count_as_overlap() -> None:
    a, b = rect(0, 0, 6, 6), rect(6, 6, 12, 12)
    assert not rings_overlap(a, b, touching_overlaps=False)
    assert rings_overlap(a, b, touching_overlaps=True)
    assert not rings_overlap(a, rect(7, 7, 9, 9), touching_overlaps=True)


coordinate = st.integers(min_value=0, max_value=12)


@st.composite
def boxes(draw: st.DrawFn) -> Ring:
    x0, y0 = draw(coordinate), draw(coordinate)
    w, h = draw(st.integers(min_value=1, max_value=6)), draw(st.integers(min_value=1, max_value=6))
    return rect(x0, y0, x0 + w, y0 + h)


@given(boxes(), boxes())
def test_legality_interiors_agree_with_boxes(a: Ring, b: Ring) -> None:
    open_overlap = a[0].x < b[2].x and b[0].x < a[2].x and a[0].y < b[2].y and b[0].y < a[2].y
    assert interiors_intersect(a, b) == open_overlap
    assert interiors_intersect(b, a) == open_overlap
    assert rings_overlap(a, b, touching_overlaps=True) == polygons_intersect(Polygon(a), Polygon(b))


def test_legality_inside_and_cutouts() -> None:
    assert ring_inside(rect(1, 1, 5, 5), BOARD) and ring_inside(rect(0, 0, 5, 5), BOARD)  # touching is inside
    assert ring_inside(BOARD, BOARD)
    assert not ring_inside(rect(48, 10, 52, 12), BOARD) and not ring_inside(rect(60, 0, 62, 2), BOARD)
    hole = rect(20, 10, 30, 20)
    assert ring_enters(rect(22, 12, 24, 14), hole) and ring_enters(rect(28, 12, 32, 14), hole)
    assert ring_enters(hole, hole)
    assert not ring_enters(rect(30, 10, 34, 14), hole)  # shares an edge
    assert not ring_enters(rect(15, 5, 35, 25), hole)  # the cut-out lies wholly inside the ring
    l_board = (Point(0, 0), Point(20 * MM, 0), Point(20 * MM, 10 * MM), Point(10 * MM, 10 * MM),
               Point(10 * MM, 20 * MM), Point(0, 20 * MM))  # fmt: skip
    assert ring_inside(rect(1, 1, 19, 9), l_board) and ring_inside(rect(0, 0, 10, 20), l_board)
    assert not ring_inside(rect(5, 5, 15, 15), l_board)  # every vertex inside or on, one corner region out
    assert not ring_inside(rect(8, 8, 12, 12), l_board)


# --- check ------------------------------------------------------------------------------------------


def test_legality_overlap_named() -> None:
    found = check(
        [
            extent("a", rect(10, 10, 16, 16)),
            extent("b", rect(15.98, 10, 22, 16)),
            extent("c", rect(30, 10, 36, 16)),
        ],
        [BOARD],
        names=NAMES,
    )
    assert codes(found) == [("place.courtyard-overlap", "D1,R1")]
    assert found[0].severity == "error" and "D1 and R1" in found[0].message
    assert "approximate" not in found[0].message


def test_legality_touching_pairs_follow_the_switch() -> None:
    layout = [
        extent("a", rect(10, 10, 16, 16)),
        extent("b", rect(16, 10, 22, 16)),
        extent("c", rect(22, 16, 28, 22)),
    ]
    assert check(layout, [BOARD], names=NAMES) == ()
    strict = check(layout, [BOARD], names=NAMES, touching_overlaps=True)
    assert codes(strict) == [("place.courtyard-overlap", "D1,R1"), ("place.courtyard-overlap", "D1,U1")]


def test_legality_opposite_faces_do_not_overlap() -> None:
    ring = rect(10, 10, 16, 16)
    layout = [extent("a", ring), extent("b", back=(ring,))]
    assert layout[1].side == "bottom"
    assert check(layout, [BOARD], names=NAMES) == ()
    both = [extent("a", ring, back=(rect(10, 10, 12, 12),)), extent("b", back=(ring,))]
    assert codes(check(both, [BOARD], names=NAMES)) == [("place.courtyard-overlap", "D1,R1")]


def test_legality_outside_the_outline_and_in_a_cutout() -> None:
    cutout = rect(20, 10, 30, 20)
    layout = [
        extent("a", rect(48, 5, 52, 8)),
        extent("b", rect(22, 12, 26, 16)),
        extent("c", rect(2, 2, 8, 8)),
    ]
    found = check(layout, [BOARD, cutout], names=NAMES)
    assert codes(found) == [("place.outside-outline", "D1"), ("place.outside-outline", "R1")]
    assert "cut-out" in found[0].message and "leaves the board outline" in found[1].message
    assert all(i.severity == "error" for i in found)


def test_legality_edge_clearance() -> None:
    layout = [extent("a", rect(0.2, 5, 4, 8)), extent("b", rect(10, 10, 14, 14))]
    found = check(layout, [BOARD], names=NAMES, edge_clearance=500_000)
    assert codes(found) == [("place.edge-clearance", "R1")] and found[0].severity == "warning"
    assert check(layout, [BOARD], names=NAMES, edge_clearance=0) == ()
    assert check(layout, [BOARD], names=NAMES, edge_clearance=200_000) == ()  # exactly at the limit
    near_hole = check(layout, [BOARD, rect(14.3, 10, 16, 14)], names=NAMES, edge_clearance=500_000)
    assert codes(near_hole) == [("place.edge-clearance", "D1"), ("place.edge-clearance", "R1")]


def test_legality_rotated_extent() -> None:
    """A 4 × 1 mm courtyard beside another part: clear at 0°, overlapping at 270° (the dogfood case)."""
    defn = read_footprint(LIBS / "Mini.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    component = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1", value="1k")
    neighbour = extent("b", rect(9.0, 12.0, 11.0, 14.0))

    def layout(rotation: int) -> list[PlacedExtent]:
        placed = place_footprint(
            defn, component=component, at=Point(10 * MM, 10 * MM), rotation=rotation, key="R1"
        )
        return [dataclasses.replace(placed_extent(placed), footprint_id="a"), neighbour]

    flat, turned = layout(0), layout(270_000_000)
    assert flat[0].front == (rect(8.5, 9.25, 11.5, 10.75),)
    assert turned[0].front == (rect(9.25, 8.5, 10.75, 11.5),)
    wide = [flat[0], extent("b", rect(9.0, 11.0, 11.0, 13.0))]
    tall = [turned[0], extent("b", rect(9.0, 11.0, 11.0, 13.0))]
    assert check(wide, [BOARD], names=NAMES) == ()
    assert codes(check(tall, [BOARD], names=NAMES)) == [("place.courtyard-overlap", "D1,R1")]


def test_legality_no_extent_and_no_outline() -> None:
    bare = PlacedExtent("a", "top")
    layout = [bare, extent("b", rect(48, 5, 52, 8)), extent("c", rect(49, 5, 55, 8), exact=False)]
    found = check(layout, [], names=NAMES)
    assert codes(found) == [
        ("place.courtyard-overlap", "D1,U1"),
        ("place.no-extent", "R1"),
        ("place.no-outline", "board"),
    ]
    assert found[0].message.endswith("(approximate extent)")
    assert [i.severity for i in found] == ["error", "info", "info"]


def test_legality_issues_are_sorted_and_names_fall_back() -> None:
    layout = [extent("z", rect(60, 0, 62, 2)), extent("a", rect(70, 0, 72, 2))]
    found = check(layout, [BOARD], names={"a": "R9"})
    assert codes(found) == [("place.outside-outline", "R9"), ("place.outside-outline", "z")]


def test_legality_edge_clearance_of_a_design() -> None:
    design = Design.new("rules", seed=0)
    assert edge_clearance(design) == 0

    def rule(n: int, kind: str, value: int | None, selector: Selector = EVERY) -> Rule:
        return Rule(
            id=f"rul_00000000-0000-4000-8000-{n:012d}",
            name=f"r{n}",
            kind=kind,
            selector_a=selector,
            min=value,
        )  # type: ignore[arg-type]

    rules = RuleSet(
        id="rst_00000000-0000-4000-8000-000000000001",
        rules=(
            rule(1, "clearance", 100_000),
            rule(2, "edge_clearance", 500_000),
            rule(3, "edge_clearance", 300_000),
            rule(4, "edge_clearance", 100_000, Selector("ref", "U*")),
            rule(5, "edge_clearance", None),
        ),
    )
    assert edge_clearance(dataclasses.replace(design, rules=rules)) == 300_000


def test_legality_touching_follows_the_probe_files() -> None:
    recorded = {
        path.name: json.loads(path.read_text(encoding="utf-8"))["probes"]["place-touch"]
        for path in sorted(PROBES.glob("*.json"))
    }
    assert set(recorded) == {"9.0.9.json", "10.0.6.json"}
    assert set(recorded.values()) <= {"absent", "present"}
    assert TOUCHING_OVERLAPS == ("present" in recorded.values())  # the stricter outcome wins
