# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent connected-mesh area identity, location faults and exact current bounds."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_faces as exact
from fenolite.geometry.boolean._exact_noding import Budget, Limits
from fenolite.geometry.errors import GeometryError

Mesh = tuple[exact.Frame, tuple[exact.Ring, ...], dict[int, bool]]


@pytest.fixture(scope="module")
def connected_mesh() -> Mesh:
    count = 45
    heights = tuple(F(1, (1 << 120) + 2 * i + 1) for i in range(count))
    xs = tuple(F(x) for i in range(count) for x in (3 * i, 3 * i + 1)) + (F(3 * count),)
    ys = (F(0),) + tuple(sorted(heights)) + (F(1),)
    edges: dict[exact.Edge, exact.Current] = {}
    for xa, xb in zip(xs[:-1], xs[1:], strict=True):
        for ya, yb in zip(ys[:-1], ys[1:], strict=True):
            x, y = (xa + xb) / 2, (ya + yb) / 2
            owner = int(x) // 3
            inside = owner < count and 3 * owner < x < 3 * owner + 1 and 0 < y < heights[owner]
            ring = ((xa, ya), (xb, ya), (xb, yb), (xa, yb))
            for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
                edge = min((a, b), (b, a))
                previous = edges.get(edge, (0, 0))
                edges[edge] = (previous[0] + int(inside) * (1 if edge == (a, b) else -1), 0)
    # A real connected planar mesh: frames enforces conservation, face ownership,
    # Euler identity and bounded exact face areas before the identity under test.
    frame = exact.frames(edges, Budget())
    loops = tuple(
        ((F(3 * i), F(0)), (F(3 * i + 1), F(0)), (F(3 * i + 1), h), (F(3 * i), h))
        for i, h in enumerate(heights)
    )
    selected: dict[int, bool] = {}
    for i, cycle in enumerate(frame.cycles):
        ring = tuple(a for a, _ in cycle)
        x = (min(p[0] for p in ring) + max(p[0] for p in ring)) / 2
        y = (min(p[1] for p in ring) + max(p[1] for p in ring)) / 2
        owner = int(x) // 3
        selected[i] = (
            exact.area2(ring, Budget()) > 0
            and owner < count
            and 3 * owner < x < 3 * owner + 1
            and 0 < y < heights[owner]
        )
    assert len(frame.exteriors) == 1
    return frame, loops, selected


def test_connected_selected_mesh_has_exact_area_identity(connected_mesh: Mesh) -> None:
    frame, loops, selected = connected_mesh
    assert exact.global_area_sum(tuple(exact.area2(r, Budget()) for r in loops), Budget()) is None
    exact._area_identity(frame, loops, selected, Budget())


def test_mesh_identity_preserves_loop_order_and_cyclic_start_invariance(connected_mesh: Mesh) -> None:
    frame, loops, selected = connected_mesh
    moved = tuple(r[1:] + r[:1] for r in reversed(loops))
    exact._area_identity(frame, moved, selected, Budget())


def test_equal_area_at_other_real_mesh_points_is_not_a_current_identity(connected_mesh: Mesh) -> None:
    frame, loops, selected = connected_mesh
    moved = tuple((x + 3, y) for x, y in loops[0])
    assert exact.area2(moved, Budget()) == exact.area2(loops[0], Budget())
    assert all(p in frame.neighbors for p in moved)
    with pytest.raises(GeometryError, match="current mismatch"):
        exact._area_identity(frame, (moved, *loops[1:]), selected, Budget())


def test_missing_selected_face_is_not_certified(connected_mesh: Mesh) -> None:
    frame, loops, selected = connected_mesh
    altered = dict(selected)
    altered[next(i for i, value in altered.items() if value)] = False
    with pytest.raises(GeometryError, match="current mismatch"):
        exact._area_identity(frame, loops, altered, Budget())


def test_connected_mesh_uses_remaining_global_work(connected_mesh: Mesh) -> None:
    frame, loops, selected = connected_mesh
    budget = Budget()
    budget.visit(budget.limits.winding_visits - 1)
    with pytest.raises(GeometryError, match="visit budget"):
        exact._area_identity(frame, loops, selected, budget)


@pytest.mark.parametrize(
    "coarse",
    [
        ((F(0), F(0)), (F(2), F(0)), (F(0), F(2))),
        ((F(-1, 3), F(2, 7)), (F(5, 3), F(16, 7)), (F(2, 3), F(23, 7))),
    ],
)
def test_collinear_subdivision_preserves_exact_oriented_current(coarse: exact.Ring) -> None:
    middle = tuple((3 * a + b) / 4 for a, b in zip(coarse[0], coarse[1], strict=True))
    fine = (coarse[0], (middle[0], middle[1]), coarse[1], coarse[2])
    cycle = tuple(zip(fine, fine[1:] + fine[:1], strict=True))
    exact._component_current_identity((coarse,), (cycle,), Budget())
    with pytest.raises(GeometryError, match="current mismatch"):
        exact._component_current_identity((tuple(reversed(coarse)),), (cycle,), Budget())


def test_current_endpoint_storage_refuses_without_relaxing_the_cap() -> None:
    ring = ((F(0), F(0)), (F(1), F(0)), (F(1), F(1)), (F(0), F(1)))
    cycle = tuple(zip(ring, ring[1:] + ring[:1], strict=True))
    exact._component_current_identity((ring,), (cycle,), Budget(replace(Limits(), nodes=8)))
    with pytest.raises(GeometryError, match="current endpoint budget"):
        exact._component_current_identity((ring,), (cycle,), Budget(replace(Limits(), nodes=7)))
