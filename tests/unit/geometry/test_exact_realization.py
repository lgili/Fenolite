# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Projection, source-corner, topology and real debris-policy certificates (c0332)."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction as F

import pytest

from fenolite.backends.altium.pour import _without_debris
from fenolite.geometry.boolean import _exact_faces as faces
from fenolite.geometry.boolean import _exact_realization as real
from fenolite.geometry.boolean._exact_noding import Budget, Segment
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.vector import Point

IntRing = tuple[tuple[int, int], ...]


def rectangle(x0: int, y0: int, x1: int, y1: int) -> IntRing:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def ring(points: tuple[tuple[int | F, int | F], ...]) -> faces.Ring:
    return tuple((F(x), F(y)) for x, y in points)


def source(subject: tuple[IntRing, ...], clip: tuple[IntRing, ...]) -> tuple[Segment, ...]:
    return tuple(
        Segment(a, b, channel)
        for channel, rings in enumerate((subject, clip))
        for r in rings
        for a, b in zip(r, r[1:] + r[:1], strict=True)
    )


def build(
    subject: tuple[IntRing, ...], clip: tuple[IntRing, ...], tol: int = 1
) -> tuple[real.Projection, tuple[Polygon, ...], real.Certificate]:
    segments = source(subject, clip)
    budget = Budget()
    loops = faces.difference_loops(segments, budget)
    budget.stage("realization")
    projection = real.project_boundaries(loops, segments, budget)
    result = _without_debris(projection.polygons, tol)
    return projection, result, projection.certify(result, tol, budget)


def test_integer_hole_and_original_vertices_remain_exact() -> None:
    projection, result, cert = build((rectangle(0, 0, 10, 10),), (rectangle(2, 2, 8, 8),))
    assert len(result) == 1 and len(result[0].holes) == 1
    assert result[0].area2 == 128
    assert cert.canonical_nodes == cert.protected_vertices == 8
    assert cert.losses == () and cert.local_sign_changes == 0
    assert projection.polygons == result


def test_piece_area_is_tested_before_filling_its_hole() -> None:
    projection, result, cert = build((rectangle(0, 0, 3, 3),), (rectangle(1, 1, 2, 2),), 3)
    assert result == ()
    assert len(projection.polygons[0].holes) == 1 and projection.polygons[0].area2 == 16
    assert len(cert.losses) == 1
    loss = cert.losses[0]
    assert loss.kind == "debris-piece" and loss.exact_area == loss.integer_area == 8
    assert len(loss.owned_holes) == 1
    wrong = (Polygon(projection.polygons[0].outer),)
    with pytest.raises(GeometryError, match="ineligible piece"):
        projection.certify(wrong, 3, Budget())


def test_hole_and_piece_at_the_exact_threshold_are_kept() -> None:
    _, result, cert = build((rectangle(0, 0, 2, 2),), (), 2)
    assert len(result) == 1 and result[0].area2 == 8 and cert.losses == ()
    _, result, cert = build((rectangle(0, 0, 6, 6),), (rectangle(2, 2, 4, 4),), 2)
    assert len(result[0].holes) == 1 and cert.losses == ()


def test_small_hole_is_filled_only_in_a_kept_piece() -> None:
    _, result, cert = build((rectangle(0, 0, 4, 4),), (rectangle(1, 1, 2, 2),), 2)
    assert len(result) == 1 and result[0].holes == () and result[0].area2 == 32
    assert len(cert.losses) == 1
    assert cert.losses[0].kind == "debris-hole"
    assert cert.losses[0].exact_area == cert.losses[0].integer_area == 1


def test_subgrid_collapse_has_zero_signed_current_and_exact_area_proof() -> None:
    loops = (ring(((0, 0), (F(1, 4), 0), (0, F(1, 4)))),)
    budget = Budget()
    projection = real.project_boundaries(loops, (), budget)
    assert projection.polygons == ()
    cert = projection.certify((), 1, budget)
    assert len(cert.losses) == 1 and cert.losses[0].kind == "collapsed-piece"
    assert cert.losses[0].exact_area == F(1, 32) and cert.losses[0].integer_area == 0


def test_thin_piece_owns_large_hole_when_both_boundaries_project_together() -> None:
    outer = ring(rectangle(0, 0, 3, 3))
    e = F(1, 100)
    hole = ring(((e, e), (e, 3 - e), (3 - e, 3 - e), (3 - e, e)))
    budget = Budget()
    projection = real.project_boundaries((outer, hole), (), budget)
    assert projection.polygons[0].area2 == 0
    result = _without_debris(projection.polygons, 1)
    cert = projection.certify(result, 1, budget)
    assert result == () and len(cert.losses) == 1
    assert cert.losses[0].exact_area == F(299, 2500)
    assert len(cert.losses[0].owned_holes) == 1


def test_removing_a_qualified_piece_or_hole_refuses() -> None:
    projection, result, _ = build((rectangle(0, 0, 10, 10),), (rectangle(2, 2, 8, 8),))
    with pytest.raises(GeometryError, match="qualified whole piece"):
        projection.certify((), 1, Budget())
    with pytest.raises(GeometryError, match="qualified whole hole"):
        projection.certify((Polygon(result[0].outer),), 1, Budget())


def test_hole_cannot_be_assigned_to_another_piece() -> None:
    projection, result, _ = build(
        (rectangle(0, 0, 10, 10), rectangle(20, 0, 30, 10)),
        (rectangle(2, 2, 4, 4), rectangle(22, 2, 24, 4)),
    )
    wrong = normalize_polygons(
        (Polygon(result[0].outer, result[1].holes), Polygon(result[1].outer, result[0].holes))
    )
    with pytest.raises(GeometryError, match="hole ownership"):
        projection.certify(wrong, 1, Budget())


def test_original_corner_erased_by_rounding_is_refused() -> None:
    # Integer-only Boolean input: the clipped predecessor (-1, 1/4) rounds
    # onto y=0 and makes the original (0,0) corner collinear. Area is retained.
    subject = (((-4, 1), (0, 0), (4, 0), (4, 2), (-4, 2)),)
    clip = (rectangle(-5, -5, -1, 5), rectangle(1, -5, 5, 5))
    with pytest.raises(GeometryError, match="protected source vertex missing"):
        build(subject, clip)


def test_local_sign_change_keeps_actual_precision_and_nonzero_vertex_contract() -> None:
    subject = (((10, 1), (0, 0), (-100, -1), (-100, -10), (10, -10)),)
    clip = (((-101, -102), (99, 100), (-200, 100), (-200, -102)),)
    _, result, cert = build(subject, clip)
    assert result[0].area2 == 310
    assert cert.local_sign_changes == 1 and cert.protected_vertices == 3
    assert Point(0, 0) in result[0].outer


def test_wrong_displacement_and_wrong_half_even_tie_are_refused() -> None:
    p = (F(1, 3), F(0))
    with pytest.raises(GeometryError, match="quantization bound"):
        real.projection_bound({p}, {p: (2, 0)})
    tie = (F(1, 2), F(1, 2))
    with pytest.raises(GeometryError, match="prescribed half-even"):
        real.projection_bound({tie}, {tie: (1, 1)})
    real.projection_bound({tie}, {tie: (0, 0)})


def test_one_projection_per_canonical_node_and_contact_ray_word(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Counter[faces.ExactPoint] = Counter()
    original = real.round_point

    def counted(x: F | int, y: F | int) -> Point:
        calls[F(x), F(y)] += 1
        return original(x, y)

    monkeypatch.setattr(real, "round_point", counted)
    _, result, cert = build((rectangle(0, 0, 2, 2), rectangle(2, 2, 4, 4)), ())
    assert len(result) == 2 and cert.canonical_nodes == 7
    assert len(calls) == 7 and set(calls.values()) == {1}
    assert cert.contact_points == 1


def test_zero_area_bow_tie_cannot_be_misreported_as_a_collapsed_face() -> None:
    # This exact concave loop is simple and positive, but rounds to a zero-area bow tie.
    loop = ring(
        (
            (F(49, 100), F(49, 100)),
            (F(149, 100), F(149, 100)),
            (F(-49, 100), F(101, 100)),
            (F(101, 100), F(-49, 100)),
        )
    )
    assert faces.area2(loop, Budget()) > 0
    with pytest.raises(GeometryError, match="zero area does not prove collapsed winding"):
        real.project_boundaries((loop,), (), Budget())


def test_cleanup_cannot_drop_a_long_zero_current_spike() -> None:
    loop = ring(((0, 0), (10, 0), (10, F(19, 4)), (20, 5), (10, F(21, 4)), (10, 10), (0, 10)))
    projection = real.project_boundaries((loop,), (), Budget())
    result = _without_debris(projection.polygons, 1)
    with pytest.raises(GeometryError, match="cleanup loses projected boundary points"):
        projection.certify(result, 1, Budget())


@pytest.mark.parametrize("height", [F(3, 5), F(9, 10)])
def test_cleaned_rational_hairline_requires_the_complete_continuous_bound(height: F) -> None:
    loop = ring(((0, 0), (10, 0), (10, F(19, 4)), (10 + height, 5), (10, F(21, 4)), (10, 10), (0, 10)))
    segments = source((rectangle(0, 0, 10, 10),), ())
    projection = real.project_boundaries((loop,), segments, Budget())
    result = _without_debris(projection.polygons, 1)
    assert projection.omitted == frozenset()
    assert real.line_cover(tuple(projection.projected[p] for p in loop), Budget()) != real.line_cover(
        projection.integer_loops[0], Budget()
    )
    if height == F(9, 10):
        with pytest.raises(GeometryError, match="uncovered continuous interval endpoint"):
            projection.certify(result, 1, Budget())
    else:
        certificate = projection.certify(result, 1, Budget())
        assert certificate.protected_vertices == 4 and certificate.losses == ()
        assert set(result[0].outer) == {Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)}


def test_rounding_cannot_join_previously_disjoint_pieces() -> None:
    left = ring(((0, 0), (F(7, 5), 0), (F(7, 5), 2), (0, 2)))
    right = ring(((F(149, 100), 0), (3, 0), (3, 2), (F(149, 100), 2)))
    projection = real.project_boundaries((left, right), (), Budget())
    result = _without_debris(projection.polygons, 1)
    with pytest.raises(GeometryError, match="overlap along an edge"):
        projection.certify(result, 1, Budget())


@pytest.mark.parametrize("as_hole", [False, True])
def test_integer_debris_is_not_enough_when_exact_face_is_above_threshold(as_hole: bool) -> None:
    small = ring(((2, 2), (F(349, 100), 2), (F(349, 100), F(549, 100)), (2, F(549, 100))))
    loops = (ring(rectangle(0, 0, 10, 10)), tuple(reversed(small))) if as_hole else (small,)
    projection = real.project_boundaries(loops, (), Budget())
    result = _without_debris(projection.polygons, 2)
    with pytest.raises(GeometryError, match="loss is not eligible"):
        projection.certify(result, 2, Budget())


@pytest.mark.parametrize("as_hole", [False, True])
def test_discarded_simple_inversion_requires_exact_and_integer_whole_face_eligibility(as_hole: bool) -> None:
    # A fresh authored near-collinear triangle changes sign on nearest rounding.
    triangle = ring(((0, 0), (100, 1), (F(3, 5), F(49, 100))))
    if as_hole:
        shifted = tuple((x + 10, y + 10) for x, y in reversed(triangle))
        loops = (ring(rectangle(0, 0, 1000, 1000)), shifted)
    else:
        loops = (triangle,)
    projection = real.project_boundaries(loops, (), Budget())
    result = _without_debris(projection.polygons, 10)
    cert = projection.certify(result, 10, Budget())
    assert len(cert.losses) == 1 and cert.losses[0].orientation_changed
    assert cert.losses[0].exact_area == F(121, 5) and cert.losses[0].integer_area == F(1, 2)
    # Keeping the inverted ring is forbidden even though normalization could
    # hide its original sign. At a tighter floor the exact loss is ineligible.
    with pytest.raises(GeometryError, match="retained whole-ring orientation"):
        projection.certify(projection.polygons, 0, Budget())
    with pytest.raises(GeometryError, match="loss is not eligible"):
        projection.certify(_without_debris(projection.polygons, 1), 1, Budget())
