# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper shapes of a converted KiCad board against ``kicad-cli pcb import`` (capability altium-pcb-writer,
"Board graphics and keep-out records", scenario "Copper polygon with a net"; change c0412; hypothesis
``H-A-PCBX-KICAD``). ``pcb import`` exists from 10.0 only (S-0166). A pass checks what KiCad's importer
reads; it settles no Altium row."""

from __future__ import annotations

from pathlib import Path

import pytest
from _coppershapes import shapes_design
from _pcbxcases import import_document
from _resources import kicad_cli_major

from fenolite.backends.kicad import fpitems
from fenolite.lens.altium import write_model

pytestmark = pytest.mark.needs_kicad


def test_kicad_imports_copper_shapes_on_their_layers_and_nets(tmp_path: Path) -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    written = write_model(shapes_design(tmp_path))
    found = import_document(written.files["shapes.PcbDoc"], "shapes.PcbDoc")
    assert found.code == 0, found.output
    design = fpitems.with_graphic_nets(found.board)
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    copper = sorted(
        (g.layer, g.kind, len(g.points), names.get(g.net_id or "", ""))
        for g in design.board.graphics
        if g.layer.endswith(".Cu") and g.filled
    )
    assert ("F.Cu", "polygon", 5, "VCC") in copper and ("B.Cu", "polygon", 4, "") in copper
    gnd = [t for t in design.board.tracks if t.layer == "F.Cu" and names.get(t.net_id or "") == "GND"]
    assert [t.width for t in gnd if t.width == 500_000] == [500_000]
