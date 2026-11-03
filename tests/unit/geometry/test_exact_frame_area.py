# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent connected fans whose exterior has no bounded scalar area."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_faces as exact
from fenolite.geometry.boolean._exact_noding import Budget, Limits
from fenolite.geometry.errors import GeometryError


def fan(
    *, rotated: bool = False, translated: bool = False
) -> tuple[dict[exact.Edge, exact.Current], tuple[exact.Ring, ...]]:
    def move(x: F, y: F) -> exact.ExactPoint:
        if rotated:
            x, y = -y, x
        return (x + 1000, y - 1000) if translated else (x, y)

    loops = tuple(
        (
            move(F(0), F(0)),
            move(F(3 * i + 1) + F(1, (1 << 60) + 2 * i + 1), F(1)),
            move(F(3 * i + 1), F(1)),
        )
        for i in range(100)
    )
    edges: dict[exact.Edge, exact.Current] = {}
    for ring in loops:
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
            edge = min((a, b), (b, a))
            previous = edges.get(edge, (0, 0))
            edges[edge] = (previous[0] + (1 if edge == (a, b) else -1), 0)
    return edges, loops


@pytest.mark.parametrize("rotated,translated", [(False, False), (False, True), (True, True)])
def test_connected_fan_keeps_one_exterior_without_inventing_its_area(rotated: bool, translated: bool) -> None:
    edges, expected = fan(rotated=rotated, translated=translated)
    frame = exact.frames(dict(reversed(tuple(edges.items()))), Budget())
    assert len(frame.cycles) == 101 and len(frame.exteriors) == 1
    exterior = frame.exteriors[0]
    ring = tuple(a for a, _ in frame.cycles[exterior])
    with pytest.raises(GeometryError, match="arithmetic bit budget"):
        exact.area2(ring, Budget())  # Its exact scalar remains unavailable.
    selected = {i: (int(i != exterior), 0) for i in range(len(frame.cycles))}
    loops = exact.boundaries(frame, selected, Budget())
    assert {frozenset(r) for r in loops} == {frozenset(r) for r in expected}
    assert all(exact.area2(r, Budget()) > 0 for r in loops)


def test_frame_sign_fallback_respects_coordinate_and_work_limits() -> None:
    edges, _ = fan()
    with pytest.raises(GeometryError, match="coordinate bit budget"):
        exact.frames(edges, Budget(replace(Limits(), coordinate_bits=8)))
    with pytest.raises(GeometryError, match="visit budget"):
        exact.frames(edges, Budget(replace(Limits(), winding_visits=0)))


def test_frame_area_scalar_and_zero_paths_keep_their_original_meaning() -> None:
    ring = ((F(0), F(0)), (F(2), F(0)), (F(0), F(3)))
    assert exact._face_area(ring, Budget()) == (F(6), 1)
    assert exact._face_area(tuple(reversed(ring)), Budget()) == (F(-6), -1)
    assert exact._face_area(((F(0), F(0)), (F(1), F(0))), Budget()) == (F(0), 0)


def test_unbounded_zero_walk_does_not_invent_a_strict_sign() -> None:
    _, loops = fan()
    walk = tuple(point for ring in loops for point in ring)
    with pytest.raises(GeometryError, match="face area sign certificate unresolved"):
        exact._face_area(walk + tuple(reversed(walk)), Budget())


def test_sign_only_area_uses_the_existing_point_ceiling() -> None:
    _, loops = fan()
    exterior = tuple(reversed(tuple(point for ring in loops for point in ring)))
    assert exact._face_area(exterior, Budget(replace(Limits(), nodes=201))) == (None, -1)
    with pytest.raises(GeometryError, match="face sign point budget"):
        exact._face_area(exterior, Budget(replace(Limits(), nodes=200)))
    ticks = iter((0.0, 241.0))
    with pytest.raises(GeometryError, match="deadline"):
        exact._face_area(exterior, Budget(clock=lambda: next(ticks)))
