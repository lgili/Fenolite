# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import random

from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.core.units import parse_angle
from fenolite.model import Board, FootprintInstance, Pad, Padstack, PadstackLayer, StackLayer, Stackup, Zone


def test_ninety_degrees_is_exact() -> None:
    rng = random.Random(1)
    fp = FootprintInstance(
        id=new_id("fp", rng),
        component_id="",
        lib_ref="L:F",
        position=Point(0, 0),
        rotation=parse_angle("90deg"),
    )
    assert fp.rotation == 90_000_000


def test_board_structure() -> None:
    rng = random.Random(2)
    stack = Stackup(
        id=new_id("stk", rng),
        layers=(
            StackLayer(id=new_id("sly", rng), name="F.Cu", kind="copper", thickness=35_000),
            StackLayer(
                id=new_id("sly", rng), name="core", kind="dielectric", thickness=1_510_000, epsilon_r="4.5"
            ),
            StackLayer(id=new_id("sly", rng), name="B.Cu", kind="copper", thickness=35_000),
        ),
    )
    pad = Pad(
        id=new_id("pad", rng),
        number="1",
        shape="roundrect",
        size=Size(900_000, 950_000),
        position=Point(-800_000, 0),
        layers=("F.Cu", "F.Paste", "F.Mask"),
        padstack=Padstack(
            id=new_id("pst", rng), layers=(PadstackLayer("F.Cu", "rect", Size(900_000, 950_000)),)
        ),
    )
    zone = Zone(id=new_id("zon", rng), outline=(Point(0, 0), Point(10, 0), Point(10, 10)), layers=("F.Cu",))
    board = Board(id=new_id("brd", rng), stackup=stack, zones=(zone,))
    assert sum(layer.thickness for layer in stack.layers) == 1_580_000
    assert pad.padstack is not None and board.zones[0].fills == ()
