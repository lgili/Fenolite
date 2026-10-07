# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tenting flags of a written via against ``kicad-cli pcb import`` (capability altium-pcb-writer, "Via
tenting flags"; altium-import, "Via tenting of imported vias"; change c0112).

A PCB document with four through vias, one per value of the two tenting flags (``0C``, ``2C``, ``4C``,
``6C``), is imported with ``kicad-cli pcb import --format altium`` (10.0 only), run as a subprocess, and
the board KiCad writes is read with ``read_board``. KiCad's importer was neither read nor transcribed.

A pass says what KiCad's importer reads from the two bits, and that Fenolite's import of the same document
gives the same tenting. It settles no Altium row: ``H-A-PCB-CU-VIATENT`` waits for the author report.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
from _altium_board6 import at, bare_spec
from _probes import runner

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.pcbdoc import write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.board import Via, ViaProtection

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]

CASES = ((False, False), (True, False), (False, True), (True, True))


def document() -> bytes:
    vias = tuple(
        Via(
            id=f"via_{k}",
            position=at(10 + 2 * k, 10),
            diameter=600_000,
            drill=300_000,
            layers=("F.Cu", "B.Cu"),
            protection=ViaProtection(tenting_front=top, tenting_back=bottom),
        )
        for k, (top, bottom) in enumerate(CASES)
    )
    return write_pcbdoc(bare_spec(copper_layers=("F.Cu", "B.Cu"), vias=vias), filename="tented.PcbDoc")


def test_kicad_reads_the_two_bits_as_front_and_back_tenting() -> None:
    data = document()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tented.PcbDoc"
        path.write_bytes(data)
        imported = runner().import_board(path)
    assert imported.board is not None, imported.run.stderr
    design = read_board(imported.board.decode("utf-8"))
    assert design.board is not None
    kicad = sorted(design.board.vias, key=lambda v: v.position.x)
    found = [(v.protection.tenting_front, v.protection.tenting_back) for v in kicad]
    assert found == list(CASES)  # explicit on every via: none follows KiCad's board default
    ours = import_board(
        read_pcbdoc(data, file="tented.PcbDoc"),
        file="tented.PcbDoc",
        sha256=hashlib.sha256(data).hexdigest(),
    )
    assert ours.board is not None
    own = sorted(ours.board.vias, key=lambda v: v.position.x)
    assert [(v.protection.tenting_front, v.protection.tenting_back) for v in own] == found
