# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Turned circular-pad slots retain their absolute axis (c0161 task 2.4)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad._fpmap import aligned_slot_pad
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad, Padstack


def pad(shape: str) -> Pad:
    return Pad(
        id="pad-slot",
        number="1",
        shape=shape,
        size=Size(2000000, 2000000),
        position=Point(0, 0),
        rotation=30000000,
        drill=1000000,
        kind="thru_hole",
        layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"),
        padstack=Padstack(id="pst-slot", hole_shape="slot", hole_length=3000000, hole_rotation=45000000),
    )


def test_round_pad_slot() -> None:
    actual = aligned_slot_pad(pad("circle"))
    assert actual.rotation == 75000000 and actual.padstack.hole_rotation == 0


def test_rectangular_pad_slot_is_refused() -> None:
    with pytest.raises(ValueError, match="slot rotation"):
        aligned_slot_pad(pad("rect"))


def test_round_slot_library_readback() -> None:
    from fenolite.backends.kicad.mod import read_footprint, write_footprint
    from fenolite.model.library import FootprintDef

    source = pad("circle")
    definition = FootprintDef(id="fpd-slot", name="slot", pads=(source,))
    actual = read_footprint(write_footprint(definition)).pads[0]
    assert actual.size == source.size and actual.drill == source.drill
    assert actual.padstack is not None and source.padstack is not None
    assert (actual.rotation + actual.padstack.hole_rotation) % 180000000 == (
        source.rotation + source.padstack.hole_rotation
    ) % 180000000
