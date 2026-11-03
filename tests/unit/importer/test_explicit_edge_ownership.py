# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit physical edge ownership, never inferred from proximity (c0349)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _importcode import build, imported, notched

from fenolite.backends.kicad.frame import footprint_edges
from fenolite.backends.kicad.outline import edge_outline, graphic_text
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, mm
from fenolite.importer.source import read_kicad
from fenolite.model.design import Design as ModelDesign


def source(tmp: Path, *, arc: bool = False) -> Path:
    path = notched(tmp)
    text = path.read_text()
    old = "(fp_line (start -28 25) (end -28 -15)"
    new = (
        "(fp_arc (start -27.999999 25) (mid -29 5) (end -27.999999 -15)"
        if arc
        else "(fp_line (start -27.999999 25) (end -27.999999 -15)"
    )
    assert old in text
    path.write_text(text.replace(old, new))
    return path


def root_edges(design: ModelDesign) -> list[tuple[str, int, bool]]:
    assert design.board is not None
    return sorted(
        (graphic_text(g) or "", g.width, g.filled) for g in design.board.graphics if g.layer == "Edge.Cuts"
    )


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("curved", (False, True))
def test_explicit_physical_edges_roundtrip(tmp_path: Path, target: int, curved: bool) -> None:
    original = read_kicad(source(tmp_path / "source", arc=curved)).design
    assert original.board is not None
    logical = edge_outline(original)
    assert logical is not None
    declared = dataclasses.replace(original, board=dataclasses.replace(original.board, outline=logical))
    after = read_board(write_board(declared, target=target, downgrade=True).text)
    assert after.board is not None
    assert root_edges(after) == root_edges(original)
    assert footprint_edges(after.board, ("Edge.Cuts",)) == footprint_edges(original.board, ("Edge.Cuts",))


@pytest.mark.parametrize("curved", (False, True))
def test_import_keeps_exact_root_not_synthetic_copies(tmp_path: Path, curved: bool) -> None:
    path = source(tmp_path / "source", arc=curved)
    before = read_kicad(path).design
    reply = imported(tmp_path, path, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert build(tmp_path / "out").exit_code == 0
    after = read_board(tmp_path / "out/built/notched.kicad_pcb")
    assert root_edges(after) == root_edges(before)
    assert after.board is not None and before.board is not None
    original = footprint_edges(before.board, ("Edge.Cuts",))
    rebuilt = footprint_edges(after.board, ("Edge.Cuts",))
    assert [(e.kind, e.points) for e in rebuilt] == [(e.kind, e.points) for e in original]


def test_dsl_lines_and_arcs_explicitly_take_edge_cuts() -> None:
    design = Design("explicit")
    design.board(mm(10), mm(10))
    design.line("edge", (mm(0), mm(0)), (mm(10), mm(0)), layer="Edge.Cuts", width=mm("0.05"))
    design.arc(
        "curve", (mm(10), mm(0)), (mm(11), mm(5)), (mm(10), mm(10)), layer="Edge.Cuts", width=mm("0.05")
    )
    assert len(design.drawings) == 2


@pytest.mark.parametrize("kind", ("parallel", "duplicate", "mid", "gap", "collapsed", "transitive"))
def test_inconsistent_explicit_geometry_never_silently_disappears(tmp_path: Path, kind: str) -> None:
    original = read_kicad(source(tmp_path / "source", arc=True)).design
    assert original.board is not None
    outline = edge_outline(original)
    assert outline is not None
    graphics = list(original.board.graphics)
    edge = next(g for g in graphics if g.layer == "Edge.Cuts" and g.kind == "line")
    if kind in ("parallel", "duplicate", "collapsed", "transitive"):
        delta = {"parallel": 1, "duplicate": 0, "collapsed": 1, "transitive": 9_999}[kind]
        points = tuple(Point(p.x + delta, p.y) for p in edge.points)
        if kind == "collapsed":
            points = (points[0], Point(points[0].x + 1, points[0].y))
        graphics.append(dataclasses.replace(edge, id=derived_id("gfx", "ownership", kind), points=points))
        if kind == "transitive":
            graphics.append(
                dataclasses.replace(
                    edge,
                    id=derived_id("gfx", "ownership", "transitive-tail"),
                    points=tuple(Point(p.x + 18_000, p.y) for p in edge.points),
                )
            )
    elif kind == "gap":
        graphics[graphics.index(edge)] = dataclasses.replace(
            edge, points=(Point(edge.points[0].x + 10_000, edge.points[0].y), edge.points[1])
        )
    else:
        outline = dataclasses.replace(
            outline, arcs=tuple(dataclasses.replace(a, mid=Point(a.mid.x + 1, a.mid.y)) for a in outline.arcs)
        )
    declared = dataclasses.replace(
        original, board=dataclasses.replace(original.board, outline=outline, graphics=tuple(graphics))
    )
    try:
        written = write_board(declared)
    except LossyWriteError as error:
        assert "outline" in str(error).lower(), error
    else:
        after = read_board(written.text)
        assert root_edges(after) == sorted(
            (graphic_text(g) or "", g.width, g.filled) for g in graphics if g.layer == "Edge.Cuts"
        )


def test_exact_chain_gap_is_not_joined() -> None:
    from fenolite.backends.kicad.outline import CHAIN_GAP
    from fenolite.geometry import Segment
    from fenolite.geometry.polygon import join_ends

    original = (
        Segment(Point(0, 0), Point(0, 1_000_000)),
        Segment(Point(CHAIN_GAP, 0), Point(CHAIN_GAP, 1_000_000)),
    )
    joined, groups = join_ends(original, CHAIN_GAP)
    assert joined == list(original) and groups == 0
