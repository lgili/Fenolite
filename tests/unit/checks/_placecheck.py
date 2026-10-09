# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored layouts for the placement rules and measures (change c0113): a board box, parts whose pads are
given by position, nets and zones, built without any backend. Every value is round and invented for these
tests."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Graphic, Layer, Outline, Zone
from fenolite.model.circuit import Circuit, Component, Net, NetClass
from fenolite.model.design import Design

MM = 1_000_000
PadAt = tuple[str, float, float, str | None]
"""``(number, x in mm, y in mm, net name or None)``."""


def at(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


@dataclass
class Layout:
    """A board of ``width`` × ``height`` millimetres (no box when ``width`` is ``None``) and its parts."""

    width: float | None = 50
    height: float = 30
    edge: bool = False
    """With ``edge``, the box is drawn as four lines on ``Edge.Cuts`` and the model holds no outline."""
    components: list[Component] = field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = field(default_factory=lambda: [])
    pads: list[BoardPad] = field(default_factory=lambda: [])
    nets: dict[str, Net] = field(default_factory=lambda: {})
    zones: list[Zone] = field(default_factory=lambda: [])
    classes: list[NetClass] = field(default_factory=lambda: [])

    def net(self, name: str) -> str:
        if name not in self.nets:
            self.nets[name] = Net(id=f"net_{name}", name=name)
        return self.nets[name].id

    def part(
        self,
        ref: str,
        *pads: PadAt,
        path: str | None = None,
        position: tuple[float, float] | None = None,
    ) -> None:
        """A part whose position is that of its first pad unless ``position`` gives one. ``path`` is its
        component path (``None``: the board holds none, as a board that no script built)."""
        where = position if position is not None else (pads[0][1], pads[0][2])
        properties = {} if path is None else {"fenolite.path": path}
        self.components.append(Component(id=f"cmp_{ref}", ref=ref, properties=properties))
        self.footprints.append(
            FootprintInstance(id=f"fpi_{ref}", component_id=f"cmp_{ref}", lib_ref="", position=at(*where))
        )
        for n, (number, x, y, net) in enumerate(pads):
            self.pads.append(
                BoardPad(
                    footprint_id=f"fpi_{ref}",
                    ref=ref,
                    path=path or "",
                    pad_id=f"pad_{ref}_{n}",
                    number=number,
                    kind="smd",
                    position=at(x, y),
                    rotation=0,
                    side="top",
                    layers=("F.Cu",),
                    net_id=None if net is None else self.net(net),
                    net=net,
                )
            )

    def zone(self, net: str) -> None:
        ring = (at(0, 0), at(1, 0), at(1, 1))
        self.zones.append(Zone(id=f"zon_{net}", outline=ring, layers=("F.Cu",), net_id=self.net(net)))

    def default_class(self, track_width: int | None, clearance: int | None) -> None:
        self.classes.append(
            NetClass(id="cls_default", name="Default", track_width=track_width, clearance=clearance)
        )

    def build(self) -> tuple[Design, tuple[BoardPad, ...]]:
        outline = None
        graphics: tuple[Graphic, ...] = ()
        layers: tuple[Layer, ...] = ()
        if self.width is not None:
            corners = (at(0, 0), at(self.width, 0), at(self.width, self.height), at(0, self.height))
            if self.edge:
                layers = (Layer(id="lay_edge", name="Edge.Cuts", kind="edge", ordinal=44),)
                graphics = tuple(
                    Graphic(id=f"gfx_{n}", kind="line", layer="Edge.Cuts", points=(a, b))
                    for n, (a, b) in enumerate(zip(corners, (*corners[1:], corners[0]), strict=True))
                )
            else:
                outline = Outline(id="out_1", points=corners)
        base = Design.new("layout", seed=0)
        board = Board(
            id="brd_1",
            outline=outline,
            layers=layers,
            footprints=tuple(self.footprints),
            zones=tuple(self.zones),
            graphics=graphics,
        )
        circuit = Circuit(
            components=tuple(self.components), nets=tuple(self.nets.values()), netclasses=tuple(self.classes)
        )
        return dataclasses.replace(base, circuit=circuit, board=board), tuple(self.pads)


__all__ = ["MM", "Layout", "at"]
