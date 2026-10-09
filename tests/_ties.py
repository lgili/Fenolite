# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-tie footprints and the boards that hold them, for the unit tests and for the net-tie bench (change
c0114). Every footprint is authored with ``fenolite.dsl.Footprint`` and placed with ``place_footprint``:
no file is read, nothing comes from a library, and every value is a round invented one."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.board import Board, FootprintInstance, Outline, Track
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MM = 1_000_000
LIBRARY = "Tie"
SQUARE = MM
"""The side of the square pads."""
ROUND = MM // 2
"""The diameter of the round pads of the footprint that follows KiCad's own net-tie form."""
OVERLAP = MM // 5
"""How far two touching square pads overlap."""
WIDTH = MM // 4


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def row(count: int, pitch: int) -> tuple[int, ...]:
    """The x of ``count`` pad centres ``pitch`` apart, centred on 0 (``pitch`` and ``count`` keep them
    whole nanometres)."""
    first = -(count - 1) * pitch // 2
    return tuple(first + index * pitch for index in range(count))


def tie_footprint(
    name: str,
    xs: Sequence[int],
    *,
    groups: Sequence[Sequence[str]] = (),
    size: int = SQUARE,
    shape: str = "rect",
    bridge: bool = False,
) -> FootprintDef:
    """An authored SMD footprint whose pads ``1``, ``2``, … sit at ``xs`` on the x axis. ``groups`` are its
    net-tie groups (``Footprint.net_tie``). ``bridge`` joins the first two pads with a filled polygon on
    ``F.Cu``, as the footprints of KiCad's own net-tie library do."""
    footprint = Footprint(LIBRARY, name, kind="smd")
    for number, x in enumerate(xs, start=1):
        footprint.pad(str(number), at=(nm(x), nm(0)), size=(nm(size), nm(size)), shape=shape)
    if bridge:
        half = size // 4
        corners = ((xs[0], -half), (xs[1], -half), (xs[1], half), (xs[0], half))
        footprint.polygon(tuple((nm(x), nm(y)) for x, y in corners), layer="F.Cu", width=nm(0))
    for group in groups:
        footprint.net_tie(*group)
    defn = footprint.definition
    if bridge:
        defn = dataclasses.replace(
            defn, graphics=tuple(dataclasses.replace(graphic, filled=True) for graphic in defn.graphics)
        )
    return defn


@dataclass
class TieBoard:
    """A created two-layer board of placed authored footprints and tracks. Each pad is on a net of its own,
    ``<ref>_<number>``, unless ``nets`` says otherwise; ``clearance`` is the clearance of the ``Default``
    class that every net joins (``None``: no class, as on a board whose rules come from a project file)."""

    clearance: int | None = None
    nets: dict[str, Net] = field(default_factory=lambda: {})
    members: dict[str, list[PinRef]] = field(default_factory=lambda: {})
    components: list[Component] = field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = field(default_factory=lambda: [])
    tracks: list[Track] = field(default_factory=lambda: [])
    uuids: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})

    def net(self, name: str) -> str:
        if name not in self.nets:
            self.nets[name] = Net(id=_id("net", len(self.nets) + 1), name=name)
        return self.nets[name].id

    def place(
        self, ref: str, defn: FootprintDef, at: Point, nets: Mapping[str, str] | None = None
    ) -> FootprintInstance:
        """``defn`` placed as ``ref``; ``uuids["<ref>:<number>"]`` holds the KiCad uuids of that pad."""
        component = Component(
            id=_id("cmp", len(self.components) + 1), ref=ref, value=defn.name, lib_footprint_ref=defn.lib_id
        )
        placed = place_footprint(prepare_authored_definition(defn), component=component, at=at, key=ref)
        names = {pad.number: f"{ref}_{pad.number}" for pad in placed.pads} if nets is None else dict(nets)
        pads = tuple(
            dataclasses.replace(pad, net_id=self.net(names[pad.number]) if pad.number in names else None)
            for pad in placed.pads
        )
        placed = dataclasses.replace(placed, pads=pads)
        for pad in pads:
            if pad.net_id is not None:
                self.members.setdefault(pad.net_id, []).append(PinRef(component.id, pad.number))
            key = f"{ref}:{pad.number}"
            self.uuids[key] = (*self.uuids.get(key, ()), kicad_uuid(pad))
        self.uuids[ref] = (kicad_uuid(placed),)
        self.components.append(component)
        self.footprints.append(placed)
        return placed

    def track(self, label: str, net: str, start: Point, end: Point, *, width: int = WIDTH) -> Track:
        track = Track(
            id=_id("trk", len(self.tracks) + 1),
            start=start,
            end=end,
            width=width,
            layer="F.Cu",
            net_id=self.net(net),
        )
        self.tracks.append(track)
        self.uuids[label] = (kicad_uuid(track),)
        return track

    def build(self, *, width: int = 60 * MM, height: int = 40 * MM) -> Design:
        classes: tuple[NetClass, ...] = ()
        class_id: str | None = None
        if self.clearance is not None:
            classes = (NetClass(id=_id("cls", 1), name="Default", clearance=self.clearance),)
            class_id = classes[0].id
        nets = tuple(
            dataclasses.replace(net, members=tuple(self.members.get(net.id, ())), netclass_id=class_id)
            for net in self.nets.values()
        )
        board = Board(
            id=_id("brd", 1),
            outline=Outline(
                id=_id("out", 1),
                points=(Point(0, 0), Point(width, 0), Point(width, height), Point(0, height)),
            ),
            layers=created_layers(2),
            footprints=tuple(self.footprints),
            tracks=tuple(self.tracks),
        )
        base = Design.new("ties", seed=0)
        circuit = Circuit(components=tuple(self.components), nets=nets, netclasses=classes)
        return dataclasses.replace(base, circuit=circuit, board=board)


__all__ = ["LIBRARY", "MM", "OVERLAP", "ROUND", "SQUARE", "WIDTH", "TieBoard", "row", "tie_footprint"]
