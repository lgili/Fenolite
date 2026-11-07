# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The mask opening of vias through a conversion (change c0445; capability design-conversion, "Mask and paste
of imported pads"; altium-pcb-writer, "Via records"; kicad-file-backend, "Board mask margin in a written
board"). Authored values only."""

from __future__ import annotations

import dataclasses
import struct

import pytest

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.convert import openings
from fenolite.convert.altium_to_kicad import VIA_MASK_CHANGED, VIA_RULE_SCOPED, Ledger, board_mask
from fenolite.convert.to_altium import board_mask_margin
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, FootprintInstance, Outline, Pad
from fenolite.model.design import Design

MIL = 25_400


def _rule(scope: str, priority: int, expansion: str, **more: str) -> dict[str, str]:
    return {
        "RULEKIND": "SolderMaskExpansion",
        "ENABLED": "TRUE",
        "PRIORITY": str(priority),
        "SCOPE1EXPRESSION": scope,
        "EXPANSION": expansion,
        **more,
    }


def test_the_via_rule_is_the_first_of_scope_isvia_or_all() -> None:
    records = [_rule("All", 2, "3mil"), _rule("IsVia", 1, "1mil", SOLDERMASKFROMHOLE="TRUE")]
    assert openings.via_rule(records) == openings.ViaRule(MIL, from_hole=True, scoped=False)
    assert openings.via_rule([_rule("All", 1, "4mil")]) == openings.ViaRule(4 * MIL)
    assert openings.via_rule([]) == openings.ViaRule()


def test_a_pad_rule_is_no_via_rule_and_another_scope_is_reported() -> None:
    assert openings.via_rule([_rule("IsPad", 1, "2mil"), _rule("All", 2, "3mil")]) == openings.ViaRule(
        3 * MIL
    )
    scoped = openings.via_rule([_rule("InNet('GND')", 1, "2mil"), _rule("All", 2, "3mil")])
    assert scoped == openings.ViaRule(3 * MIL, scoped=True)


@pytest.mark.parametrize(
    ("state", "expansion", "rule", "margin"),
    [
        (openings.VIA_MODE_MANUAL, 2 * MIL, openings.ViaRule(MIL, from_hole=True), 2 * MIL),
        (openings.VIA_MODE_RULE, 4 * MIL, openings.ViaRule(MIL, from_hole=True), -4 * MIL),
        (0, 4 * MIL, openings.ViaRule(3 * MIL), 3 * MIL),
        (openings.VIA_MODE_RULE, 4 * MIL, openings.ViaRule(), None),
    ],
)
def test_the_margin_of_a_via(state: int, expansion: int, rule: openings.ViaRule, margin: int | None) -> None:
    """A 20 mil via with a 10 mil hole: from the hole, 1 mil opens 12 mil, a margin of -4 mil."""
    assert openings.via_margin(20 * MIL, 10 * MIL, state, expansion, rule) == margin


def _pad(ident: str, layers: tuple[str, ...], margin: int | None = None) -> Pad:
    return Pad(
        id=ident, number=ident, shape="rect", size=Size(MIL, MIL), position=Point(0, 0), layers=layers,
        mask_margin=margin,
    )  # fmt: skip


def _board() -> Board:
    pads = (
        _pad("pad_free", ("F.Cu", "F.Mask")),
        _pad("pad_own", ("F.Cu", "F.Mask"), 3 * MIL),
        _pad("pad_bare", ("F.Cu",)),
    )
    fp = FootprintInstance(id="fp", component_id="cmp", lib_ref="lib:fp", position=Point(0, 0), pads=pads)
    return Board(id="brd", footprints=(fp,))


def test_the_board_takes_the_most_frequent_margin_and_pads_keep_theirs() -> None:
    ledger = Ledger()
    board = board_mask(_board(), {"via_a": -4 * MIL, "via_b": -4 * MIL, "via_c": MIL}, ledger)
    assert board.mask_margin == -4 * MIL
    assert dict(ledger.changed["via"]) == {VIA_MASK_CHANGED: ["via_c"]}
    margins = {pad.id: pad.mask_margin for pad in board.footprints[0].pads}
    assert margins == {"pad_free": 0, "pad_own": 3 * MIL, "pad_bare": None}


def test_a_tie_takes_the_smaller_margin_and_no_via_changes_nothing() -> None:
    ledger = Ledger()
    assert board_mask(_board(), {"via_a": MIL, "via_b": -MIL}, ledger).mask_margin == -MIL
    assert board_mask(_board(), {}, Ledger()) == _board()
    zero = board_mask(_board(), {"via_a": 0}, Ledger())
    assert zero.mask_margin == 0 and zero.footprints == _board().footprints


def test_a_via_that_a_scoped_rule_may_govern_is_counted_once() -> None:
    ledger = Ledger()
    board_mask(_board(), {"via_a": MIL, "via_b": MIL, "via_c": -MIL}, ledger, scoped=("via_a", "via_c"))
    assert dict(ledger.changed["via"]) == {VIA_RULE_SCOPED: ["via_a"], VIA_MASK_CHANGED: ["via_c"]}


def test_the_kicad_board_holds_the_margin() -> None:
    corners = (Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 10_000_000), Point(0, 10_000_000))
    board = Board(
        id="brd", outline=Outline(id="out", points=corners), layers=created_layers(2), mask_margin=-101_600
    )
    design = Design.new("margin", seed=445)
    text = write_board(dataclasses.replace(design, board=board), target=10).text
    assert "(pad_to_mask_clearance -0.1016)" in text
    assert board_mask_margin(text) == -101_600
    assert board_mask_margin("(kicad_pcb (setup))") == 0


def test_the_via_record_holds_its_own_expansion() -> None:
    plain = rec.via_record(0, 0, 200_000, 100_000)[5:]
    own = rec.via_record(0, 0, 200_000, 100_000, mask=-40_000)[5:]
    assert struct.unpack_from("<i", plain, 54)[0] == 4 * 10_000 and plain[66] == 0
    assert struct.unpack_from("<i", own, 54)[0] == struct.unpack_from("<i", own, 242)[0] == -40_000
    assert own[66] == 2
