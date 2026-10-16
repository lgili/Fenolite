# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slotted drills of footprint pads (capability altium-pcb-writer, "Slotted drills of footprint pads";
change c0170; ``docs/formats/altium/pcb-records.md``, "Pad" and "Slot pads").

A pad of one shape whose hole is a slot is written with hole shape 2, hole size the drill, slot length the
padstack's ``hole_length`` and slot rotation its ``hole_rotation``, which the model holds in the pad's own
frame (``docs/design-model.md``) and the record relative to the pad. The import reads it back in that
frame, so the slot's axis on the board is the footprint's rotation plus the pad's plus ``hole_rotation``
on both sides.
"""

from __future__ import annotations

import dataclasses
import hashlib
import math

import pytest
from _convert import read_as, two_layer

from fenolite.backends.altium import pcblib
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.frame import board_pads as altium_pads
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import PadRecord
from fenolite.backends.kicad.frame import board_pads as kicad_pads
from fenolite.backends.kicad.mod import read_footprint
from fenolite.convert import convert_project
from fenolite.core.coords import Point, Size
from fenolite.lens.altium import pad_extras
from fenolite.model.board import Pad, Padstack, PadstackLayer
from fenolite.model.design import Design

MM = 1_000_000
OVAL = """(footprint "Slot_1x3"
\t(version 20260206)
\t(generator "fenolite")
\t(layer "F.Cu")
\t(attr through_hole)
\t(pad "1" np_thru_hole oval
\t\t(at 1 2 30)
\t\t(size 3 1)
\t\t(drill oval {drill})
\t\t(layers "*.Cu" "*.Mask")
\t)
\t(pad "2" thru_hole circle (at -3 0) (size 2 2) (drill 1) (layers "*.Cu" "*.Mask"))
)
"""


def _library_pads(text: str) -> list[PadRecord]:
    defn = read_footprint(text, library="T")
    extras = pad_extras(defn)
    check = pcblib.check_footprint(defn, extras)
    assert check.refusal is None
    data = pcblib.write_pcblib([pcblib.LibFootprint(defn, extras)])
    (footprint,) = read_pcblib(data).footprints
    return [prim for prim in footprint.primitives if isinstance(prim, PadRecord)]


def test_an_oval_mounting_slot() -> None:
    """Scenario "An oval mounting slot": the footprint is not refused, and its pad is read back with hole
    shape 2, hole size 1 mm, slot length 3 mm, the pad's rotation and the slot along the pad."""
    slot, round_pad = _library_pads(OVAL.format(drill="3 1"))
    assert (slot.hole_shape, slot.hole, slot.slot_length) == (2, rec.to_units(MM), rec.to_units(3 * MM))
    assert (slot.rotation, slot.slot_rotation) == (30.0, 0.0)
    assert not slot.plated
    assert round_pad.hole_shape in (None, 0) and round_pad.hole == rec.to_units(MM)


def test_a_slot_across_its_pad() -> None:
    """A drill whose long side is Y (``drill oval 1 3``) lies across the pad: slot rotation 90°."""
    slot, _ = _library_pads(OVAL.format(drill="1 3"))
    assert (slot.hole_shape, slot.slot_length, slot.slot_rotation) == (2, rec.to_units(3 * MM), 90.0)


def test_a_slot_with_a_shape_per_layer_stays_refused() -> None:
    defn = read_footprint(OVAL.format(drill="3 1"), library="T")
    pad = defn.pads[0]
    assert pad.padstack is not None
    layers = (
        PadstackLayer("F.Cu", "oval", Size(3 * MM, MM)),
        PadstackLayer("B.Cu", "oval", Size(4 * MM, MM)),
    )
    stacked = dataclasses.replace(pad, padstack=dataclasses.replace(pad.padstack, layers=layers))
    defn = dataclasses.replace(defn, pads=(stacked, *defn.pads[1:]))
    refusal = pcblib.check_footprint(defn, pad_extras(defn)).refusal
    assert refusal == "pad '1': the drill is oval and the pad has a shape per layer"


def _slotted(turn: int) -> tuple[Design, str]:
    """The two-layer sample with pad 2 of the LED (a footprint on the bottom side, turned 30°) an oval pad
    turned 30° with a slot of 1 × 2.5 mm along it (``turn`` 0) or across it (``turn`` 90°)."""
    design = two_layer()
    board = design.board
    assert board is not None
    fp = next(f for f in board.footprints if f.lib_ref.endswith("LED_THT_3mm"))
    assert fp.side == "bottom" and fp.rotation == 30_000_000
    pad = fp.pads[1]
    stack = Padstack(id="pst_c0170-slot", hole_shape="slot", hole_length=5 * MM // 2, hole_rotation=turn)
    slotted: Pad = dataclasses.replace(
        pad, shape="oval", size=Size(3 * MM, 3 * MM), rotation=30_000_000, drill=MM, padstack=stack
    )
    footprints = tuple(
        dataclasses.replace(f, pads=(f.pads[0], slotted)) if f.id == fp.id else f for f in board.footprints
    )
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=footprints)), pad.id


def _axis(ends: tuple[Point, ...]) -> float:
    a, b = ends
    return round(math.degrees(math.atan2(b.y - a.y, b.x - a.x)) % 180.0, 3)


@pytest.mark.parametrize("turn", [0, 90_000_000])
def test_a_turned_slot_survives_a_conversion(monkeypatch: pytest.MonkeyPatch, turn: int) -> None:
    """A slot of a turned pad of a turned footprint on the bottom side is written into the document and
    the library with its slot rotation relative to the pad, is not lost, and is read back on the board
    along the axis of the source (KiCad's frame against the import's)."""
    design, pad_id = _slotted(turn)
    read_as(monkeypatch, design)
    conversion = convert_project("two_layer.kicad_pcb", to="altium")
    row = conversion.report.row("pad")
    assert row is None or pad_id not in row.ids("lost")
    data = conversion.files[conversion.read_back]
    pads = [p for p in read_pcbdoc(data).pads if isinstance(p, PadRecord)]
    slots = [(p.slot_rotation, p.slot_length) for p in pads if p.hole_shape == 2]
    assert slots == [(rec.degrees_of(turn), rec.to_units(5 * MM // 2))]
    library = next(v for k, v in conversion.files.items() if k.endswith(".PcbLib"))
    found = [p for fp in read_pcblib(library).footprints for p in fp.primitives if isinstance(p, PadRecord)]
    # the library holds the footprint as seen from its own side: the bottom pad's 30° is mirrored to 330°
    assert [(p.rotation, p.slot_rotation) for p in found if p.hole_shape == 2] == [
        (330.0, rec.degrees_of(turn))
    ]
    source = next(p for p in kicad_pads(design) if p.pad_id == pad_id)
    back = import_board(read_pcbdoc(data), file="x.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    (read,) = [p for p in altium_pads(back) if len(p.hole) == 2]
    assert _axis(source.hole) == _axis(read.hole)
