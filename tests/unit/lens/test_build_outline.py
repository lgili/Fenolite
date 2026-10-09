# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Outline shapes in a build (capability design-dsl, "Outline shapes in a build"; kicad-file-backend,
"Outline lowering"; layout-lens, "Placement precedence" and "Board content outside the design is kept";
change c0102)."""

from __future__ import annotations

import pytest
from _outlinehelp import BOARD, ROUNDED, SHAPE, board_text, build_script, codes, rebuild_script, variant

from fenolite.backends.kicad.outline import board_outline, edge_graphics, is_signed
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point
from fenolite.dsl import mm, outline_locked
from fenolite.geometry import orient2d
from fenolite.lens import preserve

MM = 1_000_000
ROUND = SHAPE + "design.board(outline=shape.circle(mm(20), mm(20), mm(40)))"


def edge_nodes(text: str) -> list[Node]:
    return [
        child
        for child in parse(text).children
        if isinstance(child, Node) and child.name in ("gr_line", "gr_arc") and "Edge.Cuts" in str(child)
    ]


def point(node: Node, head: str) -> Point:
    child = node.find(head)
    assert child is not None
    x, y = (atom.value for atom in child.atoms())
    return Point(round(float(x) * MM), round(float(y) * MM))


@pytest.mark.parametrize("target", [9, 10])
def test_a_rounded_board_with_cutouts(target: int) -> None:
    output = build_script(variant(ROUNDED), target)
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    assert not [code for code in codes(output) if code.startswith("kicad.outline.")]
    nodes = edge_nodes(board_text(output))
    assert [n.name for n in nodes].count("gr_line") == 6 and [n.name for n in nodes].count("gr_arc") == 8
    for arc in (n for n in nodes if n.name == "gr_arc"):
        assert orient2d(point(arc, "start"), point(arc, "mid"), point(arc, "end")) > 0
    # the board read back gives the script's rings, its arcs polygonised
    read = board_outline(read_board(board_text(output)))
    assert read.source == "edge" and len(read.rings) == 3 and not read.exact
    model = board_outline(output.design)
    assert model.source == "model" and len(model.rings) == 3
    assert {min(ring) for ring in read.rings} == {min(ring) for ring in model.rings}


def test_a_cutout_across_the_edge_stops_the_build() -> None:
    design = variant(BOARD + "\n" + SHAPE + "design.cutout(shape.circle(mm(49), mm(15), mm(4)))")
    output = build_script(design)
    assert dict(output.files) == {}
    (issue,) = [i for i in output.issues if i.code == "kicad.outline.invalid"]
    assert issue.severity == "error" and "cut-out 1" in issue.message and "board" in issue.message


def test_a_rectangle_builds_every_file_as_before_but_for_the_edge_uuids() -> None:
    """The four edge lines of ``board(width, height)`` are the lines of earlier releases with signed
    uuids, and the edge content of the written board is signed."""
    output = build_script(variant())
    nodes = edge_nodes(board_text(output))
    assert [n.name for n in nodes] == ["gr_line"] * 4
    assert [point(n, "start") for n in nodes] == [
        Point(100 * MM, 100 * MM),
        Point(150 * MM, 100 * MM),
        Point(150 * MM, 130 * MM),
        Point(100 * MM, 130 * MM),
    ]
    assert output.design.board is not None and output.design.board.outline is not None
    assert is_signed(output.design.board.outline, edge_graphics(read_board(board_text(output))))


def test_the_lock_reaches_the_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    design = variant("design.board(mm(50), mm(30), locked=True)")
    assert outline_locked(design) is True and outline_locked(variant()) is False
    first = build_script(design)
    seen: list[bool] = []
    real = preserve.merge_layout

    def spy(*args: object, **kwargs: object) -> preserve.Merged:
        seen.append(bool(kwargs.get("lock_outline")))
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(preserve, "merge_layout", spy)
    rebuild_script(design, board_text(first))
    assert seen and all(seen)
    seen.clear()
    rebuild_script(variant(), board_text(first))
    assert seen and not any(seen)


def test_an_outline_with_arcs_is_kept_as_written() -> None:
    first = build_script(variant(ROUNDED))
    again = rebuild_script(variant(ROUNDED), board_text(first))
    assert "layout.outline-kept" not in codes(again)
    assert not [code for code in codes(again) if code.startswith("kicad.outline.")]
    assert dict(again.files) == dict(first.files)


def test_a_part_on_a_round_board() -> None:
    """``R1`` at (20 mm, 5 mm) lies inside ``outline_box`` though outside the box of the outline's two
    vertices, so a rebuild without its ``place()`` keeps its board position."""
    placed = variant(ROUND)
    placed.parts["R1"].request = None
    placed.parts["R1"].place(mm(20), mm(5))
    first = build_script(placed)
    assert "layout.unplaced" not in codes(first)
    unplaced = variant(ROUND)
    unplaced.parts["R1"].request = None
    again = rebuild_script(unplaced, board_text(first))
    assert "layout.unplaced" not in codes(again)
    read = read_board(board_text(again))
    refs = {c.id: c.ref for c in read.circuit.components}
    assert read.board is not None
    (r1,) = [fp for fp in read.board.footprints if refs[fp.component_id] == "R1"]
    assert r1.position == Point(120 * MM, 105 * MM)


def test_staging_starts_right_of_the_box_of_the_arcs() -> None:
    design = variant(ROUND)
    design.parts["R1"].request = None
    output = build_script(design)
    assert "layout.unplaced" in codes(output)
    read = read_board(board_text(output))
    refs = {c.id: c.ref for c in read.circuit.components}
    assert read.board is not None
    (r1,) = [fp for fp in read.board.footprints if refs[fp.component_id] == "R1"]
    assert r1.position.x > 140 * MM  # right of the circle, not of its two vertices' box alone
    assert r1.position.y >= 100 * MM
