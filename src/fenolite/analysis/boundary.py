# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The boundary of a board for the distance analyses: the outer ring, the cut-outs and the thickness
(capability board-analyses, "Board boundary").

From ``Board.outline`` when the model has one, its arcs (``Outline.arcs``) polygonised; otherwise from the
graphics on the layer of kind ``edge``, chained by exact endpoint equality with
``geometry.assemble_rings``. Curved edges are polygonised, and ``band`` bounds that approximation. A board
without a closed outline gives ``source == "none"``: this function never raises on what it finds. No
thickness is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.geometry import (
    DEFAULT_TOL,
    Arc,
    Circle,
    GeometryError,
    Location,
    Segment,
    area2,
    assemble_rings,
    point_in_ring,
)
from fenolite.model.board import Board, Graphic, Outline

Ring = tuple[Point, ...]
Source = Literal["model", "edge", "none"]


@dataclass(frozen=True, slots=True)
class BoardBoundary:
    """``outer`` and ``cutouts`` are rings without a closing copy of their first point. ``band`` is the
    bound in nanometres of the approximation of curved edges, 0 for a polygonal boundary."""

    outer: Ring = ()
    cutouts: tuple[Ring, ...] = ()
    thickness: Nm | None = None
    band: int = 0
    source: Source = "none"

    def rings(self) -> tuple[Ring, ...]:
        return (self.outer, *self.cutouts) if self.outer else ()


def _clean(points: tuple[Point, ...]) -> Ring:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _pieces(graphic: Graphic) -> tuple[list[Segment | Arc], bool]:
    """The pieces of one edge graphic that is not a circle, and whether one of them is an arc."""
    points = graphic.points
    if graphic.kind == "arc" and len(points) == 3:
        try:
            return [Arc(points[0], points[1], points[2])], True
        except (GeometryError, ValueError):
            return [Segment(points[0], points[2])], False
    if graphic.kind == "rect" and len(points) == 2:
        a, b = points
        corners = (a, Point(b.x, a.y), b, Point(a.x, b.y))
        return [Segment(p, q) for p, q in zip(corners, (*corners[1:], corners[0]), strict=True)], False
    if graphic.kind == "polygon":
        return [Segment(p, q) for p, q in zip(points, (*points[1:], points[0]), strict=True)], False
    return [Segment(p, q) for p, q in zip(points, points[1:], strict=False)], False


def _thickness(board: Board, given: Nm | None) -> Nm | None:
    if given is not None:
        return given
    if board.stackup is not None and board.stackup.layers:
        total = sum(layer.thickness for layer in board.stackup.layers)
        return total if total > 0 else None
    return None


def _edge_rings(board: Board, arc_tol: int) -> tuple[list[Ring], bool]:
    layers = {layer.name for layer in board.layers if layer.kind == "edge"}
    rings: list[Ring] = []
    pieces: list[Segment | Arc] = []
    curved = False
    for graphic in board.graphics:
        if graphic.layer not in layers:
            continue
        if graphic.kind == "circle" and len(graphic.points) == 2:
            circle = Circle.from_kicad(graphic.points[0], graphic.points[1])
            if circle.radius2 > 0:
                rings.append(_clean(circle.polygonize(arc_tol)))
                curved = True
            continue
        found, arc = _pieces(graphic)
        kept = [piece for piece in found if piece.start != piece.end]
        pieces += kept
        curved = curved or (arc and bool(kept))
    if pieces:
        for path in assemble_rings(pieces):
            rings.append(_clean(path.polygonize(arc_tol)))
    return [ring for ring in rings if len(ring) >= 3 and area2(ring) != 0], curved


def _model_ring(outline: Outline, index: int, arc_tol: int) -> tuple[Ring, bool]:
    """Ring ``index`` of a model outline (0 is the board ring, k is cut-out k − 1) with the arcs of
    ``Outline.arcs`` replaced by their polygonisation at ``arc_tol``, and whether it holds one."""
    ring = outline.points if index == 0 else outline.cutouts[index - 1]
    mids = {arc.edge: arc.mid for arc in outline.arcs if arc.ring == index}
    if not mids:
        return _clean(tuple(ring)), False
    points: list[Point] = []
    curved = False
    for k, start in enumerate(ring):
        end = ring[(k + 1) % len(ring)]
        points.append(start)
        mid = mids.get(k)
        if mid is None or start == end:
            continue
        try:
            arc = Arc(start, mid, end)
        except (GeometryError, ValueError):
            continue
        if arc.is_straight:
            continue
        curved = True
        points += arc.polygonize(arc_tol)[1:-1]
    return _clean(tuple(points)), curved


def board_boundary(board: Board, *, arc_tol: int = DEFAULT_TOL, thickness: Nm | None = None) -> BoardBoundary:
    """The boundary of ``board``: from its outline, else from its edge graphics, else ``source`` ``none``."""
    thick = _thickness(board, thickness)
    if board.outline is not None:
        outer, bent = _model_ring(board.outline, 0, arc_tol)
        if len(outer) >= 3:
            found = [_model_ring(board.outline, k + 1, arc_tol) for k in range(len(board.outline.cutouts))]
            cutouts = tuple(ring for ring, _ in found if len(ring) >= 3)
            curved = bent or any(flag for ring, flag in found if len(ring) >= 3)
            return BoardBoundary(outer, cutouts, thick, arc_tol + 1 if curved else 0, "model")
    try:
        rings, curved = _edge_rings(board, arc_tol)
    except (GeometryError, ValueError):
        return BoardBoundary(thickness=thick)
    if not rings:
        return BoardBoundary(thickness=thick)
    largest = max(range(len(rings)), key=lambda i: (abs(area2(rings[i])), -i))
    outer = rings[largest]
    inside = [
        ring
        for i, ring in enumerate(rings)
        if i != largest and all(point_in_ring(p, outer) is not Location.OUTSIDE for p in ring)
    ]
    return BoardBoundary(outer, tuple(sorted(inside, key=min)), thick, arc_tol + 1 if curved else 0, "edge")


__all__ = ["BoardBoundary", "board_boundary"]
