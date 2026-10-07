# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The outline as the board writer emits it: lines, arcs with a positive orientation, and signed uuids
(capability kicad-file-backend, "Outline lowering"; change c0102)."""

from __future__ import annotations

import dataclasses
import hashlib
import re

import pytest

from fenolite.backends.kicad import _edgesign
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import (
    edge_graphics,
    edge_texts,
    edge_uuid,
    is_signed,
    outline_digest,
    position_uuid,
)
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import orient2d
from fenolite.model.board import Board, Outline, OutlineArc
from fenolite.model.design import Design

MM = 1_000_000


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


RECT = (mm(0, 0), mm(50, 0), mm(50, 30), mm(0, 30))
CIRCLE = (mm(11.6, 10), mm(8.4, 10))
CIRCLE_ARCS = (OutlineArc(1, 0, mm(10, 8.4)), OutlineArc(1, 1, mm(10, 11.6)))


def outline(points: tuple[Point, ...] = RECT, **more: object) -> Outline:
    return Outline(id=derived_id("out", "write", "outline"), points=points, **more)  # type: ignore[arg-type]


def design(found: Outline) -> Design:
    board = Board(id=derived_id("brd", "write", "board"), layers=created_layers(2), outline=found)
    return dataclasses.replace(Design.new("write", seed=0), board=board)


def edges(text: str) -> list[Node]:
    return [
        child
        for child in parse(text).children
        if isinstance(child, Node) and child.name in ("gr_line", "gr_arc")
    ]


def point(node: Node, head: str) -> Point:
    child = node.find(head)
    assert child is not None
    x, y = (atom.value for atom in child.atoms())
    return Point(round(float(x) * MM), round(float(y) * MM))


def uuid_of(node: Node) -> str:
    child = node.find("uuid")
    assert child is not None
    return child.atoms()[0].value


def test_edge_texts_do_not_depend_on_the_direction() -> None:
    assert edge_texts(outline()) == (
        "line 0 0 50000000 0",
        "line 50000000 0 50000000 30000000",
        "line 0 30000000 50000000 30000000",
        "line 0 0 0 30000000",
    )
    turned = outline(tuple(reversed(RECT)))
    assert sorted(edge_texts(turned)) == sorted(edge_texts(outline()))
    with_circle = outline(cutouts=(CIRCLE,), arcs=CIRCLE_ARCS)
    assert edge_texts(with_circle)[4:] == (
        "arc 8400000 10000000 11600000 10000000 10000000 8400000",
        "arc 8400000 10000000 11600000 10000000 10000000 11600000",
    )


def test_the_digest_is_sixteen_digits_of_the_sorted_texts() -> None:
    texts = edge_texts(outline())
    data = "".join(f"{text}\n" for text in sorted(texts)).encode("utf-8")
    assert outline_digest(texts) == hashlib.sha256(data).hexdigest()[:16]
    assert outline_digest(reversed(texts)) == outline_digest(texts)
    assert re.fullmatch(r"[0-9a-f]{16}", outline_digest(texts))


def test_the_uuid_rule_is_the_writers() -> None:
    found = outline()
    assert edge_uuid(found, "abc", "line 0 0 1 1") == kicad_uuid(found, "outline:abc:line 0 0 1 1")
    assert position_uuid(found, 2, 3) == kicad_uuid(found, "outline:2:3")
    assert _edgesign.signed_uuids(found) == tuple(
        kicad_uuid(found, f"outline:{outline_digest(edge_texts(found))}:{text}") for text in edge_texts(found)
    )


@pytest.mark.parametrize("target", [9, 10])
def test_rectangle_outline(target: int) -> None:
    found = outline()
    lines = edges(write_board(design(found), target=target).text)
    assert [line.name for line in lines] == ["gr_line"] * 4
    assert point(lines[-1], "end") == mm(0, 0) and point(lines[0], "start") == mm(0, 0)
    assert [uuid_of(line) for line in lines] == list(_edgesign.signed_uuids(found))
    assert all(line.find("layer") == parse('(layer "Edge.Cuts")') for line in lines)


@pytest.mark.parametrize("target", [9, 10])
def test_arcs_written_with_a_positive_orientation(target: int) -> None:
    found = outline(cutouts=(CIRCLE,), arcs=CIRCLE_ARCS)
    written = edges(write_board(design(found), target=target).text)
    lines = [node for node in written if node.name == "gr_line"]
    arcs = [node for node in written if node.name == "gr_arc"]
    assert len(lines) == 4 and len(arcs) == 2
    first = [point(arcs[0], head) for head in ("start", "mid", "end")]
    assert first == [mm(8.4, 10), mm(10, 8.4), mm(11.6, 10)]  # the edge ran the other way
    for arc in arcs:
        assert orient2d(point(arc, "start"), point(arc, "mid"), point(arc, "end")) > 0
        assert arc.find("stroke") == parse("(stroke (width 0.1) (type solid))")
    assert [node.name for node in arcs[0].nodes()] == ["start", "mid", "end", "stroke", "layer", "uuid"]
    assert [uuid_of(node) for node in (*lines, *arcs)] == list(_edgesign.signed_uuids(found))


def test_one_moved_vertex_changes_every_uuid() -> None:
    first = write_board(design(outline()), target=10).text
    moved = write_board(design(outline((mm(0, 0), mm(50, 0), mm(51, 30), mm(0, 30)))), target=10).text
    one, two = {uuid_of(e) for e in edges(first)}, {uuid_of(e) for e in edges(moved)}
    assert len(one) == len(two) == 4 and not one & two
    assert {uuid_of(e) for e in edges(write_board(design(outline()), target=10).text)} == one


@pytest.mark.parametrize("target", [9, 10])
def test_a_written_outline_reads_back_signed(target: int) -> None:
    found = outline(cutouts=(CIRCLE,), arcs=CIRCLE_ARCS)
    board = read_board(write_board(design(found), target=target).text)
    graphics = edge_graphics(board)
    assert len(graphics) == 6 and is_signed(found, graphics)
    assert sorted(g.kind for g in graphics) == ["arc", "arc", "line", "line", "line", "line"]
    # a moved line keeps its uuid and changes its text: no longer signed
    moved = dataclasses.replace(graphics[0], points=(mm(0, 0), mm(51, 0)))
    assert not is_signed(found, (moved, *graphics[1:]))
    assert not is_signed(found, ())


def test_no_outline_no_edges() -> None:
    assert edges(write_board(design(Outline(id=derived_id("out", "write", "empty"))), target=10).text) == []
