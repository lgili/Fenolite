# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User layers named after an Altium mechanical layer (capability altium-pcb-writer, "Mechanical layers of
KiCad drawings", scenario "User layer named after a mechanical layer"; change c0412). The board is
Fenolite's own two-layer sample with three user layers and one drawn line on each, authored for the test;
no tool runs."""

from __future__ import annotations

from pathlib import Path

from _coppershapes import KICAD_ROUTED

from fenolite.backends.altium import lower
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TrackRecord
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.model.design import Design

USER_LAYERS = """\t\t(43 "User.3" user "Mechanical 5")
\t\t(59 "User.11" user "Mech.13")
\t\t(61 "User.12" user)
"""
LINES = "".join(
    f"""
\t(gr_line (start {x} 40) (end {x + 4} 40)
\t\t(stroke (width 0.2) (type solid)) (layer "{layer}")
\t\t(uuid "6c1e3d0a-0412-4b01-8000-00000000000{n}"))"""
    for n, (x, layer) in enumerate(((20, "User.3"), (30, "User.11"), (40, "User.12"), (50, "F.Fab")), 1)
)


def _design(tmp_path: Path) -> Design:
    text = KICAD_ROUTED.read_text()
    at = text.index('\t\t(33 "B.Fab" user)\n') + len('\t\t(33 "B.Fab" user)\n')
    text = text[:at] + USER_LAYERS + text[at:]
    end = text.rindex(")")
    path = tmp_path / "mech.kicad_pcb"
    path.write_text(text[:end] + LINES + "\n" + text[end:])
    return KicadBackend().read(path).design


def test_named_user_layers_land_on_their_mechanical_layers(tmp_path: Path) -> None:
    design = _design(tmp_path)
    assert design.board is not None
    mapped = lower.kicad_mechanical(design.board)
    assert mapped["User.3"] == 56 + 5 and mapped["User.11"] == 56 + 13
    assert "User.12" not in mapped and mapped["F.Fab"] == 56 + 13
    assert mapped["User.1"] == 57, "an unnamed layer keeps the fixed map"


def test_written_document_holds_the_named_layers(tmp_path: Path) -> None:
    design = _design(tmp_path)
    written = lower.write_design(design)
    lost = [i.message for i in written.issues if i.where == "graphic"]
    assert len(lost) == 1 and "the layer User.12 has no layer in the document" in lost[0]
    document = read_pcbdoc(written.files["mech.PcbDoc"], file="mech.PcbDoc")
    layers = [t.prefix.layer for t in document.tracks if isinstance(t, TrackRecord) and t.prefix.layer > 56]
    # User.3 on Mechanical 5; Mechanical 13 holds User.11's line beside the sample's F.Fab outline (four
    # edges) and the added F.Fab line
    assert layers.count(56 + 5) == 1 and layers.count(56 + 13) == 6 and set(layers) == {61, 69}
