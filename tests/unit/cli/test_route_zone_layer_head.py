# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``route`` rewrites a board whose rule area or zone holds its layers under the singular head with a
wildcard (capability kicad-file-backend, "Singular and plural layer heads of a zone", change c0145).

Before the change the write was refused: exit 7, ``field 'layers' cannot be written from the model``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run

from fenolite.backends.kicad.pcb import read_board

ROOT = Path(__file__).resolve().parents[3]
TWO_PADS = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
OUTLINE = "(polygon (pts (xy 200 200) (xy 210 200) (xy 210 210) (xy 200 210)))"
AREA = (
    '(zone (net 0) (net_name "") {layer} (uuid "00000000-0000-4000-8000-000000000145") (hatch edge 0.5)'
    " (connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)"
    " (keepout (tracks allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints allowed))"
    ' (placement (enabled no) (sheetname "")) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    + OUTLINE
    + ")"
)


def board_with_area(folder: Path, layer: str) -> Path:
    """The two-pad routing board with a rule area far from the pads, its layers written as ``layer``."""
    text = TWO_PADS.read_text(encoding="utf-8").rstrip()
    assert text.endswith(")")
    path = folder / "area.kicad_pcb"
    path.write_text(f"{text[:-1]}\t{AREA.format(layer=layer)}\n)\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("layer", ['(layer "*.Cu")', '(layer "F&B.Cu")', '(layers "*.Cu")'])
def test_route_rewrites_a_board_with_a_wildcard_rule_area(monkeypatch, tmp_path: Path, layer: str) -> None:
    """Scenario "Route rewrites the board"."""
    board = board_with_area(tmp_path, layer)
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board),
        "--router",
        "direct",
        "--out",
        "routed.kicad_pcb",
        "--confirm",
    )
    assert code == 0, (env, error)
    assert env["result"]["routed"] == ["ROUTE_ME"]
    routed = (tmp_path / "routed.kicad_pcb").read_text(encoding="utf-8")
    assert routed.count(layer) == 1
    design = read_board(routed)
    assert design.board is not None
    (area,) = design.board.keepouts
    assert area.layers == ("F.Cu", "B.Cu")
