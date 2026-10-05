# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board outline as closed rings: ``board_outline`` (capability kicad-file-backend, "Board outline as
rings"; facts: ``docs/formats/kicad/board.md``; change c0022).

A design with a model outline gives its points and cut-outs. A read board gives the root graphics on its
edge layer together with the edge items of its footprints (``frame.footprint_edges``;
``H-K-OUTLINE-FPEDGE``), chained with ``geometry.assemble_rings`` after endpoints closer than
``CHAIN_GAP`` are joined, as KiCad joins them (``H-K-OUTLINE-CHAIN``). ``H-G-EDGE-EXACT``, the earlier
premise that endpoints meet exactly, is refuted by that measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from fenolite.backends.kicad.frame import footprint_edges
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import DEFAULT_TOL, Arc, Circle, GeometryError, Segment, area2, assemble_rings
from fenolite.geometry.errors import BRANCHING_CONTOUR
from fenolite.model.board import Board
from fenolite.model.design import Design

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-G-PLACE-OUTLINE", "H-K-OUTLINE-CHAIN", "H-K-OUTLINE-FPEDGE")
)
"""Raised to ``CORPUS-VERIFIED`` when ``H-G-PLACE-OUTLINE`` is settled."""
CHAIN_GAP = 10_000
"""Edge endpoints closer than this (nm, strictly) are one point. Both majors close an outline across a gap
below 10 µm and report it open above; at exactly 10 µm, 10.0.6 closes and 9.0.9 does not, so Fenolite
says open there: the safe answer for 9.0."""
OutlineSource = Literal["model", "edge"]
OutlineProblem = Literal["", "open-contour", "branching-contour", "no-edge-content"]
PROBLEMS: tuple[str, ...] = ("open-contour", "branching-contour", "no-edge-content")
DEFAULT_EDGE = "Edge.Cuts"
Ring = tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class BoardOutline:
    """The outline of a board: ``rings[0]`` is the board (the ring of largest area) and the others are its
    cut-outs. ``problem`` says why ``rings`` is empty; ``exact`` is false when a curve was polygonised;
    ``joined`` counts the groups of endpoints closer than ``CHAIN_GAP`` that were joined into one point."""

    rings: tuple[Ring, ...] = ()
    source: OutlineSource = "edge"
    problem: OutlineProblem = ""
    exact: bool = True
    joined: int = 0

    def __post_init__(self) -> None:
        if bool(self.rings) == bool(self.problem):
            raise ValueError("a board outline holds rings or a problem, never both and never neither")


def _edge_layers(board: Board) -> frozenset[str]:
    return frozenset(layer.name for layer in board.layers if layer.kind == "edge") or frozenset(
        {DEFAULT_EDGE}
    )


class _EdgeLike(Protocol):
    """What an edge graphic gives: a root ``Graphic`` or a ``frame.EdgeItem``."""

    @property
    def kind(self) -> str: ...

    @property
    def points(self) -> Sequence[Point]: ...


def _join(pieces: list[Segment | Arc]) -> tuple[list[Segment | Arc], int]:
    """``pieces`` with every group of endpoints closer than ``CHAIN_GAP`` joined into the group's smallest
    point, and the number of groups joined. Distances are compared squared, with integers. A piece whose
    two ends join into one point is left out."""
    points = sorted({end for piece in pieces for end in (piece.start, piece.end)})
    if len(points) < 2:
        return pieces, 0
    parent = {point: point for point in points}

    def root(point: Point) -> Point:
        while parent[point] != point:
            parent[point] = parent[parent[point]]
            point = parent[point]
        return point

    cells: dict[tuple[int, int], list[Point]] = {}
    for point in points:
        cell = (point.x // CHAIN_GAP, point.y // CHAIN_GAP)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in cells.get((cell[0] + dx, cell[1] + dy), ()):
                    gap2 = (point.x - other.x) ** 2 + (point.y - other.y) ** 2
                    if gap2 < CHAIN_GAP * CHAIN_GAP:
                        a, b = root(point), root(other)
                        if a != b:
                            parent[max(a, b)] = min(a, b)
        cells.setdefault(cell, []).append(point)
    moved = {point: root(point) for point in points if root(point) != point}
    if not moved:
        return pieces, 0
    joined: list[Segment | Arc] = []
    for piece in pieces:
        start, end = moved.get(piece.start, piece.start), moved.get(piece.end, piece.end)
        if start == end:
            continue
        if (start, end) == (piece.start, piece.end):
            joined.append(piece)
        elif isinstance(piece, Arc):
            try:
                joined.append(Arc(start, piece.mid, end))
            except (GeometryError, ValueError):
                joined.append(Segment(start, end))
        else:
            joined.append(Segment(start, end))
    return joined, len(set(moved.values()))


def _pieces(graphic: _EdgeLike) -> tuple[list[Segment | Arc], bool]:
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


def _sorted(rings: list[Ring]) -> tuple[Ring, ...]:
    """The ring of largest area first; the others in the order of their smallest point."""
    largest = max(range(len(rings)), key=lambda i: (abs(area2(rings[i])), -i))
    rest = sorted((ring for i, ring in enumerate(rings) if i != largest), key=min)
    return (rings[largest], *rest)


def board_outline(design: Design, *, tol: int = DEFAULT_TOL) -> BoardOutline:
    """The outline of ``design``'s board as rings in the board frame.

    From ``Board.outline`` when the model has one (``source`` ``model``: its points, then its cut-outs),
    otherwise from the root graphics on the edge layer and the edge items of the footprints (``source``
    ``edge``), with endpoints closer than ``CHAIN_GAP`` joined. Never raises on what it finds: a board
    without a closed outline gets a ``problem``.
    """
    board = design.board
    if board is None:
        return BoardOutline(problem="no-edge-content")
    if board.outline is not None and len(board.outline.points) >= 3:
        cutouts = tuple(tuple(ring) for ring in board.outline.cutouts if len(ring) >= 3)
        return BoardOutline((tuple(board.outline.points), *cutouts), "model")
    layers = _edge_layers(board)
    rings: list[Ring] = []
    pieces: list[Segment | Arc] = []
    exact = True
    edge_items: list[_EdgeLike] = [graphic for graphic in board.graphics if graphic.layer in layers]
    edge_items += footprint_edges(board, layers)
    for graphic in edge_items:
        if graphic.kind == "circle" and len(graphic.points) == 2:
            circle = Circle.from_kicad(graphic.points[0], graphic.points[1])
            if circle.radius2 > 0:
                rings.append(circle.polygonize(tol))
                exact = False
            continue
        found, curved = _pieces(graphic)
        kept = [piece for piece in found if piece.start != piece.end]
        pieces += kept
        exact = exact and not (curved and kept)
    if not pieces and not rings:
        return BoardOutline(problem="no-edge-content")
    pieces, joined = _join(pieces)
    if pieces:
        try:
            paths = assemble_rings(pieces)
        except GeometryError as error:
            code: OutlineProblem = "branching-contour" if error.code == BRANCHING_CONTOUR else "open-contour"
            return BoardOutline(problem=code)
        for path in paths:
            ring = path.polygonize(tol)
            if len(ring) >= 3 and area2(ring) != 0:
                rings.append(ring)
    if not rings:
        return BoardOutline(problem="open-contour")
    return BoardOutline(_sorted(rings), "edge", exact=exact, joined=joined)


__all__ = ["CHAIN_GAP", "EVIDENCE", "PROBLEMS", "BoardOutline", "board_outline"]
