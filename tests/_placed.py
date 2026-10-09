# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small designs of placed mini and frame-bench footprints, for the board-frame and copper tests (change
c0028). Every design is built through the model API: no file is written and no tool runs."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from fenolite.backends.kicad.embed import PATH_PROPERTY, place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Side
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

LIBS = Path(__file__).resolve().parent / "data" / "libs"
MM = 1_000_000
DEG = 1_000_000


def mm(value: float) -> int:
    return round(value * MM)


def pt(x: float, y: float) -> Point:
    return Point(mm(x), mm(y))


@cache
def definition(name: str, library: str = "Mini", target: int = 10) -> FootprintDef:
    """A footprint of ``tests/data/libs/<library>.pretty``, or of ``<library>_v9.pretty`` for a board of
    ``target`` 9: the files of ``Mini.pretty`` are in the 10.0 form and hold a key that KiCad 9 does not
    know (``duplicate_pad_numbers_are_jumpers``), so the 9.0 writer would refuse them as lossy."""
    folder = library if target >= 10 else f"{library}_v9"
    return read_footprint(LIBS / f"{folder}.pretty" / f"{name}.kicad_mod", library=library)


@dataclass(frozen=True)
class Part:
    """A footprint to place: where, how, and the net name of each pad number that has one."""

    ref: str
    name: str
    x: float
    y: float
    rot: float = 0
    side: Side = "top"
    nets: Mapping[str, str] = field(default_factory=lambda: {})
    library: str = "Mini"
    path: str = ""


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def design_of(
    *parts: Part,
    copper: int = 2,
    classes: Sequence[NetClass] = (),
    class_of: Mapping[str, str] | None = None,
    extra_nets: Sequence[str] = (),
    target: int = 10,
) -> Design:
    """A created board holding ``parts``; nets are made for every net name the parts or ``extra_nets`` use,
    and ``class_of`` maps a net name to the name of its class. ``target`` picks the footprint files of
    that KiCad major (see ``definition``)."""
    layers = created_layers(copper)
    copper_names = tuple(la.name for la in layers if la.kind == "copper")
    names = list(dict.fromkeys([n for p in parts for n in p.nets.values()] + list(extra_nets)))
    nets = {name: _id("net", i) for i, name in enumerate(names, start=1)}
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    members: dict[str, list[PinRef]] = {name: [] for name in names}
    for n, part in enumerate(parts, start=1):
        defn = definition(part.name, part.library, target)
        properties = {PATH_PROPERTY: part.path} if part.path else {}
        component = Component(
            id=_id("cmp", n), ref=part.ref, lib_footprint_ref=defn.lib_id, properties=properties
        )
        placed = place_footprint(
            defn,
            component=component,
            at=pt(part.x, part.y),
            rotation=round(part.rot * DEG),
            side=part.side,
            key=part.path or part.ref,
            copper=copper_names,
        )
        pads = tuple(
            dataclasses.replace(pad, net_id=nets[part.nets[pad.number]]) if pad.number in part.nets else pad
            for pad in placed.pads
        )
        for number, name in part.nets.items():
            members[name].append(PinRef(component.id, number))
        components.append(component)
        footprints.append(dataclasses.replace(placed, pads=pads))
    class_ids = {c.name: c.id for c in classes}
    circuit = Circuit(
        components=tuple(components),
        nets=tuple(
            Net(
                id=nets[name],
                name=name,
                netclass_id=class_ids.get((class_of or {}).get(name, "")),
                members=tuple(sorted(members[name])),
            )
            for name in names
        ),
        netclasses=tuple(classes),
    )
    board = Board(id=_id("brd", 1), layers=layers, footprints=tuple(footprints))
    return dataclasses.replace(Design.new("frame", seed=0), circuit=circuit, board=board)


__all__ = ["DEG", "LIBS", "MM", "Part", "definition", "design_of", "mm", "pt"]
