# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The arc vertices of the outlines of the public Altium boards (change c0378; ``H-A-IMP-OUTLINE-ARC``).

For every arc vertex k of the ``Board6`` outline and of each polygon, the ends computed from its centre,
radius and angles lie within ``OUTLINE_VERTEX_NM`` of vertex k and vertex k+1, and much farther from the
pair of vertex k-1 and vertex k; the import's outline arcs end on their two vertices. Counts only: no value
of the files reaches the output.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium.adapter import import_board, units
from fenolite.backends.altium.adapter.copper import OUTLINE_VERTEX_NM
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.core.coords import Point

pytestmark = pytest.mark.needs_corpus
DOCUMENTS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id]
APART_NM = 1_000_000
"""The other pairing (vertex k-1 to vertex k) misses by at least this on every public arc: 1 mm."""


def _point(vertex: OutlineVertex) -> Point:
    return Point(units.units_length(vertex.x)[0], -units.units_length(vertex.y)[0])


def _gap(p: Point, q: Point) -> int:
    return max(abs(p.x - q.x), abs(p.y - q.y))


def _pairing(vertices: Sequence[OutlineVertex]) -> list[tuple[int, int]]:
    """Per arc vertex whose two vertices differ: the greater end distance to (vertex k, vertex k+1) and to
    (vertex k-1, vertex k), each in the better of the two orders (Chebyshev distance, nm)."""
    found: list[tuple[int, int]] = []
    count = len(vertices)
    for k, vertex in enumerate(vertices):
        if vertex.kind == 0 or vertex.radius <= 0:
            continue
        before, a, b = (_point(vertices[(k + d) % count]) for d in (-1, 0, 1))
        if a == b:
            continue
        start, _, end = units.arc_points(
            vertex.cx,
            vertex.cy,
            vertex.radius,
            units.angle(vertex.start_angle)[0],
            units.angle(vertex.end_angle)[0],
        )

        def pair(p: Point, q: Point) -> int:
            return min(max(_gap(start, p), _gap(end, q)), max(_gap(start, q), _gap(end, p)))  # noqa: B023

        found.append((pair(a, b), pair(before, a)))
    return found


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_an_arc_vertex_runs_to_the_next_vertex(item) -> None:  # type: ignore[no-untyped-def]
    path = require(item)
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    rings = [document.board.outline, *(polygon.vertices for polygon in document.polygons)]
    pairs = [pair for ring in rings for pair in _pairing(ring)]
    assert all(forward <= OUTLINE_VERTEX_NM for forward, _ in pairs)
    assert all(back >= APART_NM for _, back in pairs)
    design = import_board(document, file=path.name, sha256="0" * 64)
    assert design.board is not None
    corners = {_point(vertex) for vertex in document.board.outline}
    arcs = [g for g in design.board.graphics if g.layer == "Edge.Cuts" and g.kind == "arc"]
    assert all(g.points[0] in corners and g.points[2] in corners for g in arcs)
