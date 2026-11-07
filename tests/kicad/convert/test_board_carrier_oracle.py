# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board properties of ``boardcarrier`` against kicad-cli (change c0434; H-K-FENOLITE-PROPS).

The board is the committed ``tests/data/kicad/board/two_layer.kicad_pcb`` with two ``Fenolite.Altium.*``
properties: a short value and an 80 kB one (60 000 random bytes, which zlib cannot shrink). Every run
happens in ``tmp_path`` because KiCad writes a ``.kicad_prl`` next to the board.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from _kicad import run, run_raw

from fenolite.backends.kicad import boardcarrier

pytestmark = pytest.mark.needs_kicad
BOARD = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _board(tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
    items = {"Fenolite.Altium.Rules6": b"rules", "Fenolite.Altium.Large": os.urandom(60_000)}
    board = tmp_path / "carrier.kicad_pcb"  # a 9.0 board (20241229), which 10.0 reads too
    board.write_text(boardcarrier.with_carried(BOARD.read_text(encoding="utf-8"), items), encoding="utf-8")
    return board, items


def test_kicad_loads_a_board_with_carried_properties(tmp_path: Path) -> None:
    board, _items = _board(tmp_path)
    svg = tmp_path / "carrier.svg"
    result = run_raw("pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", svg, board)
    assert result.returncode == 0, result.stderr


@pytest.mark.kicad_min_major(10)
def test_a_resave_keeps_the_carried_properties(tmp_path: Path) -> None:
    board, items = _board(tmp_path)
    run("pcb", "upgrade", "--force", board)
    assert boardcarrier.carried(board.read_text(encoding="utf-8")) == items
