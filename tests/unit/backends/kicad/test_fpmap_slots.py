# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots turned against the X and Y of their pad (capability design-conversion, "Slots of a converted
Altium board"; change c0161, task 2.4).

KiCad's oval drill lies along the X or the Y of its pad, so ``_fpmap.emit_pad`` writes a slot at another
angle in a pad with round copper by turning the pad to the slot's axis; the copper and the hole stay those
of the source. Any other pad with such a slot is refused by the writer, and the conversion reports it lost.
"""

from __future__ import annotations

import dataclasses

import pytest
from _boards import created_board

from fenolite.backends.kicad._fpmap import round_copper, slot_turn
from fenolite.backends.kicad.mod import write_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Size
from fenolite.model.board import Pad, Padstack
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MM = 1_000_000
TURN = 45_000_000


def _slot_pad(pad: Pad, *, shape: str = "circle", size: Size = Size(2 * MM, 2 * MM), turn: int = TURN) -> Pad:
    stack = Padstack(
        id=pad.id.replace("pad_", "pst_"), hole_shape="slot", hole_length=3 * MM, hole_rotation=turn
    )
    return dataclasses.replace(
        pad, kind="thru_hole", shape=shape, size=size, drill=MM, padstack=stack,  # type: ignore[arg-type]
        layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"), zone_connection=None,
    )  # fmt: skip


def _board(pad: Pad) -> Design:
    design = created_board(2)
    assert design.board is not None
    fp = design.board.footprints[0]
    turned = dataclasses.replace(fp, pads=(pad, *fp.pads[1:]), attributes=("through_hole",))
    return dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(turned,)))


def test_round_pad_with_a_turned_slot() -> None:
    """Scenario "Round pad with a turned slot": a round pad of 2 mm with a slot of 1 x 3 mm at 45°."""
    design = _board(_slot_pad(created_board(2).board.footprints[0].pads[0]))  # type: ignore[union-attr]
    pad = design.board.footprints[0].pads[0]  # type: ignore[union-attr]
    assert round_copper(pad) and slot_turn(pad) == TURN
    for target in (9, 10):
        text = write_board(design, target=target).text
        assert "(drill oval 3 1)" in text
        back = read_board(text)
        assert back.board is not None
        (read,) = [p for p in back.board.footprints[0].pads if p.number == "1"]
        assert read.shape == "circle" and read.size == pad.size and read.drill == MM
        assert read.padstack is not None and read.padstack.hole_length == 3 * MM
        # the pad turned to the slot: the slot's axis on the board is the source's
        assert (read.rotation + read.padstack.hole_rotation) % 180_000_000 == TURN


@pytest.mark.parametrize(("shape", "size"), [("oval", Size(3 * MM, 2 * MM)), ("rect", Size(2 * MM, 2 * MM))])
def test_other_pads_refuse_a_turned_slot(shape: str, size: Size) -> None:
    pad = _slot_pad(created_board(2).board.footprints[0].pads[0], shape=shape, size=size)  # type: ignore[union-attr]
    assert not round_copper(pad) and slot_turn(pad) == 0
    with pytest.raises(ValueError, match="slot rotation"):
        write_board(_board(pad), target=10)


def test_aligned_slots_are_written_as_before() -> None:
    for turn in (0, 90_000_000):
        pad = _slot_pad(created_board(2).board.footprints[0].pads[0], turn=turn)  # type: ignore[union-attr]
        assert slot_turn(pad) == 0
        assert "(drill oval" in write_board(_board(pad), target=10).text


def test_library_footprint_with_a_turned_slot() -> None:
    pad = _slot_pad(created_board(2).board.footprints[0].pads[0])  # type: ignore[union-attr]
    pad = dataclasses.replace(pad, net_id=None, native_ids={}, ext={})
    defn = FootprintDef(id="fpd_00000000-0000-4000-8000-000000000001", name="Slot", library="t", pads=(pad,))
    text = write_footprint(defn, target=10)
    assert "(drill oval 3 1)" in text and "(at -1.27 0 45)" in text
