# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A copper count change on a built board (capability layout-lens, "Copper layer changes across rebuilds"
and "Board content outside the design is kept", scenario "Copper count changed in the script"; change
c0102). Each test builds a blink variant, edits the board by token as KiCad would, and builds again."""

from __future__ import annotations

import dataclasses
from typing import cast

from _boards import four_layer_stackup
from _layout_edit import EDIT_UUIDS, add_items, edit_blink, net_ref
from _outlinehelp import board_text, build_script, codes, rebuild_script, variant

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.lens.build import BuildOutput
from fenolite.model.design import Design

TWO = "design.board(mm(50), mm(30))"
SETUP = "(pad_to_mask_clearance 0)"
STACKUP = (
    '(stackup (layer "F.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 1" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "In1.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 2" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "In2.Cu" (type "copper") (thickness 0.035)) '
    '(layer "dielectric 3" (type "core") (thickness 0.5) (epsilon_r 4.5) (loss_tangent 0.02)) '
    '(layer "B.Cu" (type "copper") (thickness 0.035)) (copper_finish "None") (dielectric_constraints no))'
)
"""A four-copper stack-up in KiCad's form, authored here with round values."""


def layers(copper: int) -> str:
    return TWO if copper == 2 else f"design.board(mm(50), mm(30), copper={copper})"


def read(output: BuildOutput) -> Design:
    return read_board(board_text(output))


def copper_names(design: Design) -> list[str]:
    assert design.board is not None
    return [layer.name for layer in design.board.layers if layer.kind == "copper"]


def kept(output: BuildOutput) -> list[str]:
    preserved = cast("dict[str, object]", output.summary["preserved"])
    return cast("list[str]", preserved["kept"])


def test_two_layers_become_four() -> None:
    first = build_script(variant())
    again = rebuild_script(variant(layers(4)), edit_blink(board_text(first)))
    assert again.files and "layout.copper-mismatch" not in codes(again)
    board = read(again)
    assert copper_names(board) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    (added,) = [i for i in again.issues if i.code == "kicad.layers.added"]
    assert added.severity == "info" and "In1.Cu" in added.message and "In2.Cu" in added.message
    assert board.board is not None
    uuids = {item.native_ids["kicad"] for item in (*board.board.tracks, *board.board.vias)}
    assert set(EDIT_UUIDS) <= uuids
    refs = {c.id: c.ref for c in board.circuit.components}
    (d1,) = [fp for fp in board.board.footprints if refs[fp.component_id] == "D1"]
    assert all(set(pad.layers) >= {"F.Cu", "In1.Cu", "In2.Cu", "B.Cu"} for pad in d1.pads)
    assert {"D1", "R1", "U1"} <= set(kept(again))


def test_copper_count_changed_in_the_script() -> None:
    first = build_script(variant())
    again = rebuild_script(variant(layers(4)), board_text(first))
    assert again.files and "kicad.layers.added" in codes(again)
    assert "layout.copper-mismatch" not in codes(again)
    assert copper_names(read(again)) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    # the adapted board is the board of a fresh four-layer build
    assert board_text(again) == board_text(build_script(variant(layers(4))))


def test_four_layers_become_six() -> None:
    first = build_script(variant(layers(4)))
    text = board_text(first)
    text = add_items(
        text,
        f'(segment (start 110 120) (end 120 120) (width 0.25) (layer "In1.Cu") {net_ref(text, "GND")} '
        '(uuid "00000000-0000-4000-8000-0000000d0001"))',
    )
    again = rebuild_script(variant(layers(6)), text)
    assert again.files
    board = read(again)
    assert copper_names(board) == ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
    (added,) = [i for i in again.issues if i.code == "kicad.layers.added"]
    assert "In3.Cu" in added.message and "In4.Cu" in added.message and "In1.Cu" not in added.message
    assert board.board is not None
    assert [(t.layer, t.native_ids["kicad"]) for t in board.board.tracks] == [
        ("In1.Cu", "00000000-0000-4000-8000-0000000d0001")
    ]
    assert not [code for code in codes(again) if code == "kicad.layers.removed"]


def test_four_layers_become_two() -> None:
    first = build_script(variant(layers(4)))
    text = board_text(first)
    gnd, zone = net_ref(text, "GND"), net_ref(text, "GND", zone=True)
    text = add_items(
        text,
        f'(segment (start 110 120) (end 120 120) (width 0.25) (layer "In1.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000d0001"))',
        f'(zone {zone} (layer "In2.Cu") (uuid "00000000-0000-4000-8000-0000000d0004") (name "inner") '
        "(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no) "
        "(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) "
        "(polygon (pts (xy 105 105) (xy 115 105) (xy 115 115) (xy 105 115))))",
    )
    again = rebuild_script(variant(), text)
    assert again.files
    written = board_text(again)
    assert "In1.Cu" not in written and "In2.Cu" not in written
    removed = {i.where: i for i in again.issues if i.code == "kicad.layers.removed"}
    assert sorted(removed) == ["In1.Cu", "In2.Cu"]
    assert "1 track" in removed["In1.Cu"].message and "1 zone" in removed["In2.Cu"].message
    assert removed["In1.Cu"].severity == "warning"
    assert board_text(again) == board_text(build_script(variant()))  # nothing of the inner layers is left


def test_a_stale_stackup_is_removed() -> None:
    first = build_script(variant(layers(4)))
    text = board_text(first)
    assert text.count(SETUP) == 1
    again = rebuild_script(variant(), text.replace(SETUP, f"{SETUP} {STACKUP}"))
    assert again.files and "kicad.layers.stackup-reset" in codes(again)
    assert "(stackup" not in board_text(again)
    # with the same count the stack-up is the board's and stays
    same = rebuild_script(variant(layers(4)), text.replace(SETUP, f"{SETUP} {STACKUP}"))
    assert "(stackup" in board_text(same) and "kicad.layers.stackup-reset" not in codes(same)


def test_a_read_stackup_goes_with_the_layers_it_names() -> None:
    # the four-layer board holds a complete stack-up, which the reader projects (c0101); built again as
    # two layers, the written board holds no stack-up and the build's model none either
    held = read(build_script(variant(layers(4))))
    assert held.board is not None
    held = dataclasses.replace(held, board=dataclasses.replace(held.board, stackup=four_layer_stackup()))
    text = write_board(held, target=10).text
    assert read_board(text).board.stackup is not None  # type: ignore[union-attr]
    again = rebuild_script(variant(), text)
    assert again.files and "kicad.layers.stackup-reset" in codes(again)
    assert not [code for code in codes(again) if code.startswith(("model.stackup", "kicad.board.stackup"))]
    written = board_text(again)
    assert "(stackup" not in written and "In1.Cu" not in written and "In2.Cu" not in written
    assert again.layout is not None and again.layout.board is not None
    assert again.layout.board.stackup is None and read_board(written).board.stackup is None  # type: ignore[union-attr]
    assert again.summary["stackup"] is None
    # with the same count the stack-up is the board's and stays
    same = rebuild_script(variant(layers(4)), text)
    assert "(stackup" in board_text(same) and "kicad.layers.stackup-reset" not in codes(same)
    assert cast("dict[str, object]", same.summary["stackup"])["copper"] == 4


def test_a_table_that_is_not_kicads() -> None:
    first = build_script(variant(layers(4)))
    text = board_text(first).replace('(6 "In2.Cu" signal)', '(8 "In3.Cu" signal)')
    assert text != board_text(first)
    again = rebuild_script(variant(layers(4)), text)
    assert dict(again.files) == {}
    (issue,) = [i for i in again.issues if i.code == "layout.copper-mismatch"]
    assert issue.severity == "error" and "In3.Cu" in issue.message and "--discard-layout" in issue.hint
    assert "copper=" not in issue.hint


def test_layers_added_in_kicad_and_the_script_left_at_four() -> None:
    """Six rows on the board and four in the script: the board follows the script again, and the two
    empty inner layers are removed with a line each."""
    first = build_script(variant(layers(4)))
    anchor = '\t\t(6 "In2.Cu" signal)\n'
    text = board_text(first)
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '\t\t(8 "In3.Cu" signal)\n\t\t(10 "In4.Cu" signal)\n')
    again = rebuild_script(variant(layers(4)), text)
    assert again.files and copper_names(read(again)) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    removed = [i.where for i in again.issues if i.code == "kicad.layers.removed"]
    assert removed == ["In3.Cu", "In4.Cu"]
    assert board_text(again) == board_text(first)
