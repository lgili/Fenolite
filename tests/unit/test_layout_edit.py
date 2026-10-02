# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The token-edit helper of the layout tests (change c0019, task 2.1), without KiCad."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build
from _layout_edit import D1_SHIFT, EDIT_UUIDS, ZONE_UUID, add_filled_zone, edit_blink, pad_position

from fenolite.backends.kicad.pcb import read_board


def board_text(target: int) -> str:
    return build(blink(), target).files["blink.kicad_pcb"].decode("utf-8")


@pytest.mark.parametrize("target", [9, 10])
def test_edited_blink_reads_back(target: int) -> None:
    text = board_text(target)
    edited = edit_blink(text)
    before, after = read_board(text), read_board(edited)
    assert before.board is not None and after.board is not None
    refs = {c.id: c.ref for c in after.circuit.components}
    old = {refs[f.component_id]: f.position for f in before.board.footprints}  # type: ignore[index]
    new = {refs[f.component_id]: f.position for f in after.board.footprints}  # type: ignore[index]
    assert new["D1"].x == old["D1"].x + D1_SHIFT and new["D1"].y == old["D1"].y
    assert new["R1"] == old["R1"] and new["U1"] == old["U1"]
    nets = {n.id: n.name for n in after.circuit.nets}
    tracks = {t.native_ids["kicad"]: t for t in after.board.tracks}
    vias = {v.native_ids["kicad"]: v for v in after.board.vias}
    seg_f, seg_b, via = EDIT_UUIDS
    assert tracks[seg_f].layer == "F.Cu" and tracks[seg_b].layer == "B.Cu" and via in vias
    assert {nets[tracks[seg_f].net_id], nets[tracks[seg_b].net_id], nets[vias[via].net_id]} == {"LED_A"}  # type: ignore[index]
    assert tracks[seg_f].start == pad_position(edited, "R1", "2")
    assert tracks[seg_b].end == pad_position(edited, "D1", "2")


@pytest.mark.parametrize("target", [9, 10])
def test_filled_zone(target: int) -> None:
    edited = add_filled_zone(board_text(target), net="GND", layer="B.Cu")
    design = read_board(edited)
    assert design.board is not None
    (zone,) = [z for z in design.board.zones if z.native_ids.get("kicad") == ZONE_UUID]
    assert len(zone.fills) == 2 and {n.name for n in design.circuit.nets if n.id == zone.net_id} == {"GND"}
