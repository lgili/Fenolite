# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored board of five two-pad nets for the tests of router runs and route records (change c0120).

The nets ``N1`` to ``N5`` each join two round pads 10 mm apart, one row per net, 2 mm between the rows;
the board holds no copper. All values are round and invented for Fenolite."""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model.base import ExtBag
from fenolite.model.board import FootprintInstance, Layer, Pad
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.routing.protocol import JobNet, JobPad

MM = 1_000_000
NETS = ("N1", "N2", "N3", "N4", "N5")
SPAN = 10 * MM
PITCH = 2 * MM


def five_nets() -> Design:
    rng = random.Random(120120)
    design = Design.new("five-nets", seed=120120)
    nets = {name: Net(id=new_id("net", rng), name=name) for name in NETS}
    pads: list[Pad] = []
    for row, name in enumerate(NETS):
        for column in range(2):
            pads.append(
                Pad(
                    id=new_id("pad", rng),
                    number=f"{name}{'AB'[column]}",
                    shape="circle",
                    size=Size(600_000, 600_000),
                    position=Point(column * SPAN, row * PITCH),
                    layers=("F.Cu", "B.Cu"),
                    net_id=nets[name].id,
                )
            )
    component_id = new_id("cmp", rng)
    component = Component(
        id=component_id, ref="J1", pins=tuple(Pin(id=new_id("pin", rng), number=pad.number) for pad in pads)
    )
    members: dict[str, list[PinRef]] = {name: [] for name in nets}
    for pad in pads:
        members[pad.number[:2]].append(PinRef(component_id, pad.number))
    nets = {name: dataclasses.replace(net, members=tuple(members[name])) for name, net in nets.items()}
    footprint = FootprintInstance(
        id=new_id("fp", rng),
        component_id=component_id,
        lib_ref="Test:Ten",
        position=Point(0, 0),
        pads=tuple(pads),
    )
    assert design.board is not None
    layers = tuple(
        Layer(
            id=new_id("lay", rng),
            name=name,
            kind="copper",
            ordinal=ordinal,
            ext={"kicad": ExtBag(payload=(("number", str(ordinal)), ("type", "signal")))},
        )
        for name, ordinal in (("F.Cu", 0), ("B.Cu", 31))
    )
    board = dataclasses.replace(design.board, layers=layers, footprints=(footprint,))
    return dataclasses.replace(
        design, circuit=Circuit(components=(component,), nets=tuple(nets.values())), board=board
    )


def job_nets(design: Design, names: tuple[str, ...] = NETS) -> tuple[JobNet, ...]:
    """The routing requests of ``names``, with round class values."""
    found: list[JobNet] = []
    for name in names:
        net = next(item for item in design.circuit.nets if item.name == name)
        pads = tuple(
            JobPad("J1", pad.number, name, pad.position, pad.layers, pad.drill) for pad in design.by_net[name]
        )
        found.append(JobNet(name, net.id, pads, 250_000, 200_000, 600_000, 300_000))
    return tuple(found)


def write_five_nets(folder: Path, name: str = "five.kicad_pcb") -> Path:
    """The board written as a KiCad 10 file in ``folder``."""
    path = folder / name
    path.write_text(write_board(five_nets(), target=10).text, encoding="utf-8", newline="\n")
    return path


__all__ = ["MM", "NETS", "PITCH", "SPAN", "five_nets", "job_nets", "write_five_nets"]
