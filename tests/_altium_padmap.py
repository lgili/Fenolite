# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared by the tests of ``pad_map`` in an Altium build (change c0135): the blink's LED with its pins on
the other pads, and the nets of the pads of a written PCB document."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.read.pcb import read_pcbdoc

D1 = 'd1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")'
SWAPPED = D1.replace(")", ', pad_map={"1": "2", "2": "1"})')
"""The blink's LED with its pins on the other pads: pin 1 (on ``GND``) on pad 2."""


def pad_nets(folder: Path) -> dict[tuple[str, str], str]:
    """(reference, pad number) → the name of the pad's net in the written PCB document, ``""`` for none."""
    (file,) = folder.glob("*.PcbDoc")
    document = read_pcbdoc(file.read_bytes(), file=file.name)
    parts = read_board(document, file=file.name, sha256="0" * 64, ids=Ids("altium_pcbdoc", EVIDENCE))
    refs = {component.id: component.ref for component in parts.components}
    names = {net.id: net.name for net in parts.nets}
    return {
        (refs[footprint.component_id], pad.number): names.get(pad.net_id or "", "")
        for footprint in parts.board.footprints
        for pad in footprint.pads
    }


__all__ = ["D1", "SWAPPED", "pad_nets"]
