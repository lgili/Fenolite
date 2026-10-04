# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small authored routing designs shared by selection and merge tests."""

from __future__ import annotations

import dataclasses
import random

from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model.base import ExtBag
from fenolite.model.board import FootprintInstance, Layer, Pad, Track, Zone
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design


def routing_design() -> Design:
    rng = random.Random(160016)
    design = Design.new("routing-unit", seed=160016)
    nets = {name: Net(id=new_id("net", rng), name=name) for name in ("A", "B", "GND", "NC")}
    pads: list[Pad] = []
    for name, count in (("A", 2), ("B", 2), ("GND", 3), ("NC", 1)):
        for index in range(count):
            pads.append(
                Pad(
                    id=new_id("pad", rng),
                    number=f"{name}{index + 1}",
                    shape="circle",
                    size=Size(600_000, 600_000),
                    position=Point(index * 1_000_000, 0),
                    layers=("F.Cu", "B.Cu"),
                    net_id=nets[name].id,
                )
            )
    component_id = new_id("cmp", rng)
    pins = tuple(Pin(id=new_id("pin", rng), number=pad.number) for pad in pads)
    component = Component(id=component_id, ref="J1", pins=pins)
    members: dict[str, list[PinRef]] = {name: [] for name in nets}
    for pad in pads:
        net_name = next(name for name, net in nets.items() if net.id == pad.net_id)
        members[net_name].append(PinRef(component_id, pad.number))
    nets = {name: dataclasses.replace(net, members=tuple(members[name])) for name, net in nets.items()}
    footprint = FootprintInstance(
        id=new_id("fp", rng),
        component_id=component_id,
        lib_ref="Test:Four",
        position=Point(0, 0),
        pads=tuple(pads),
    )
    track = Track(
        id=new_id("trk", rng),
        start=Point(0, 0),
        end=Point(1_000_000, 0),
        width=250_000,
        layer="F.Cu",
        net_id=nets["B"].id,
    )
    zone = Zone(id=new_id("zon", rng), outline=(), layers=("F.Cu",), net_id=nets["GND"].id)
    board = dataclasses.replace(
        design.board,
        layers=(
            Layer(
                id=new_id("lay", rng),
                name="F.Cu",
                kind="copper",
                ordinal=0,
                ext={"kicad": ExtBag(payload=(("number", "0"), ("type", "signal")))},
            ),
            Layer(
                id=new_id("lay", rng),
                name="B.Cu",
                kind="copper",
                ordinal=31,
                ext={"kicad": ExtBag(payload=(("number", "31"), ("type", "signal")))},
            ),
        ),
        footprints=(footprint,),
        tracks=(track,),
        zones=(zone,),
    )
    return dataclasses.replace(
        design, circuit=Circuit(components=(component,), nets=tuple(nets.values())), board=board
    )
