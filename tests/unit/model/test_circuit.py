# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import random

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model import Component, ExtBag, Net, Pin, PinRef, Track


def test_entities_are_immutable() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="R1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        component.ref = "R2"  # type: ignore[misc]


def test_header_defaults() -> None:
    pin = Pin(id=new_id("pin", random.Random(1)), number="1")
    assert (pin.native_ids, pin.provenance, pin.ext, pin.etype) == ({}, None, {}, "passive")


def test_extension_bag_survives_replace() -> None:
    bag = ExtBag(min_version="20241229", payload=(("locked", "yes"),))
    track = Track(
        id=new_id("trk", random.Random(2)),
        start=Point(0, 0),
        end=Point(1, 0),
        width=250_000,
        layer="F.Cu",
        ext={"kicad": bag},
    )
    wider = dataclasses.replace(track, width=300_000)
    assert wider.ext == {"kicad": bag} and wider.width == 300_000 and wider.id == track.id


def test_net_members_are_pin_refs() -> None:
    net = Net(
        id=new_id("net", random.Random(3)), name="GND", members=(PinRef("cmp_x", "2"), PinRef("cmp_y", "1"))
    )
    assert sorted(net.members)[0] == PinRef("cmp_x", "2")
