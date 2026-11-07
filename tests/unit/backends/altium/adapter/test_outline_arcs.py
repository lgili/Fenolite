# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The arcs of the board outline join their vertices (capability altium-import, "Outline, graphics and
texts"; change c0378): an arc vertex of ``Board6`` runs from its vertex to the next, so its ends are the
two vertices, also when a vertex lies a few micrometres off the circle of the arc's centre and radius (as
on a public board, ``docs/formats/altium/pcb-document.md``)."""

from __future__ import annotations

from _outline_arc import mil, rounded

from fenolite.backends.altium import frame
from fenolite.backends.kicad import outline as kicad_outline
from fenolite.convert.report import ConversionReport
from fenolite.convert.rings import compare_rings
from fenolite.core.coords import Point
from fenolite.model.design import Design


def edges(design: Design) -> list[tuple[str, tuple[Point, ...]]]:
    assert design.board is not None
    return [(g.kind, g.points) for g in design.board.graphics if g.layer == "Edge.Cuts"]


def test_an_outline_arc_runs_from_its_vertex_to_the_next() -> None:
    (arc,) = [points for kind, points in edges(rounded()) if kind == "arc"]
    assert (arc[0], arc[2]) == (mil(1000, 700), mil(900, 800))


def test_an_arc_vertex_off_its_circle_still_joins_its_neighbours() -> None:
    """The end vertex lies 0.2 mil (5.08 µm) off the circle: the arc ends on it, the next line starts on
    it, and the ring of the Altium edge equals the ring KiCad reads from the same edges."""
    design = rounded("800.2mil")
    found = edges(design)
    (arc,) = [points for kind, points in found if kind == "arc"]
    assert (arc[0], arc[2]) == (mil(1000, 700), mil(900, 800.2))
    starts = {points[0] for kind, points in found if kind == "line"}
    assert mil(900, 800.2) in starts
    source = frame.board_edges(design)
    written = kicad_outline.board_edges(design)
    assert source is not None and written is not None
    assert compare_rings(source, written, ConversionReport()) == ()


def test_an_arc_far_from_its_vertices_keeps_its_own_ends() -> None:
    """Beyond 10 µm the vertices are not taken: the arc keeps the ends of its centre, radius and angles."""
    (arc,) = [points for kind, points in edges(rounded("801mil")) if kind == "arc"]
    assert arc[2] == mil(900, 800)
