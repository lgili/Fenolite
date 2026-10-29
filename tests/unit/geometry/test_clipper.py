# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``clipper`` union backend and the selection of a backend by operation (capability
geometry-boolean-backends, "Clipper union backend", "Backend selection"; change c0167)."""

from __future__ import annotations

import importlib.util
import math
import sys

import pytest

from fenolite.core.coords import Point
from fenolite.core.stadium import stadium
from fenolite.geometry import Arc, GeometryError, Polygon
from fenolite.geometry.boolean import ClipperBackend, FallbackBackend, available_backends, select_backend
from fenolite.geometry.errors import BackendUnavailable

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="the union needs pyclipper of the geo extra")
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


@needs_geo
def test_selection_by_operation() -> None:
    assert isinstance(select_backend(), FallbackBackend)
    assert isinstance(select_backend(operation="union"), ClipperBackend)
    assert isinstance(select_backend(operation="intersection"), FallbackBackend)
    assert available_backends() == ("fallback", "clipper")


def test_selection_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyclipper", None)  # an import of it now fails
    assert isinstance(select_backend(), FallbackBackend)
    with pytest.raises(BackendUnavailable) as info:
        select_backend(operation="union")
    assert info.value.issue.code == "geometry.backend-unavailable"
    assert "fenolite[geo]" in info.value.issue.hint
    assert available_backends() == ("fallback",)


@needs_geo
def test_two_slots_in_an_ell() -> None:
    a, b = ell()
    (union,) = ClipperBackend().union([Polygon(a), Polygon(b)])
    assert union.holes == ()
    new = set(union.outer) - set(a) - set(b)
    assert new == {Point(119 * MM, 111 * MM)}


@needs_geo
def test_union_is_deterministic_and_normal() -> None:
    a, b = ell()
    first = ClipperBackend().union([Polygon(a), Polygon(b)])
    again = ClipperBackend().union([Polygon(b), Polygon(a)])
    assert first == again
    assert first[0].outer[0] == min(first[0].outer)


@needs_geo
def test_separate_rings_stay_two() -> None:
    a = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    b = Polygon((Point(20, 0), Point(30, 0), Point(30, 10), Point(20, 10)))
    assert len(ClipperBackend().union([a, b])) == 2
    assert ClipperBackend().union([]) == ()


@needs_geo
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


def _square(x0: int, y0: int, size: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x0 + size, y0), Point(x0 + size, y0 + size), Point(x0, y0 + size)))


@needs_geo
def test_other_operations_and_domain() -> None:
    """Scenario "Intersection, difference and xor" of "Clipper backend" (change c0215)."""
    backend = ClipperBackend()
    assert backend.operations == frozenset({"union", "intersection", "difference", "xor", "offset"})
    a, b = _square(0, 0, 10), _square(5, 5, 10)
    assert backend.intersection(a, b) == (_square(5, 5, 5),)
    (rest,) = backend.difference(a, b)
    assert rest.outer == (Point(0, 0), Point(10, 0), Point(10, 5), Point(5, 5), Point(5, 10), Point(0, 10))
    assert len(backend.xor(a, b)) == 2
    assert backend.difference(a, ()) == (a,)
    assert backend.intersection(a, _square(20, 20, 5)) == ()
    far = Polygon((Point(0, 0), Point(2**31, 0), Point(0, 10)))
    for call in (lambda: backend.union(far), lambda: backend.difference(a, far), lambda: backend.xor(far, a)):
        with pytest.raises(GeometryError) as info:
            call()
        assert info.value.code == "geometry.out-of-range"


@needs_geo
def test_offset_and_stroke_stay_within_their_tolerance() -> None:
    """Scenario "Offsets and strokes" of "Clipper backend": a round offset and a stroke place their vertices
    on the true arcs, so every chord lies at most ``tol`` inside the arc; a stroke of one point is a disc."""
    backend = ClipperBackend()
    (grown,) = backend.offset(_square(0, 0, 10_000), 1_000, tol=10)
    assert grown.bbox() == _square(-1_000, -1_000, 12_000).bbox()
    (shrunk,) = backend.offset(_square(0, 0, 10_000), -1_000, join="miter", tol=10)
    assert shrunk == _square(1_000, 1_000, 8_000)
    (disc,) = backend.stroke([[Point(0, 0)]], 100_000, tol=50)
    radii = [math.hypot(p.x, p.y) for p in disc.outer]
    assert all(abs(r - 100_000) <= 1 for r in radii)
    sag = 100_000 * (1 - math.cos(math.pi / len(disc.outer)))
    assert sag <= 50 + 1
    (bar,) = backend.stroke([[Point(0, 0), Point(10_000, 0)]], 500, tol=10)
    assert (
        bar.bbox()
        == Polygon((Point(-500, -500), Point(10_500, -500), Point(10_500, 500), Point(-500, 500))).bbox()
    )
    with pytest.raises(ValueError):
        backend.stroke([[Point(0, 0)]], 0)
    with pytest.raises(ValueError):
        backend.offset(_square(0, 0, 10), 1, tol=0)
