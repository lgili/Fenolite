# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The unrouted blink layout through the model API, for the probes-first group of c0011 (Decision 25).

Parts come from ``Mini_v9.pretty`` for both targets on a 50 mm × 30 mm board made with
``layers.created_layers(2)`` and ``embed.place_footprint``. ``offboard=True`` moves ``R1`` 10 mm right of
the outline.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point
from fenolite.core.units import Udeg
from fenolite.model.board import Board, FootprintInstance, Outline, Side
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design

LIBS = Path(__file__).resolve().parents[2] / "data" / "libs" / "Mini_v9.pretty"
MM = 1_000_000
ORIGIN = 100 * MM
PARTS: tuple[tuple[str, str, str, int, int, Udeg, Side, bool], ...] = (
    ("U1", "MCU", "Mini_QFP-32_7x7mm_P0.8mm", 14, 15, 0, "top", True),
    ("R1", "330", "Mini_R_0603", 32, 9, 0, "top", False),
    ("D1", "LED", "Mini_LED_THT_3mm", 38, 20, 0, "bottom", False),
)
NETS: dict[str, tuple[tuple[str, str], ...]] = {
    "VIN": (("U1", "9"),),
    "GND": (("U1", "10"), ("D1", "1")),
    "LED_DRV": (("U1", "1"), ("R1", "1")),
    "LED_A": (("R1", "2"), ("D1", "2")),
}


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def probe_board(target: int, *, offboard: bool = False) -> Design:
    """The blink layout for ``target`` (the design is the same for 9 and 10)."""
    del target
    nets = {name: Net(id=_id("net", i), name=name) for i, name in enumerate(NETS, start=1)}
    by_pin = {pin: nets[name].id for name, pins in NETS.items() for pin in pins}
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    for n, (ref, value, name, x, y, rot, side, locked) in enumerate(PARTS, start=1):
        defn = read_footprint(LIBS / f"{name}.kicad_mod", library="Mini")
        component = Component(id=_id("cmp", n), ref=ref, value=value, lib_footprint_ref=defn.lib_id)
        if ref == "R1" and offboard:
            x = 60
        at = Point(ORIGIN + x * MM, ORIGIN + y * MM)
        placed = place_footprint(
            defn, component=component, at=at, rotation=rot, side=side, locked=locked, key=ref
        )
        pads = tuple(dataclasses.replace(p, net_id=by_pin.get((ref, p.number))) for p in placed.pads)
        props = {k: v for k, v in defn.properties.items()} | {"Reference": ref, "Value": value}
        components.append(dataclasses.replace(component, properties=dict(sorted(props.items()))))
        footprints.append(dataclasses.replace(placed, pads=pads))
    ids = {c.ref: c.id for c in components}
    circuit = Circuit(
        components=tuple(components),
        nets=tuple(
            dataclasses.replace(nets[name], members=tuple(sorted(PinRef(ids[r], p) for r, p in pins)))
            for name, pins in NETS.items()
        ),
    )
    outline = Outline(
        id=_id("out", 1),
        points=(
            Point(ORIGIN, ORIGIN),
            Point(ORIGIN + 50 * MM, ORIGIN),
            Point(ORIGIN + 50 * MM, ORIGIN + 30 * MM),
            Point(ORIGIN, ORIGIN + 30 * MM),
        ),
    )
    board = Board(id=_id("brd", 1), outline=outline, layers=created_layers(2), footprints=tuple(footprints))
    return dataclasses.replace(Design.new("blink", seed=0), circuit=circuit, board=board)


__all__ = ["NETS", "PARTS", "probe_board"]
