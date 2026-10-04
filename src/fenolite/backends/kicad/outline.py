# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board outline as closed rings: ``board_outline`` (capability kicad-file-backend, "Board outline as
rings"; facts: ``docs/formats/kicad/board.md``; change c0022).

A design with a model outline gives its points and cut-outs. A read board gives the root graphics on its
edge layer, chained by exact endpoint equality with ``geometry.assemble_rings``: no snapping tolerance
(``H-G-EDGE-EXACT``). Edge items inside footprints stay opaque and are not chained; a board whose only
edge items are there gets the problem ``footprint-edges-only``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fenolite.backends.kicad.slots import from_ext
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import DEFAULT_TOL, Arc, Circle, GeometryError, Segment, area2, assemble_rings
from fenolite.geometry.errors import BRANCHING_CONTOUR
from fenolite.model.base import Opaque
from fenolite.model.board import Board, Graphic
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PLACE-OUTLINE", "H-G-EDGE-EXACT"))
"""Raised to ``CORPUS-VERIFIED`` when ``H-G-PLACE-OUTLINE`` is settled."""
OutlineSource = Literal["model", "edge"]
OutlineProblem = Literal["", "open-contour", "branching-contour", "no-edge-content", "footprint-edges-only"]
PROBLEMS: tuple[str, ...] = ("open-contour", "branching-contour", "no-edge-content", "footprint-edges-only")
DEFAULT_EDGE = "Edge.Cuts"
Ring = tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class BoardOutline:
    """The outline of a board: ``rings[0]`` is the board (the ring of largest area) and the others are its
    cut-outs. ``problem`` says why ``rings`` is empty; ``exact`` is false when a curve was polygonised."""

    rings: tuple[Ring, ...] = ()
    source: OutlineSource = "edge"
    problem: OutlineProblem = ""
    exact: bool = True

    def __post_init__(self) -> None:
        if bool(self.rings) == bool(self.problem):
            raise ValueError("a board outline holds rings or a problem, never both and never neither")


def _edge_layers(board: Board) -> frozenset[str]:
    return frozenset(layer.name for layer in board.layers if layer.kind == "edge") or frozenset(
        {DEFAULT_EDGE}
    )


def _footprint_edges(board: Board, layers: frozenset[str]) -> bool:
    """Whether a footprint holds an item on an edge layer among its opaque children."""
    marks = tuple(f'(layer "{name}")' for name in layers)
    for footprint in board.footprints:
        bag = footprint.ext.get("kicad")
        if bag is None:
            continue
        for slot in from_ext(bag):
            if (
                isinstance(slot, Opaque)
                and slot.fragment.startswith("(fp_")
                and any(mark in slot.fragment for mark in marks)
            ):
                return True
    return False


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


def _sorted(rings: list[Ring]) -> tuple[Ring, ...]:
    """The ring of largest area first; the others in the order of their smallest point."""
    largest = max(range(len(rings)), key=lambda i: (abs(area2(rings[i])), -i))
    rest = sorted((ring for i, ring in enumerate(rings) if i != largest), key=min)
    return (rings[largest], *rest)


def board_outline(design: Design, *, tol: int = DEFAULT_TOL) -> BoardOutline:
    """The outline of ``design``'s board as rings in the board frame.

    From ``Board.outline`` when the model has one (``source`` ``model``: its points, then its cut-outs),
    otherwise from the root graphics on the edge layer (``source`` ``edge``). Never raises on what it
    finds: a board without a closed outline gets a ``problem``.
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
    for graphic in board.graphics:
        if graphic.layer not in layers:
            continue
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
        problem: OutlineProblem = (
            "footprint-edges-only" if _footprint_edges(board, layers) else "no-edge-content"
        )
        return BoardOutline(problem=problem)
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
    return BoardOutline(_sorted(rings), "edge", exact=exact)


__all__ = ["EVIDENCE", "PROBLEMS", "BoardOutline", "board_outline"]
