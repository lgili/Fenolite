# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A slotted hole on a board pad at any angle is written as it was read (capability kicad-file-backend).

A board stores a pad's angle absolute, and the reader adds it to the slot's own turn. The writer has to
take it out again; a pad at 45° otherwise has a slot the writer refuses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board, write_board

ROOT = Path(__file__).resolve().parents[4]
BOARD = ROOT / "tests" / "data" / "kicad" / "routing" / "two_pads.kicad_pcb"


@pytest.mark.parametrize("angle", ["", " 45", " 90", " 135", " 270", " 12.5"])
@pytest.mark.parametrize("drill", ["(drill oval 0.4 0.8)", "(drill oval 0.8 0.4)"])
def test_slot_on_a_rotated_board_pad_round_trips(angle: str, drill: str) -> None:
    text = BOARD.read_text(encoding="utf-8")
    pad = '\t\t(pad "1" thru_hole circle\n\t\t\t(at 0 0)'
    assert text.count(pad) == 2 and text.count("(drill 0.4)") == 2
    text = text.replace(pad, pad.replace("(at 0 0)", f"(at 0 0{angle})"), 1).replace("(drill 0.4)", drill, 1)
    design = read_board(text, file="two_pads.kicad_pcb")
    assert write_board(design, target=10).text == text
