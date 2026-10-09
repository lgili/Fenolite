# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``layers.merge_layers``: rows, items on removed layers, re-projected pads and the stack-up (capability
layout-lens, "Copper layer changes across rebuilds", unit half; change c0102). The boards are builds of the
blink edited by token, as KiCad would; the stack-up texts are authored here with round values."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import four_layer_stackup
from _layout_edit import add_items, net_ref
from _outlinehelp import board_text, build_script, variant

from fenolite.backends.kicad.layers import MERGE_ISSUE_CODES, LayerMerge, created_layers, merge_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.model.design import Design

FOUR = "design.board(mm(50), mm(30), copper=4)"
SETUP = "(pad_to_mask_clearance 0)"


def built(copper: int = 2) -> str:
    board = (
        "design.board(mm(50), mm(30))" if copper == 2 else f"design.board(mm(50), mm(30), copper={copper})"
    )
    return board_text(build_script(variant(board)))


def copper_names(design: Design) -> list[str]:
    assert design.board is not None
    return [layer.name for layer in design.board.layers if layer.kind == "copper"]


def stackup(*copper: str) -> str:
    """A ``stackup`` node of the copper layers ``copper`` with a dielectric between each pair."""
    rows: list[str] = []
    for index, name in enumerate(copper):
        if index:
            rows.append(
                f'(layer "dielectric {index}" (type "core") (thickness 0.5) (material "FR4") '
                "(epsilon_r 4.5) (loss_tangent 0.02))"
            )
        rows.append(f'(layer "{name}" (type "copper") (thickness 0.035))')
    return f'(stackup {" ".join(rows)} (copper_finish "None") (dielectric_constraints no))'


def with_stackup(text: str, *copper: str) -> str:
    assert text.count(SETUP) == 1
    return text.replace(SETUP, f"{SETUP} {stackup(*copper)}")


def inner_items(text: str) -> str:
    """A four-layer build with a segment and a blind via on ``In1.Cu``, a zone on ``In2.Cu``, a zone on
    ``F.Cu`` and ``In2.Cu``, a through via, and a line and a text on ``In1.Cu``."""
    gnd = net_ref(text, "GND")
    zone = net_ref(text, "GND", zone=True)
    box = "(polygon (pts (xy 105 105) (xy 115 105) (xy 115 115) (xy 105 115)))"
    settings = (
        "(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no) "
        "(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))"
    )
    return add_items(
        text,
        f'(segment (start 110 120) (end 120 120) (width 0.25) (layer "In1.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0001"))',
        f'(via blind (at 110 120) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0002"))',
        f'(via (at 125 120) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0003"))',
        f'(zone {zone} (layer "In2.Cu") (uuid "00000000-0000-4000-8000-0000000d0004") (name "inner") '
        f"{settings} {box})",
        f'(zone {zone} (layers "F.Cu" "In2.Cu") (uuid "00000000-0000-4000-8000-0000000d0005") (name "two") '
        f"{settings} {box})",
        '(gr_line (start 101 101) (end 105 101) (stroke (width 0.1) (type solid)) (layer "In1.Cu") '
        '(uuid "00000000-0000-4000-8000-0000000d0006"))',
        '(gr_text "INNER" (at 110 103 0) (layer "In1.Cu") (uuid "00000000-0000-4000-8000-0000000d0007") '
        "(effects (font (size 1 1) (thickness 0.15))))",
    )


def codes(merge: LayerMerge) -> list[str]:
    return [found.code for found in merge.issues]


def test_the_closed_table() -> None:
    assert dict(MERGE_ISSUE_CODES) == {
        "kicad.layers.removed": "warning",
        "kicad.layers.stackup-reset": "warning",
        "kicad.layers.added": "info",
    }


def test_the_same_count_and_a_table_that_is_not_created_are_left_alone() -> None:
    board = read_board(built(4))
    same = merge_layers(board, 4)
    assert same.board is board and same.issues == () and same.added == same.removed == ()
    odd = read_board(built(4).replace('(6 "In2.Cu" signal)', '(8 "In3.Cu" signal)'))
    assert copper_names(odd) == ["F.Cu", "In1.Cu", "In3.Cu", "B.Cu"]
    left = merge_layers(odd, 2)
    assert left.board is odd and left.issues == ()
    with pytest.raises(ValueError, match="copper layers"):
        merge_layers(board, 3)


@pytest.mark.parametrize("target", [9, 10])
def test_two_layers_become_four(target: int) -> None:
    text = board_text(build_script(variant(), target))
    board = read_board(text)
    merge = merge_layers(board, 4)
    assert copper_names(merge.board) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert merge.added == ("In1.Cu", "In2.Cu") and merge.removed == ()
    assert codes(merge) == ["kicad.layers.added"] and merge.issues[0].severity == "info"
    assert "In1.Cu" in merge.issues[0].message and "In2.Cu" in merge.issues[0].message
    assert merge.board.board is not None and board.board is not None
    # the rows that stay keep their bags; the new rows are those of a created table
    wanted = {layer.name: layer for layer in created_layers(4)}
    for layer in merge.board.board.layers:
        if layer.name in merge.added:
            assert layer.ext == wanted[layer.name].ext
        else:
            (old,) = [found for found in board.board.layers if found.name == layer.name]
            assert layer.ext == old.ext and layer.id == old.id
    assert [layer.ordinal for layer in merge.board.board.layers] == list(range(len(merge.board.board.layers)))
    # the through-hole pads of D1 are on the four copper layers, copper first in table order
    refs = {c.id: c.ref for c in merge.board.circuit.components}
    (d1,) = [fp for fp in merge.board.board.footprints if refs[fp.component_id] == "D1"]
    assert all(pad.layers[:4] == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") for pad in d1.pads)
    # and the writer accepts the adapted board: no projection is read-only
    written = write_board(merge.board, target=target).text
    assert copper_names(read_board(written)) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert '(layers "*.Cu" "*.Mask")' in written


def test_four_layers_become_six() -> None:
    merge = merge_layers(read_board(inner_items(built(4))), 6)
    assert copper_names(merge.board) == ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
    assert merge.added == ("In3.Cu", "In4.Cu") and codes(merge) == ["kicad.layers.added"]
    assert merge.board.board is not None
    assert len(merge.board.board.tracks) == 1 and len(merge.board.board.vias) == 2
    assert len(merge.board.board.zones) == 2
    numbers = [dict(layer.ext["kicad"].payload)["number"] for layer in merge.board.board.layers[:6]]
    assert numbers == ["0", "4", "6", "8", "10", "2"]


def test_four_layers_become_two() -> None:
    board = read_board(inner_items(built(4)))
    merge = merge_layers(board, 2)
    assert copper_names(merge.board) == ["F.Cu", "B.Cu"]
    assert merge.removed == ("In1.Cu", "In2.Cu") and merge.added == ()
    assert codes(merge) == ["kicad.layers.removed", "kicad.layers.removed"]
    first, second = merge.issues
    assert first.where == "In1.Cu" and first.severity == "warning"
    for words in ("1 track", "0 arcs", "1 via", "0 zones", "1 graphic", "1 text"):
        assert words in first.message, words
    assert second.where == "In2.Cu" and "2 zones" in second.message and "0 tracks" in second.message
    model = merge.board.board
    assert model is not None
    assert model.tracks == () and [via.layers for via in model.vias] == [("F.Cu", "B.Cu")]
    assert [(zone.name, zone.layers) for zone in model.zones] == [("two", ("F.Cu",))]
    assert all(g.layer != "In1.Cu" for g in model.graphics) and model.texts == ()
    written = write_board(merge.board, target=10).text
    assert "In1.Cu" not in written and "In2.Cu" not in written
    assert copper_names(read_board(written)) == ["F.Cu", "B.Cu"]


def test_a_smaller_count_removes_the_deepest_layers() -> None:
    merge = merge_layers(read_board(built(8)), 4)
    assert copper_names(merge.board) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert merge.removed == ("In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu")
    assert codes(merge) == ["kicad.layers.removed"] * 4


def test_a_stale_stackup_is_removed() -> None:
    text = with_stackup(built(4), "F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    merge = merge_layers(read_board(text), 2)
    assert codes(merge)[-1] == "kicad.layers.stackup-reset" and merge.issues[-1].severity == "warning"
    written = write_board(merge.board, target=10).text
    assert "(stackup" not in written and "(pad_to_mask_clearance 0)" in written
    added = merge_layers(read_board(text), 6)
    assert codes(added) == ["kicad.layers.added", "kicad.layers.stackup-reset"]


def test_a_stale_stackup_of_the_model_is_removed_with_its_node() -> None:
    # a complete stack-up is read into ``Board.stackup`` (c0101): the reduced table takes both away, the
    # node of ``setup`` and the model's value, or the writer is asked for four copper rows on two layers
    held = read_board(built(4))
    assert held.board is not None
    held = dataclasses.replace(held, board=dataclasses.replace(held.board, stackup=four_layer_stackup()))
    board = read_board(write_board(held, target=10).text)
    assert board.board is not None and board.board.stackup is not None
    assert [e.name for e in board.board.stackup.layers if e.kind == "copper"] == [
        "F.Cu",
        "In1.Cu",
        "In2.Cu",
        "B.Cu",
    ]
    merge = merge_layers(board, 2)
    assert codes(merge).count("kicad.layers.stackup-reset") == 1
    assert merge.board.board is not None and merge.board.board.stackup is None
    assert not [found for found in merge.board.validate() if found.code.startswith("model.stackup")]
    written = write_board(merge.board, target=10).text
    assert "(stackup" not in written and "In1.Cu" not in written and "(pad_to_mask_clearance 0)" in written
    again = read_board(written)
    assert again.board is not None and again.board.stackup is None
    # the same count keeps the model's stack-up and its node
    same = merge_layers(board, 4)
    assert same.board is board and "(stackup" in write_board(same.board, target=10).text


def test_a_stackup_of_the_new_table_is_kept() -> None:
    # six rows over a four-layer stack-up: a script of four layers matches it again
    text = with_stackup(built(6), "F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    merge = merge_layers(read_board(text), 4)
    assert "kicad.layers.stackup-reset" not in codes(merge)
    assert "(stackup" in write_board(merge.board, target=10).text
