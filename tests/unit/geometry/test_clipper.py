# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``clipper`` union backend and the selection of a backend by operation (capability
geometry-boolean-backends, "Clipper union backend", "Backend selection"; change c0167)."""

from __future__ import annotations

import sys

import pytest

from fenolite.core.coords import Point
from fenolite.core.stadium import stadium
from fenolite.geometry import Arc, GeometryError, Polygon
from fenolite.geometry.boolean import ClipperBackend, FallbackBackend, available_backends, select_backend
from fenolite.geometry.errors import BackendUnavailable

pytest.importorskip("pyclipper")
MM = 1_000_000


def polygonised(center: Point, length: int, width: int, rotation: int, tol: int = 1_000) -> tuple[Point, ...]:
    """The stadium of a slot with its two arcs polygonised at ``tol``."""
    ring = stadium(center, length, width, rotation)
    mids = dict(ring.arcs())
    points: list[Point] = []
    for k, start in enumerate(ring.points):
        points.append(start)
        if k in mids:
            points += Arc(start, mids[k], ring.points[(k + 1) % 4]).polygonize(tol)[1:-1]
    return tuple(points)


def ell() -> tuple[tuple[Point, ...], tuple[Point, ...]]:
    """The two stadiums 2 mm wide between (110, 110)–(120, 110) mm and (120, 110)–(120, 120) mm."""
    return (
        polygonised(Point(115 * MM, 110 * MM), 12 * MM, 2 * MM, 0),
        polygonised(Point(120 * MM, 115 * MM), 12 * MM, 2 * MM, 90_000_000),
    )


def test_selection_by_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(select_backend(), FallbackBackend)
    assert isinstance(select_backend(operation="union"), ClipperBackend)
    assert isinstance(select_backend(operation="intersection"), FallbackBackend)
    assert available_backends() == ("fallback", "clipper")
    monkeypatch.setitem(sys.modules, "pyclipper", None)  # an import of it now fails
    assert isinstance(select_backend(), FallbackBackend)
    with pytest.raises(BackendUnavailable) as info:
        select_backend(operation="union")
    assert info.value.issue.code == "geometry.backend-unavailable"
    assert "fenolite[geo]" in info.value.issue.hint
    assert available_backends() == ("fallback",)


def test_two_slots_in_an_ell() -> None:
    a, b = ell()
    (union,) = ClipperBackend().union([Polygon(a), Polygon(b)])
    assert union.holes == ()
    new = set(union.outer) - set(a) - set(b)
    assert new == {Point(119 * MM, 111 * MM)}


def test_union_is_deterministic_and_normal() -> None:
    a, b = ell()
    first = ClipperBackend().union([Polygon(a), Polygon(b)])
    again = ClipperBackend().union([Polygon(b), Polygon(a)])
    assert first == again
    assert first[0].outer[0] == min(first[0].outer)


def test_separate_rings_stay_two() -> None:
    a = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    b = Polygon((Point(20, 0), Point(30, 0), Point(30, 10), Point(20, 10)))
    assert len(ClipperBackend().union([a, b])) == 2
    assert ClipperBackend().union([]) == ()


def test_a_ring_of_four_bars_has_a_hole() -> None:
    bars = [
        Polygon((Point(0, 0), Point(40, 0), Point(40, 10), Point(0, 10))),
        Polygon((Point(30, 0), Point(40, 0), Point(40, 40), Point(30, 40))),
        Polygon((Point(0, 30), Point(40, 30), Point(40, 40), Point(0, 40))),
        Polygon((Point(0, 0), Point(10, 0), Point(10, 40), Point(0, 40))),
    ]
    (union,) = ClipperBackend().union(bars)
    assert len(union.holes) == 1
    assert set(union.holes[0]) == {Point(10, 10), Point(30, 10), Point(30, 30), Point(10, 30)}


def test_other_operations_and_domain() -> None:
    square = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    for call in (
        lambda: ClipperBackend().intersection(square, square),
        lambda: ClipperBackend().difference(square, square),
        lambda: ClipperBackend().xor(square, square),
        lambda: ClipperBackend().offset(square, 1),
    ):
        with pytest.raises(BackendUnavailable):
            call()
    far = Polygon((Point(0, 0), Point(2**31, 0), Point(0, 10)))
    with pytest.raises(GeometryError) as info:
        ClipperBackend().union(far)
    assert info.value.code == "geometry.out-of-range"
