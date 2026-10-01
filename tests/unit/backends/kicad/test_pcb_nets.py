# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nets in both forms (capability kicad-file-backend, change c0009)."""

from __future__ import annotations

from _boards import FIXTURE, SCENARIOS

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.errors import Issue
from fenolite.model.base import Opaque


def test_numbered_table() -> None:
    design = read_board(FIXTURE)
    nets = [(n.name, n.ext["kicad"].payload) for n in design.circuit.nets]
    assert nets == [("GND", (("number", "1"),)), ("VCC", (("number", "2"),)), ("LED_A", (("number", "3"),))]
    assert all(n.netclass_id is None for n in design.circuit.nets)


def test_net_zero_stays_opaque() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    root = slotlib.from_ext(design.board.ext["kicad"])
    assert Opaque('(net 0 "")', "20240108") in root  # inventory row board-net-table (since 8.0)


def test_name_form() -> None:
    design = read_board(SCENARIOS["name-form"])
    assert design.board is not None
    (net,) = design.circuit.nets
    assert net.name == "GND" and net.ext == {}
    assert design.board.tracks[0].net_id == net.id


def test_unknown_net_number() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["unknown-net"], issues=issues)
    assert design.board is not None
    track = design.board.tracks[0]
    assert track.net_id is None
    assert isinstance(slotlib.from_ext(track.ext["kicad"])[4], Opaque)
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.unknown-net", "warning")]
    assert "7" in issues[0].message


def test_net_members_from_pads() -> None:
    design = read_board(FIXTURE)
    led_a = design.nets_by_name["LED_A"]
    r1, d1 = design.by_ref["R1"], design.by_ref["D1"]
    assert [(m.component_id, m.pin) for m in led_a.members] == [(r1.id, "2"), (d1.id, "2")]
    assert len(design.by_net["LED_A"]) == 2
