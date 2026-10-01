# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Projected fields on write (capability kicad-file-backend, "Projected fields on write", change c0017)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import FIXTURE

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, load, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Size
from fenolite.model.board import FootprintInstance, Graphic, Text
from fenolite.model.circuit import Component
from fenolite.model.design import Design


def component(design: Design, ref: str) -> Component:
    return next(c for c in design.circuit.components if c.ref == ref)


def footprint_of(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = component(design, ref).id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def property_node(root: Node, value: str) -> Node:
    for fp in root.nodes("footprint"):
        for prop in fp.nodes("property"):
            if prop.children[1] == Atom.string(value):
                return prop
    raise AssertionError(value)


def read_only(design: Design) -> list[tuple[str, str]]:
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=9)
    assert info.value.droppable is False
    return [(i.code, i.message) for i in info.value.issues]


def test_unchanged_board_writes_without_issue() -> None:
    assert write_board(read_board(FIXTURE), target=9).issues == ()


def test_reference_renamed() -> None:
    design = read_board(FIXTURE)
    design = design.replace_entity(dataclasses.replace(component(design, "R1"), ref="R9"))
    root = parse(write_board(design, target=9).text)
    renamed = property_node(root, "R9")
    source = property_node(load(FIXTURE), "R1")
    assert renamed.children[0] == Atom.string("Reference")
    assert renamed.with_children([renamed.children[0], Atom.string("R1"), *renamed.children[2:]]) == source


def test_value_renamed() -> None:
    design = read_board(FIXTURE)
    design = design.replace_entity(dataclasses.replace(component(design, "R1"), value="470"))
    root = parse(write_board(design, target=9).text)
    assert property_node(root, "470").children[0] == Atom.string("Value")


def test_spelling_only_projection_re_emitted() -> None:
    text = FIXTURE.read_text(encoding="utf-8").replace("(width 0.25)", "(width 0.250000)", 1)
    design = read_board(text)
    assert design.board is not None
    track = design.board.tracks[0]
    result = write_board(design.replace_entity(dataclasses.replace(track, width=300_000)), target=9)
    assert result.issues == ()
    segment = parse(result.text).nodes("segment")[0]
    source = parse(text).nodes("segment")[0]
    heads = [c.name for c in segment.children if isinstance(c, Node)]
    assert heads == [c.name for c in source.children if isinstance(c, Node)]
    assert segment.find("width") == parse("(width 0.3)")


def test_unchanged_spelling_keeps_its_fragment() -> None:
    text = FIXTURE.read_text(encoding="utf-8").replace("(width 0.25)", "(width 0.250000)", 1)
    segment = parse(write_board(read_board(text), target=9).text).nodes("segment")[0]
    assert segment.find("width") == parse("(width 0.250000)")


def test_read_only_projection_edited() -> None:
    design = read_board(FIXTURE)
    r1 = component(design, "R1")
    design = design.replace_entity(
        dataclasses.replace(r1, properties={**r1.properties, "Datasheet": "x.pdf"})
    )
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=9)
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.projection-read-only" and "properties" in issue.message
    assert issue.where == "/kicad_pcb/footprint[0]"


def test_locked_projection() -> None:
    design = read_board(
        FIXTURE.read_text(encoding="utf-8").replace(
            '(layer "F.Cu")\n\t\t(uuid "d75d', '(locked yes)\n\t\t(layer "F.Cu")\n\t\t(uuid "d75d', 1
        )
    )
    fp = footprint_of(design, "R1")
    assert fp.locked is True
    assert (
        read_only(design.replace_entity(dataclasses.replace(fp, locked=False)))[0][0]
        == "kicad.board.projection-read-only"
    )
    unlocked = read_board(FIXTURE)
    fp = footprint_of(unlocked, "R1")
    root = parse(write_board(unlocked.replace_entity(dataclasses.replace(fp, locked=True)), target=9).text)
    written = root.nodes("footprint")[0]
    assert written.find("locked") == parse("(locked yes)")


def test_stroke_width_is_read_only() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    circle = next(g for g in design.board.graphics if g.kind == "circle")
    changed = design.replace_entity(dataclasses.replace(circle, width=circle.width + 10_000))
    assert [code for code, _ in read_only(changed)] == ["kicad.board.projection-read-only"]


def test_text_font_is_read_only() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    text: Text = design.board.texts[0]
    changed = design.replace_entity(dataclasses.replace(text, size=Size(2_000_000, 2_000_000)))
    assert "size" in read_only(changed)[0][1]


def test_wildcard_layers_are_read_only() -> None:
    design = read_board(FIXTURE)
    fp = footprint_of(design, "D1")
    pad = dataclasses.replace(fp.pads[0], layers=("F.Cu", "B.Cu"))
    assert "layers" in read_only(design.replace_entity(pad))[0][1]


def test_graphic_moved_is_written() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    circle: Graphic = next(g for g in design.board.graphics if g.kind == "circle")
    moved = dataclasses.replace(circle, points=tuple(p.offset(1_000_000, 0) for p in circle.points))
    root = parse(write_board(design.replace_entity(moved), target=9).text)
    assert root.nodes("gr_circle")[0].find("center") == parse("(center 11 25)")
