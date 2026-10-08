# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board given by ``board(outline=…)`` takes a stack-up, rule areas and board drawings as a rectangle
does (capability design-dsl, "Stack-up in the DSL" of change c0101 and "Rule areas in the DSL" and
"Board drawings in the DSL" of change c0103, scenarios "A shaped board takes a stack-up" and "A shaped
board takes rule areas and drawings"). No tool runs."""

from __future__ import annotations

import pytest
from _outlinehelp import BOARD, ROUNDED, board_text, build_script, variant

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.dsl import Design, DslError, mm, shape, stack, to_model
from fenolite.model.board import Board

ITEMS = (
    "from fenolite.dsl import stack\n"
    'design.stackup(stack.mask("10um"), stack.copper("35um"), stack.core("1.5mm", material="FR4"),'
    ' stack.copper("35um"), stack.mask("10um"), finish="ENIG")\n'
    'design.rule_area("ANT", [(mm(40), mm(10)), (mm(48), mm(10)), (mm(48), mm(14)), (mm(40), mm(14))],'
    ' forbid=("tracks", "vias"))\n'
    'design.rule_area("HV", [(mm(30), mm(16)), (mm(36), mm(16)), (mm(36), mm(20)), (mm(30), mm(20))])\n'
    'design.text("rev", "REV A", (mm(4), mm(4)))\n'
    'design.line("fab/edge", (mm(4), mm(15)), (mm(46), mm(15)), layer="F.Fab", width=mm(0.1))\n'
    'design.rect("r", (mm(6), mm(6)), (mm(8), mm(7)), layer="F.Fab", width=mm(0.1))\n'
    'design.circle("c", (mm(10), mm(10)), (mm(11), mm(10)), layer="B.SilkS", width=mm(0.12))\n'
    'design.arc("a", (mm(12), mm(12)), (mm(13), mm(13)), (mm(14), mm(12)), layer="Eco1.User",'
    " width=mm(0.1))\n"
    'design.polygon("p", [(mm(16), mm(4)), (mm(18), mm(4)), (mm(17), mm(6))], layer="B.Fab", width=mm(0.1))\n'
    'design.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))\n'
)
"""A stack-up, two rule areas and one drawing of each of the seven calls, all inside both boards."""


def shaped() -> Design:
    design = Design("shaped")
    design.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)), copper=4)
    return design


def test_the_calls_accept_a_board_given_by_a_path() -> None:
    """Before the fix each call raised "call board() first" or "is called after board()" here."""
    design = shaped()
    design.cutout(shape.circle(mm(45), mm(5), mm(3.2)))
    design.stackup(
        stack.copper("35um"),
        stack.prepreg("0.2mm"),
        stack.copper("35um"),
        stack.core("1.0mm"),
        stack.copper("35um"),
        stack.prepreg("0.2mm"),
        stack.copper("35um"),
    )
    design.rule_area("HV", [(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5))], layers=("In1.Cu",))
    design.text("rev", "REV A", (mm(2), mm(2)))
    design.line("l", (mm(2), mm(8)), (mm(9), mm(8)), layer="F.Fab", width=mm(0.1))
    design.rect("r", (mm(1), mm(1)), (mm(3), mm(2)), layer="F.Fab", width=mm(0.1))
    design.circle("c", (mm(5), mm(5)), (mm(6), mm(5)), layer="B.SilkS", width=mm(0.12))
    design.arc("a", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(0)), layer="Eco1.User", width=mm(0.1))
    design.polygon("p", [(mm(0), mm(0)), (mm(2), mm(0)), (mm(1), mm(2))], layer="B.Fab", width=mm(0.1))
    design.dimension("w", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-3))
    assert design.size is None and design.stack is not None
    assert list(design.rule_areas) == ["HV"]
    assert list(design.drawings) == ["rev", "l", "r", "c", "a", "p", "w"]
    board = to_model(design).board
    assert board is not None and board.stackup is not None and board.outline is not None
    assert len(board.outline.cutouts) == 1 and [k.name for k in board.keepouts] == ["HV"]


def test_the_calls_before_board_are_still_refused() -> None:
    design = Design("shaped")
    with pytest.raises(DslError, match=r"after board\(\)"):
        design.stackup(stack.copper("35um"), stack.core("1.5mm"), stack.copper("35um"))
    with pytest.raises(DslError, match=r"call board\(\) first"):
        design.rule_area("HV", [(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5))])
    with pytest.raises(DslError, match=r"text\(\): call board\(\) first"):
        design.text("rev", "REV A", (mm(2), mm(2)))
    with pytest.raises(DslError, match=r"dimension\(\): call board\(\) first"):
        design.dimension("w", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-3))
    assert design.stack is None and not design.rule_areas and not design.drawings


def stackup_node(text: str) -> str:
    setup = parse(text).find("setup")
    assert setup is not None
    found = setup.find("stackup")
    assert isinstance(found, Node)
    return dumps(found)


def items(board: Board) -> tuple[object, ...]:
    return (
        [(k.name, k.layers, k.outline, k.no_tracks, k.no_vias, k.native_ids) for k in board.keepouts],
        [(t.text, t.layer, t.position, t.native_ids) for t in board.texts],
        [(g.layer, g.native_ids) for g in board.graphics if g.layer != "Edge.Cuts"],
        [(d.kind, d.start, d.end, d.offset, d.native_ids) for d in board.dimensions],
    )


@pytest.mark.parametrize("target", [9, 10])
def test_a_rounded_board_writes_the_stackup_and_items_of_the_rectangle(target: int) -> None:
    """The rounded board with cut-outs writes the stack-up, rule areas and drawings that the rectangle of
    the same size writes, with the same uuids; only its edge differs."""
    rectangle = build_script(variant(BOARD, append=ITEMS), target)
    rounded = build_script(variant(ROUNDED, append=ITEMS), target)
    for output in (rectangle, rounded):
        assert not [i for i in output.issues if i.severity == "error"], [i.code for i in output.issues]
        assert output.summary["board_items"] == {"rule_areas": 2, "texts": 1, "graphics": 5, "dimensions": 1}
    assert stackup_node(board_text(rounded)) == stackup_node(board_text(rectangle))
    assert '(copper_finish "ENIG")' in stackup_node(board_text(rounded))
    assert '(material "FR4")' in stackup_node(board_text(rounded))
    read_rect, read_round = read_board(board_text(rectangle)).board, read_board(board_text(rounded)).board
    assert read_rect is not None and read_round is not None
    assert items(read_round) == items(read_rect)
    assert [k.name for k in read_round.keepouts] == ["ANT", "HV"]
