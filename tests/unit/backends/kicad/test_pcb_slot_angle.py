# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A slotted hole on a board pad at any angle is written as it was read (capability kicad-file-backend).

The slot's axis is held in the pad's own frame, so the angle of the pad and of its footprint play no part:
a pad at 45° keeps the oval drill KiCad wrote.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board, write_board

ROOT = Path(__file__).resolve().parents[4]
BOARD = ROOT / "tests" / "data" / "kicad" / "routing" / "two_pads.kicad_pcb"


@pytest.mark.parametrize("footprint", ["", " 30", " 90", " 225"])
@pytest.mark.parametrize("angle", ["", " 45", " 90", " 135", " 270", " 12.5"])
@pytest.mark.parametrize("drill", ["(drill oval 0.4 0.8)", "(drill oval 0.8 0.4)"])
def test_slot_on_a_rotated_board_pad_round_trips(footprint: str, angle: str, drill: str) -> None:
    """The pad angle on a board is absolute; the footprint's own angle is part of it."""
    text = BOARD.read_text(encoding="utf-8")
    pad = '\t\t(pad "1" thru_hole circle\n\t\t\t(at 0 0)'
    placed = '\t\t(uuid "d3805f64-fcb4-5d39-b318-2ebfbd689950")\n\t\t(at 0 0)'
    assert text.count(pad) == 2 and text.count("(drill 0.4)") == 2 and text.count(placed) == 1
    text = text.replace(placed, placed.replace("(at 0 0)", f"(at 0 0{footprint})"))
    text = text.replace(pad, pad.replace("(at 0 0)", f"(at 0 0{angle})"), 1).replace("(drill 0.4)", drill, 1)
    design = read_board(text, file="two_pads.kicad_pcb")
    assert write_board(design, target=10).text == text
    assert design.board is not None
    slots = [p for fp in design.board.footprints for p in fp.pads if p.padstack is not None]
    assert len(slots) == 1 and slots[0].padstack is not None
    # the model holds the axis in the pad's own frame, whatever the angles of the pad and the footprint
    assert slots[0].padstack.hole_rotation == (90_000_000 if drill.endswith("0.4 0.8)") else 0)
