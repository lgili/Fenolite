# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slotted board holes as free slot pads (capability altium-pcb-writer, "Non-plated holes and slots";
change c0168; ``docs/formats/altium/pcb-records.md``, "Slot pads")."""

from __future__ import annotations

import pytest

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Hole

MM = 1_000_000
OUTLINE = (Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM))


def _hole(name: str, drill: int, length: int | None = None, rotation: int = 0) -> Hole:
    return Hole(
        id=derived_id("hol", "test", name),
        position=Point(20 * MM, 20 * MM),
        drill=drill,
        length=length,
        rotation=rotation,
    )


def _pads(*holes: Hole) -> list[PadRecord]:
    doc = read_pcbdoc(write_pcbdoc(PcbDocSpec(outline=OUTLINE, holes=holes), filename="s.PcbDoc"))
    pads = [pad for pad in doc.pads if isinstance(pad, PadRecord)]
    assert len(pads) == len(doc.pads)
    return pads


def test_a_turned_slot() -> None:
    """Drill 2 mm, length 12 mm, rotation 30°: a free pad on Multi-Layer with hole shape 2, hole size 2 mm,
    slot length 12 mm and rotation 30°, without name, net or component, its copper equal to its hole."""
    (pad,) = _pads(_hole("H1", 2 * MM, 12 * MM, 30_000_000))
    assert pad.name == "" and pad.prefix.layer == rec.MULTI_LAYER
    assert pad.prefix.net is None and pad.prefix.component is None
    assert pad.hole == rec.to_units(2 * MM) and not pad.plated
    assert pad.hole_shape == rec.HOLE_SHAPE_SLOT
    assert pad.slot_length == rec.to_units(12 * MM) and pad.slot_rotation == 0.0
    assert pad.rotation == pytest.approx(30.0, abs=1e-9)
    size = (rec.to_units(12 * MM), rec.to_units(2 * MM))
    assert pad.size_top == pad.size_mid == pad.size_bottom == size
    assert pad.shape_top == pad.shape_mid == pad.shape_bottom == 1
    assert pad.inner_sizes is not None and set(pad.inner_sizes) == {size}


def test_a_round_hole_keeps_the_record_of_c0085() -> None:
    record = rec.hole_record(100, 200, 3000)
    assert rec.hole_record(100, 200, 3000, rotation=45_000_000) == record
    (pad,) = _pads(_hole("H1", 3_200_000))
    assert pad.hole_shape is None and pad.slot_length is None and pad.rotation == 0.0


def test_a_negative_angle_is_written_in_one_turn() -> None:
    (pad,) = _pads(_hole("H1", 2 * MM, 6 * MM, -90_000_000))
    assert pad.rotation == pytest.approx(270.0)


@pytest.mark.parametrize(("drill", "length"), [(0, 10), (2000, 2000), (2000, 1000)])
def test_a_slot_record_needs_a_drill_and_a_longer_length(drill: int, length: int) -> None:
    with pytest.raises(ValueError):
        rec.hole_record(0, 0, drill, length=length)
