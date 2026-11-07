# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board with copper shapes for the tests of change c0412: Fenolite's own two-layer sample with a filled
polygon on ``F.Cu`` on ``VCC``, a filled rectangle on ``B.Cu`` without a net and a drawn line on ``F.Cu``
on ``GND``, authored for the tests."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]
KICAD_ROUTED = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SHAPES = """
	(gr_poly (pts (xy 40 20) (xy 46 20) (xy 46 24) (xy 43 26) (xy 40 24))
		(stroke (width 0) (type solid)) (fill yes) (layer "F.Cu") (net 2)
		(uuid "6c1e3d0a-0412-4a01-8000-000000000001"))
	(gr_rect (start 40 30) (end 44 33)
		(stroke (width 0) (type solid)) (fill yes) (layer "B.Cu")
		(uuid "6c1e3d0a-0412-4a01-8000-000000000002"))
	(gr_line (start 30 30) (end 36 30)
		(stroke (width 0.5) (type solid)) (layer "F.Cu") (net 1)
		(uuid "6c1e3d0a-0412-4a01-8000-000000000003"))
"""
TOP, BOTTOM = 1, 32


def board_with_shapes(tmp_path: Path) -> Path:
    text = KICAD_ROUTED.read_text()
    at = text.rindex(")")
    path = tmp_path / "shapes.kicad_pcb"
    path.write_text(text[:at] + SHAPES + text[at:])
    return path


def shapes_design(tmp_path: Path) -> Design:
    design = fpitems.with_graphic_nets(KicadBackend().read(board_with_shapes(tmp_path)).design)
    assert design.board is not None
    copper = [g for g in design.board.graphics if g.layer.endswith(".Cu")]
    assert len(copper) == 3
    return design
