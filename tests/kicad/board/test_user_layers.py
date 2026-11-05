# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 9/10 user-layer rows (c0161 task 1.2)."""

from __future__ import annotations

import pytest
from _probes import run, runner
from _userlayers import board

pytestmark = pytest.mark.needs_kicad


def test_user_layers() -> None:
    assert run("pcb-user-layers") == "equal"


def test_undeclared_layer_is_refused() -> None:
    result = runner().run(
        ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", "probe.kicad_pcb"],
        files={"probe.kicad_pcb": board(undeclared=True)},
    )
    assert not result.ok


CUTOUT_ROWS: dict[str, str] = {
    "altium-third-party-pcbdoc-03": (
        "the region with ISBOARDCUTOUT=TRUE on the Keep-Out layer is read as an Edge.Cuts cut-out since "
        "change c0168. Its layer table cut to two copper layers loaded in KiCad until change c0409 wrote the "
        "footprints' own graphics, some of them on Mech.1, Mech.13 and Mech.15"
    ),
}
"""Row id → why its board holds an Edge.Cuts cut-out and no graphic on the Altium Keep-Out layer."""


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row_id", [f"altium-third-party-pcbdoc-{i:02d}" for i in range(1, 7)])
def test_negative_public_probe(row_id: str) -> None:
    import dataclasses

    from _corpus import manifest_items, require

    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.kicad.layers import created_layers
    from fenolite.backends.kicad.pcb import _Writer
    from fenolite.backends.kicad.sexpr import dumps

    item = next(i for i in manifest_items("rta") if i.id == row_id)
    design = AltiumBackend().read(require(item)).design
    assert design.board is not None
    # Deliberate negative fixture: bypass the public guard; no production caller can write this.
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, layers=created_layers(2)))
    text = dumps(_Writer(design, runner().major()).root()).encode()
    result = runner().run(
        ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", "probe.kicad_pcb"],
        files={"probe.kicad_pcb": text},
    )
    if row_id in CUTOUT_ROWS:
        graphics = design.board.graphics
        assert not [g for g in graphics if g.layer == "Altium.KeepOut"], row_id
        cutouts = [g for g in graphics if g.kind == "polygon" and g.layer == "Edge.Cuts" and not g.filled]
        assert cutouts, row_id
    assert not result.ok, row_id
