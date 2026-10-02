# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper items follow their nets, at the function level (capability layout-lens; change c0019)."""

from __future__ import annotations

from _buildhelp import blink
from _layout_edit import EDIT_UUIDS, add_filled_zone, edit_blink
from _preserve_help import board_text, merged


def test_items_on_surviving_nets_are_kept() -> None:
    result, board = merged(blink(), board_text(9, edit=edit_blink), target=9)
    assert result.design.board is not None and board.board is not None
    nets = {n.id: n.name for n in result.design.circuit.nets}
    kept = {t.native_ids["kicad"]: nets[t.net_id or ""] for t in result.design.board.tracks}
    assert kept == {EDIT_UUIDS[0]: "LED_A", EDIT_UUIDS[1]: "LED_A"}
    assert {t.id for t in result.design.board.tracks} == {t.id for t in board.board.tracks}


def test_items_on_a_removed_net_are_dropped() -> None:
    d = blink()
    d.parts["R1"].connections.pop("2")
    d.parts["D1"].connections.pop("2")
    del d.nets["LED_A"]
    result, _ = merged(d, board_text(edit=lambda t: add_filled_zone(edit_blink(t), net="GND", layer="B.Cu")))
    assert result.design.board is not None
    assert (
        not result.design.board.tracks
        and not result.design.board.vias
        and len(result.design.board.zones) == 1
    )
    (found,) = [i for i in result.issues if i.code == "layout.net-removed"]
    assert "LED_A" in found.message and "2 tracks" in found.message and "1 vias" in found.message
    assert result.summary["dropped"] == {"tracks": 2, "arcs": 0, "vias": 1, "zones": 0}
