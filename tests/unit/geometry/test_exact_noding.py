# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent contacts, analytic splits, signed overlap and resource refusals (c0332)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction as F
from itertools import combinations, product
from typing import cast

import pytest

from fenolite.geometry.boolean._exact_noding import Budget, Limits, Segment, candidate_pairs, node_segments
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.shapes import BBox
from fenolite.geometry.vector import Point


def test_closed_grid_boxes_include_degenerate_and_endpoint_contacts() -> None:
    points = tuple(product((-1, 0, 1), repeat=2))
    segments = tuple(Segment(a, b, i % 2) for i, (a, b) in enumerate(product(points, repeat=2)))
    boxes = [BBox.of_points((Point(*s.a), Point(*s.b))) for s in segments]
    expected = tuple(
        (i, j) for i, j in combinations(range(len(segments)), 2) if boxes[i].intersects(boxes[j])
    )
    assert candidate_pairs(segments, Budget()) == expected
    graph = node_segments(segments)
    assert graph.nodes > len(points)  # rational crossings of grid diagonals also survive


def test_t_junction_splits_the_stem_including_closed_box_boundary() -> None:
    graph = node_segments((Segment((1, 0), (1, 2), 0), Segment((1, 1), (2, 1), 1)))
    assert graph.nodes == 4
    assert graph.candidate_pairs == graph.intersecting_pairs == 1
    assert [(f.a, f.b, f.current) for f in graph.fragments] == [
        ((1, 0), (1, 1), (1, 0)),
        ((1, 1), (1, 2), (1, 0)),
        ((1, 1), (2, 1), (0, 1)),
    ]


def test_rational_crossing_is_never_quantized() -> None:
    graph = node_segments((Segment((0, 0), (3, 1), 0), Segment((1, -1), (1, 2), 1)))
    crossing = (F(1), F(1, 3))
    assert graph.nodes == 5
    assert len(graph.fragments) == 4
    assert all(crossing in (f.a, f.b) for f in graph.fragments)
    assert all(isinstance(c, F) for f in graph.fragments for q in (f.a, f.b) for c in q)


def test_signed_overlap_retains_cancelled_edges_and_each_source_direction() -> None:
    graph = node_segments(
        (
            Segment((0, 0), (6, 0), 0),
            Segment((4, 0), (2, 0), 0),
            Segment((2, 0), (4, 0), 1),
        )
    )
    assert [(f.a, f.b, f.current, f.provenance) for f in graph.fragments] == [
        ((0, 0), (2, 0), (1, 0), ((0, 1),)),
        ((2, 0), (4, 0), (0, 1), ((0, 1), (1, -1), (2, 1))),
        ((4, 0), (6, 0), (1, 0), ((0, 1),)),
    ]
    cancelled = node_segments((Segment((0, 0), (1, 0), 0), Segment((1, 0), (0, 0), 0)))
    assert len(cancelled.fragments) == 1
    assert cancelled.fragments[0].current == (0, 0)
    assert cancelled.fragments[0].provenance == ((0, 1), (1, -1))


def test_empty_and_degenerate_segments_preserve_nodes_without_fake_edges() -> None:
    assert node_segments(()).fragments == ()
    graph = node_segments((Segment((7, 8), (7, 8), 0), Segment((7, 8), (7, 8), 1)))
    assert graph.nodes == 1 and graph.intersecting_pairs == 1 and graph.fragments == ()


@pytest.mark.parametrize(
    "field", ["input_edges", "comparisons", "candidates", "nodes", "fragments", "incidences"]
)
def test_structural_limits_refuse_before_returning_a_partial_graph(field: str) -> None:
    limits = replace(Limits(), **{field: 0})
    with pytest.raises(GeometryError, match="budget"):
        node_segments((Segment((0, 0), (3, 0), 0), Segment((1, -1), (1, 1), 1)), Budget(limits))


def test_fraction_bit_limit_and_deadline_refuse() -> None:
    with pytest.raises(GeometryError, match="coordinate bit budget"):
        node_segments(
            (Segment((0, 0), (3, 2), 0), Segment((0, 2), (2, 0), 1)),
            Budget(replace(Limits(), coordinate_bits=2)),
        )
    ticks = iter((0.0, 241.0))
    with pytest.raises(GeometryError, match="deadline"):
        candidate_pairs((), Budget(clock=lambda: next(ticks)))


@pytest.mark.parametrize("coordinate", [True, 0.5])
def test_noninteger_coordinates_are_refused(coordinate: object) -> None:
    with pytest.raises(GeometryError, match="integer input coordinates"):
        node_segments((Segment((cast(int, coordinate), 0), (1, 1), 0),))


@pytest.mark.parametrize("channel", [True, -1, 2])
def test_non_operand_channels_are_refused(channel: int) -> None:
    with pytest.raises(GeometryError, match="operand channel"):
        node_segments((Segment((0, 0), (1, 1), channel),))


def test_domain_and_per_call_state() -> None:
    with pytest.raises(GeometryError) as error:
        node_segments((Segment((2**31, 0), (0, 0), 0),))
    assert error.value.code == "geometry.out-of-range"
    # An exhausted independent call cannot poison the next call's limits/state.
    with pytest.raises(GeometryError):
        node_segments((Segment((0, 0), (1, 0), 0),), Budget(replace(Limits(), nodes=0)))
    assert node_segments((Segment((0, 0), (1, 0), 0),)).nodes == 2
