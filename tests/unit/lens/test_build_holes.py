# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board holes in a build (capability design-dsl, "Board holes in a build"; change c0102): the parts of
``design.hole()`` are built as parts with authored definitions, with no step of their own."""

from __future__ import annotations

import pytest
from _outlinehelp import HOLES, board_text, build_script, codes, rebuild_script, variant

from fenolite.backends.kicad.frame import placed_extents
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design

MM = 1_000_000
NPTH = "lib/Fenolite_Holes.pretty/NPTH_3.2mm.kicad_mod"
PTH = "lib/Fenolite_Holes.pretty/PTH_3.2mm_Pad_6mm.kicad_mod"
SYMBOLS = "lib/Fenolite_Holes.kicad_sym"


def footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    (found,) = [fp for fp in design.board.footprints if refs[fp.component_id] == ref]
    return found


@pytest.mark.parametrize("target", [9, 10])
def test_holes_in_a_build(target: int) -> None:
    output = build_script(variant(append=HOLES), target)
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    assert {NPTH, PTH, SYMBOLS} <= set(output.files)
    board = read_board(board_text(output))
    h1, h2 = footprint(board, "H1"), footprint(board, "H2")
    assert [(pad.number, pad.kind) for pad in h1.pads] == [("", "np_thru_hole")]
    assert [(pad.number, pad.kind) for pad in h2.pads] == [("1", "thru_hole")]
    nets = {net.id: net.name for net in board.circuit.nets}
    assert nets[h2.pads[0].net_id or ""] == "GND" and h1.pads[0].net_id is None
    for fp in (h1, h2):
        assert {"exclude_from_pos_files", "exclude_from_bom"} <= set(fp.attributes)
        assert fp.locked and fp.side == "top"
    assert h1.position == Point(104 * MM, 104 * MM) and h2.position == Point(146 * MM, 104 * MM)
    assert h1.lib_ref == "Fenolite_Holes:NPTH_3.2mm" and h2.lib_ref == "Fenolite_Holes:PTH_3.2mm_Pad_6mm"
    assert "build.pad-without-pin" not in codes(output)


def test_the_written_definitions_carry_flags_pad_and_courtyards() -> None:
    output = build_script(variant(append=HOLES))
    text = output.files[NPTH].decode("utf-8")
    assert "(attr exclude_from_pos_files exclude_from_bom)" in text
    assert text.count('(pad "" np_thru_hole circle') == 1 and '(layers "*.Cu" "*.Mask")' in text
    definition = read_footprint(text)
    yards = sorted(g.layer for g in definition.graphics if g.layer.endswith(".CrtYd"))
    assert yards == ["B.CrtYd", "F.CrtYd"]
    symbols = output.files[SYMBOLS].decode("utf-8")
    assert '(symbol "Hole"' in symbols and '(symbol "Hole_Pad"' in symbols
    assert symbols.count("(in_bom no)") == 2 and symbols.count("(pin passive line") == 1
    rows = output.files["fp-lib-table"].decode("utf-8") + output.files["sym-lib-table"].decode("utf-8")
    assert rows.count('(name "Fenolite_Holes")') == 2


def test_only_the_definitions_used_are_written() -> None:
    output = build_script(variant(append='design.hole("H1", mm(4), mm(4), drill=mm(3.2))\n'))
    assert NPTH in output.files and PTH not in output.files
    assert '(symbol "Hole_Pad"' not in output.files[SYMBOLS].decode("utf-8")


def test_a_hole_is_judged_by_its_courtyards_on_both_sides() -> None:
    """The placement guard reads the extents of the built board: a hole has one on each side."""
    output = build_script(variant(append='design.hole("H3", mm(32), mm(9), drill=mm(1), courtyard=mm(3))\n'))
    board = read_board(board_text(output))
    h3 = footprint(board, "H3")
    (extent,) = [found for found in placed_extents(board) if found.footprint_id == h3.id]
    assert extent.source == "courtyard" and extent.front and extent.back
    for face in (extent.front, extent.back):
        xs = [p.x for ring in face for p in ring]
        assert max(xs) - min(xs) == pytest.approx(3 * MM, abs=60_000)
    # a part without a back courtyard has none: the blink's resistor
    (r1,) = [found for found in placed_extents(board) if found.footprint_id == footprint(board, "R1").id]
    assert r1.front and not r1.back


def test_holes_rebuild_to_the_same_bytes() -> None:
    first = build_script(variant(append=HOLES), 9)
    again = rebuild_script(variant(append=HOLES), board_text(first), 9)
    assert dict(again.files) == dict(first.files)
    assert not [code for code in codes(again) if code.startswith("layout.place")]


def test_a_locked_hole_wins_over_a_move_in_kicad() -> None:
    from _layout_edit import move_footprint

    first = build_script(variant(append=HOLES))
    moved = move_footprint(board_text(first), "H1", 2 * MM, 0)
    again = rebuild_script(variant(append=HOLES), moved)
    assert "layout.place-forced" in codes(again)
    assert footprint(read_board(board_text(again)), "H1").position == Point(104 * MM, 104 * MM)
    free = HOLES.replace("drill=mm(3.2))", "drill=mm(3.2), locked=False)", 1)
    unlocked = rebuild_script(variant(append=free), moved)
    assert footprint(read_board(board_text(unlocked)), "H1").position == Point(106 * MM, 104 * MM)
