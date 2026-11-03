# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Analytic areas, independent finite face seeds and signed/topology failures (c0332)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_faces as exact
from fenolite.geometry.boolean._exact_noding import Budget, Limits, Segment, node_segments
from fenolite.geometry.errors import GeometryError

IntRing = tuple[tuple[int, int], ...]


def rectangle(x0: int, y0: int, x1: int, y1: int) -> IntRing:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def segments(subject: tuple[IntRing, ...], clip: tuple[IntRing, ...]) -> tuple[Segment, ...]:
    return tuple(
        Segment(a, b, channel)
        for channel, rings in enumerate((subject, clip))
        for ring in rings
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True)
    )


SQUARE = rectangle(0, 0, 10, 10)
INNER = rectangle(2, 2, 8, 8)
CASES = (
    ((), (), F(0), 0),
    ((SQUARE,), (), F(100), 1),
    ((SQUARE,), (SQUARE,), F(0), 0),
    ((SQUARE,), (rectangle(20, 20, 30, 30),), F(100), 1),
    ((SQUARE,), (INNER,), F(64), 2),
    ((SQUARE,), (rectangle(5, 5, 15, 15),), F(75), 1),
    ((SQUARE,), (INNER, tuple(reversed(INNER))), F(100), 1),
    ((SQUARE, tuple(reversed(SQUARE))), (), F(0), 0),
    ((rectangle(-10, -10, 10, 10),), (((-4, -4), (4, 4), (-4, 4), (4, -4)),), F(368), 3),
    ((SQUARE, tuple(reversed(rectangle(3, 3, 7, 7)))), (rectangle(4, -1, 6, 11),), F(72), 2),
    ((rectangle(0, 0, 2, 2), rectangle(2, 2, 4, 4)), (), F(8), 2),
    ((rectangle(0, 0, 2, 2), rectangle(2, 0, 4, 2)), (), F(8), 1),
    ((SQUARE,), (((-2, 3), (12, 7), (12, 12), (-2, 12)),), F(50), 1),
)


def finite_seed(edge: exact.Edge, source: tuple[Segment, ...]) -> tuple[int, int]:
    """Bounded independent oracle: choose a finite epsilon below every affine sign root."""
    a, b = edge
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    normal = (a[1] - b[1], b[0] - a[0])
    roots = [F(1)]
    for s in source:
        dx, dy = s.b[0] - s.a[0], s.b[1] - s.a[1]
        terms = (
            (s.a[1] - middle[1], -normal[1]),
            (s.b[1] - middle[1], -normal[1]),
            (dx * (middle[1] - s.a[1]) - dy * (middle[0] - s.a[0]), dx * normal[1] - dy * normal[0]),
        )
        roots.extend(abs(constant / slope) for constant, slope in terms if constant and slope)
    epsilon = min(roots) / 2
    x, y = middle[0] + epsilon * normal[0], middle[1] + epsilon * normal[1]
    value = [0, 0]
    for s in source:
        orient = (s.b[0] - s.a[0]) * (y - s.a[1]) - (s.b[1] - s.a[1]) * (x - s.a[0])
        if s.a[1] <= y < s.b[1] and orient > 0:
            value[s.channel] += 1
        if s.b[1] <= y < s.a[1] and orient < 0:
            value[s.channel] -= 1
    return value[0], value[1]


@pytest.mark.parametrize("subject,clip,expected,count", CASES)
def test_analytic_difference_and_every_face_seed(
    subject: tuple[IntRing, ...], clip: tuple[IntRing, ...], expected: F, count: int
) -> None:
    source = segments(subject, clip)
    budget = Budget()
    loops = exact.difference_loops(source, budget)
    assert len(loops) == count
    assert sum((exact.area2(r, budget) for r in loops), F(0)) / 2 == expected
    graph = node_segments(source)
    frame = exact.frames({(f.a, f.b): f.current for f in graph.fragments if f.current != (0, 0)}, Budget())
    values = exact.solve(frame, source, Budget())
    for i, cycle in enumerate(frame.cycles):
        assert values[i] == finite_seed(cycle[0], source)
    for moved in (
        tuple(reversed(source)),
        tuple(Segment(s.b, s.a, s.channel) for s in source),
    ):
        result = exact.difference_loops(moved)
        assert len(result) == count
        assert sum((exact.area2(r, Budget()) for r in result), F(0)) / 2 == expected


def test_rational_vertices_and_disconnected_nested_supports_are_exact() -> None:
    result = exact.difference_loops(segments((SQUARE,), (((-2, 3), (12, 7), (12, 12), (-2, 12)),)))
    points = {p for ring in result for p in ring}
    assert (F(0), F(25, 7)) in points and (F(10), F(45, 7)) in points
    # Clipping support lies inside the subject's disconnected support. Its
    # exterior seed has subject winding 1, rather than an assumed global zero.
    source = segments((SQUARE,), (INNER,))
    graph = node_segments(source)
    frame = exact.frames({(f.a, f.b): f.current for f in graph.fragments}, Budget())
    values = exact.solve(frame, source, Budget())
    assert {values[i] for i in frame.exteriors} == {(0, 0), (1, 0)}


@pytest.mark.parametrize("field", ["faces", "halfedges", "winding_visits"])
def test_face_and_winding_limits_refuse(field: str) -> None:
    with pytest.raises(GeometryError, match="budget"):
        exact.difference_loops(segments((SQUARE,), ()), Budget(replace(Limits(), **{field: 0})))


def test_open_source_and_corrupted_dual_current_refuse() -> None:
    with pytest.raises(GeometryError, match="nonconserved"):
        exact.difference_loops((Segment((0, 0), (1, 1), 0),))
    source = segments((SQUARE,), ())
    graph = node_segments(source)
    frame = exact.frames({(f.a, f.b): f.current for f in graph.fragments}, Budget())
    face = next(iter(frame.dual))
    other, delta = frame.dual[face][0]
    frame.dual[face][0] = (other, (delta[0] + 1, delta[1]))
    with pytest.raises(GeometryError, match="contradictory"):
        exact.solve(frame, source, Budget())


def test_independent_oracle_detects_uniform_seed_fault() -> None:
    source = segments((SQUARE,), ())
    graph = node_segments(source)
    frame = exact.frames({(f.a, f.b): f.current for f in graph.fragments}, Budget())
    values = exact.solve(frame, source, Budget())
    wrong = {i: (w[0] + 1, w[1]) for i, w in values.items()}
    assert any(wrong[i] != finite_seed(cycle[0], source) for i, cycle in enumerate(frame.cycles))
    assert exact.boundaries(frame, wrong, Budget()) == ()


def test_expired_call_does_not_poison_concurrent_independent_calls() -> None:
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    source = segments((SQUARE,), ())
    graph = node_segments(source, budget)
    frame = exact.frames({(f.a, f.b): f.current for f in graph.fragments}, budget)
    now[0] = 241.0
    with pytest.raises(GeometryError, match="deadline"):
        exact.solve(frame, source, budget)

    def healthy(x: int) -> F:
        result = exact.difference_loops(segments((rectangle(x, 0, x + 10, 10),), ()))
        return sum((exact.area2(r, Budget()) for r in result), F(0)) / 2

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(healthy, range(16))) == [F(100)] * 16
