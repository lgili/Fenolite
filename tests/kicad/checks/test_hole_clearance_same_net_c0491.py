# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's DRC judges the hole clearance between an unplated pad and copper of the pad's own net (change
c0491, ``H-G-HOLE-SAME-NET``; ``docs/formats/kicad/rules.md``).

An authored board: a 3 mm unplated pad of net ``GND``, a via and a track 0.1 mm from its wall, under a
board hole clearance of 0.25 mm. Measured on KiCad 10.0.6: with the via and the track of ``GND`` there are
three ``hole_clearance`` (the via twice, once per layer, and the track), exactly as with both of ``N1`` (the
control). KiCad names the pad "NPTH pad" without a net, so the KiCad rules view keeps judging an unplated
pad's own net (``DesignRules.hole_clearance_same_net``) and only Altium documents leave it out."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def _board(folder: Path, copper_net: int) -> Path:
    uuid = "c0491000-0000-4000-8000-0000000000{:02d}".format
    board = folder / "hole.kicad_pcb"
    board.write_text(
        f"""(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")
  (general (thickness 1.6) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (setup (pad_to_mask_clearance 0))
  (net 0 "") (net 1 "GND") (net 2 "N1")
  (gr_rect (start 0 0) (end 20 20) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts")
    (uuid "{uuid(11)}"))
  (footprint "Hole" (layer "F.Cu") (uuid "{uuid(12)}") (at 10 10)
    (property "Reference" "H1" (at 0 -3 0) (layer "F.SilkS") (uuid "{uuid(13)}")
      (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "Hole" (at 0 3 0) (layer "F.Fab") (uuid "{uuid(14)}")
      (effects (font (size 1 1) (thickness 0.15))))
    (attr board_only exclude_from_pos_files exclude_from_bom)
    (pad "1" np_thru_hole circle (at 0 0) (size 3 3) (drill 3) (layers "*.Cu" "*.Mask") (net 1 "GND")
      (uuid "{uuid(15)}")))
  (via (at 8.1 10) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {copper_net}) (uuid "{uuid(16)}"))
  (segment (start 5 11.7) (end 15 11.7) (width 0.2) (layer "F.Cu") (net {copper_net}) (uuid "{uuid(17)}"))
)
""",
        encoding="utf-8",
    )
    classes = [{"name": "Default", "clearance": 0.1, "track_width": 0.2, "via_diameter": 0.6,
                "via_drill": 0.3, "priority": 2147483647}]  # fmt: skip
    pro = {"meta": {"filename": "hole.kicad_pro", "version": 3},
           "board": {"design_settings": {"rules": {"min_hole_clearance": 0.25, "min_clearance": 0.0}}},
           "net_settings": {"classes": classes, "meta": {"version": 4}}}  # fmt: skip
    (folder / "hole.kicad_pro").write_text(json.dumps(pro), encoding="utf-8")
    return board


@pytest.mark.parametrize(("copper_net", "reported"), [(1, 3), (2, 3)])
def test_kicad_judges_the_pads_own_net(tmp_path: Path, copper_net: int, reported: int) -> None:
    board = _board(tmp_path, copper_net)
    run = runner().drc(board, files={"hole.kicad_pro": tmp_path / "hole.kicad_pro"})
    assert run.report is not None, run.run.stderr
    assert [v.type for v in run.report.violations].count("hole_clearance") == reported
