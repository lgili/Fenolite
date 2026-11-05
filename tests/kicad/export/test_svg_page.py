# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The page of an SVG plot on the running ``kicad-cli`` (``H-K-EXPORT-SVG-PAGE``; capability
manufacturing-exports, "Board-area render page"; change c0409, B11). An authored board whose 50 mm by 40 mm
outline lies at negative Y, off its A4 page: the sheet plot is the A4 page, and the board-area plot
(``--exclude-drawing-sheet --page-size-mode 2``) is a page the size of the outline."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _probes import runner

from fenolite.backends.kicad.plot import VIEWS, board_page, plot_view

pytestmark = pytest.mark.needs_kicad
BOARD = """(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")
  (general (thickness 1.6) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (5 "F.SilkS" user "F.Silkscreen")
    (7 "B.SilkS" user "B.Silkscreen") (25 "Edge.Cuts" user) (33 "B.Fab" user) (35 "F.Fab" user))
  (setup (pad_to_mask_clearance 0))
  (net 0 "")
  (gr_rect (start 10 -50) (end 60 -10) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts")
    (uuid "6a1f1e2c-0000-4000-8000-000000000001"))
  (gr_text "B2" (at 30 -30 0) (layer "F.SilkS") (uuid "6a1f1e2c-0000-4000-8000-000000000002")
    (effects (font (size 2 2) (thickness 0.3))))
)
"""
SIZE = re.compile(rb'width="([0-9.]+)mm" height="([0-9.]+)mm"')


def _page(data: bytes) -> tuple[float, float]:
    found = SIZE.search(data)
    assert found is not None, "the plot names no page size"
    return float(found.group(1)), float(found.group(2))


def test_board_area_page(tmp_path: Path) -> None:
    board = tmp_path / "offpage.kicad_pcb"
    board.write_text(BOARD, encoding="utf-8")
    assert board_page(BOARD) == "board"
    sheet, message = plot_view(runner(), "front.svg", board, {}, page="sheet")
    assert sheet is not None, message
    width, height = _page(sheet)
    assert abs(width - 297) < 0.1 and abs(height - 210) < 0.1
    for name in ("front.svg", "back.svg"):
        assert VIEWS[name].kind == "svg"
        plotted, message = plot_view(runner(), name, board, {}, page="board")
        assert plotted is not None, message
        width, height = _page(plotted)
        assert abs(width - 50) < 0.5 and abs(height - 40) < 0.5, (name, width, height)
