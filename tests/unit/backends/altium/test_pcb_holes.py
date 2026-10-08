# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Holes of the board in the Altium PCB document (capability altium-pcb-writer, "Non-plated holes and
slots"; change c0085). The model's ``Hole`` is round: it has no slot, so none is written."""

from __future__ import annotations

import dataclasses

import pytest
from _altium import blink_pcbdoc_spec
from _altium_board6 import at, bare_spec, imported_point, near, read_back

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.model.board import Hole

MOUNT = Hole(id="hol_mount", position=at(4, 25), drill=3_200_000)


def test_mounting_hole() -> None:
    """Scenario "Mounting hole": a free pad with a 3.2 mm hole, plating off and no copper."""
    document, design = read_back(bare_spec(holes=(MOUNT,)))
    (pad,) = document.pads
    assert (pad.prefix.component, pad.prefix.net, pad.prefix.layer) == (None, None, pcbrecords.MULTI_LAYER)
    assert pad.name == "" and not pad.plated and pad.shape_top == 1
    assert abs(pcbrecords.to_units(3_200_000) - pad.hole) == 0
    assert pad.size_top == pad.size_mid == pad.size_bottom == (pad.hole, pad.hole)  # no copper ring
    assert pad.hole_shape is None  # no slot fields: the sixth subrecord is empty
    assert design.board is not None
    (footprint,) = design.board.footprints
    assert footprint.attributes == ("board_only",)
    (read,) = footprint.pads
    assert read.kind == "np_thru_hole" and read.drill is not None and abs(read.drill - MOUNT.drill) <= 2
    assert near(footprint.position, imported_point(MOUNT.position))
    assert dict(document.pad_unique_ids) and len(document.pad_unique_ids) == 1


def test_a_plated_hole_sets_the_plated_byte() -> None:
    plated = dataclasses.replace(MOUNT, id="hol_plated", drill=1_000_000, plated=True)
    document, design = read_back(bare_spec(holes=(MOUNT, plated)))
    assert sorted((p.plated, p.hole) for p in document.pads) == [
        (False, pcbrecords.to_units(3_200_000)),
        (True, pcbrecords.to_units(1_000_000)),
    ]
    assert design.board is not None
    assert sorted(pad.kind for fp in design.board.footprints for pad in fp.pads) == [
        "np_thru_hole",
        "thru_hole",
    ]


def test_holes_follow_the_component_pads() -> None:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    plain, _ = read_back(spec, "blink.PcbDoc")
    hole = dataclasses.replace(MOUNT, position=spec.outline[0])
    more, _ = read_back(dataclasses.replace(spec, holes=(hole,)), "blink.PcbDoc")
    assert [p.raw for p in more.pads[:-1]] == [p.raw for p in plain.pads]
    assert more.pads[-1].prefix.component is None and len(more.pad_unique_ids) == len(plain.pads) + 1


def test_a_hole_without_a_drill_is_refused() -> None:
    with pytest.raises(ValueError, match="hol_mount: a hole needs a positive drill"):
        write_pcbdoc(bare_spec(holes=(dataclasses.replace(MOUNT, drill=0),)))
    with pytest.raises(ValueError, match="positive drill"):
        pcbrecords.hole_record(0, 0, 0)
