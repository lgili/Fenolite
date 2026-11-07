# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's hole clearance test tolerates the DRC epsilon (change c0420, N4; ``docs/formats/kicad/copper.md``,
``H-K-COPPER-EPSILON``).

An authored board: a 1 mm unplated hole and a 0.25 mm track of another net, on a project whose minimum hole
clearance is 0.25 mm. A gap 400 nm below the minimum gives no ``hole_clearance``, one 600 nm below gives
one, as ``copper.hole-clearance`` judges the gap less ``clearance_tolerance`` (500 nm)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def _board(folder: Path, gap: float) -> Path:
    y = round(10 + 0.5 + 0.125 + gap, 6)
    uuid = "c0420000-0000-4000-8000-0000000000{:02d}".format
    board = folder / "hole.kicad_pcb"
    board.write_text(
        f"""(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")
  (general (thickness 1.6) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (setup (pad_to_mask_clearance 0))
  (net 0 "") (net 1 "B")
  (gr_rect (start 0 0) (end 20 20) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts")
    (uuid "{uuid(11)}"))
  (footprint "Hole" (layer "F.Cu") (uuid "{uuid(12)}") (at 10 10)
    (property "Reference" "H1" (at 0 -2 0) (layer "F.SilkS") (uuid "{uuid(13)}")
      (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "Hole" (at 0 2 0) (layer "F.Fab") (uuid "{uuid(14)}")
      (effects (font (size 1 1) (thickness 0.15))))
    (attr board_only exclude_from_pos_files exclude_from_bom)
    (pad "" np_thru_hole circle (at 0 0) (size 1 1) (drill 1) (layers "*.Cu" "*.Mask") (uuid "{uuid(15)}")))
  (segment (start 5 {y}) (end 15 {y}) (width 0.25) (layer "F.Cu") (net 1) (uuid "{uuid(16)}"))
)
""",
        encoding="utf-8",
    )
    classes = [{"name": "Default", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.6,
                "via_drill": 0.3, "priority": 2147483647}]  # fmt: skip
    pro = {"meta": {"filename": "hole.kicad_pro", "version": 3},
           "board": {"design_settings": {"rules": {"min_hole_clearance": 0.25, "min_clearance": 0.0}}},
           "net_settings": {"classes": classes, "meta": {"version": 4}}}  # fmt: skip
    (folder / "hole.kicad_pro").write_text(json.dumps(pro), encoding="utf-8")
    return board


@pytest.mark.parametrize(("gap", "reported"), [(0.2496, 0), (0.2494, 1)])
def test_hole_clearance_tolerates_the_epsilon(tmp_path: Path, gap: float, reported: int) -> None:
    board = _board(tmp_path, gap)
    run = runner().drc(board, files={"hole.kicad_pro": tmp_path / "hole.kicad_pro"})
    assert run.report is not None, run.run.stderr
    assert [v.type for v in run.report.violations].count("hole_clearance") == reported
