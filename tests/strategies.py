# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hypothesis strategies shared by the model tests: lengths, angles, ids and small valid designs."""

from __future__ import annotations

import random
from dataclasses import replace

from hypothesis import strategies as st

from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model import (
    Board,
    Component,
    Design,
    FootprintInstance,
    Layer,
    Net,
    NetClass,
    Pad,
    Pin,
    PinRef,
    Track,
    Via,
)

lengths = st.integers(min_value=-(10**9), max_value=10**9)
positive_lengths = st.integers(min_value=1, max_value=10**8)
angles = st.integers(min_value=-360_000_000, max_value=360_000_000)
points = st.builds(Point, lengths, lengths)
names = st.text(alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ0123456789_", min_size=1, max_size=8)


@st.composite
def designs(draw: st.DrawFn, max_components: int = 5) -> Design:
    """A small structurally valid design (no validation errors)."""
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    rng = random.Random(seed)
    design = Design.new(draw(names), seed=seed)
    netclass = NetClass(id=new_id("cls", rng), name="default", clearance=draw(positive_lengths))
    count = draw(st.integers(min_value=1, max_value=max_components))
    components: list[Component] = []
    for index in range(count):
        pins = tuple(Pin(id=new_id("pin", rng), number=str(n + 1)) for n in range(draw(st.integers(1, 3))))
        properties = draw(st.dictionaries(names, names, max_size=2))
        components.append(
            Component(id=new_id("cmp", rng), ref=f"U{index + 1}", pins=pins, properties=properties)
        )
    all_pins = [PinRef(c.id, p.number) for c in components for p in c.pins]
    n_nets = draw(st.integers(min_value=1, max_value=max(1, len(all_pins) // 2)))
    nets = []
    for index in range(n_nets):
        members = tuple(sorted(all_pins[index::n_nets]))
        nets.append(Net(id=new_id("net", rng), name=f"N{index}", netclass_id=netclass.id, members=members))
    net_of = {m: n.id for n in nets for m in n.members}
    footprints = []
    for component in components:
        pads = tuple(
            Pad(
                id=new_id("pad", rng),
                number=pin.number,
                shape="rect",
                size=Size(500_000, 600_000),
                position=Point(int(pin.number) * 1_000_000, 0),
                layers=("F.Cu",),
                net_id=net_of.get(PinRef(component.id, pin.number)),
            )
            for pin in component.pins
        )
        footprints.append(
            FootprintInstance(
                id=new_id("fp", rng),
                component_id=component.id,
                lib_ref="Lib:FP",
                position=draw(points),
                rotation=draw(angles),
                pads=pads,
            )
        )
    tracks = tuple(
        Track(
            id=new_id("trk", rng),
            start=draw(points),
            end=draw(points),
            width=draw(positive_lengths),
            layer=draw(st.sampled_from(["F.Cu", "B.Cu"])),
            net_id=draw(st.sampled_from([n.id for n in nets])),
        )
        for _ in range(draw(st.integers(0, 4)))
    )
    vias = tuple(
        Via(
            id=new_id("via", rng),
            position=draw(points),
            diameter=600_000,
            drill=300_000,
            layers=("F.Cu", "B.Cu"),
        )
        for _ in range(draw(st.integers(0, 2)))
    )
    layers = (
        Layer(id=new_id("lay", rng), name="F.Cu", kind="copper", ordinal=0),
        Layer(id=new_id("lay", rng), name="B.Cu", kind="copper", ordinal=31),
    )
    board = design.board or Board(id=new_id("brd", rng))
    board = replace(board, layers=layers, footprints=tuple(footprints), tracks=tracks, vias=vias)
    circuit = replace(design.circuit, components=tuple(components), nets=tuple(nets), netclasses=(netclass,))
    return replace(design, circuit=circuit, board=board)
