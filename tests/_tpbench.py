# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test-point bench of change c0229: authored two-layer boards whose nets ``fenolite testpoints
--place`` gives probes. No file is read, nothing comes from a library, and every value is a round invented
one.

``PIN2`` is a two-pin through-hole part: round pads of 1.6 mm with a drill of 0.8 mm at x = -1.27 mm and
+1.27 mm, and a courtyard rectangle of 4.6 mm x 2.2 mm on the front. ``covered`` places six of them, ``R1``
to ``R3`` on a row at y = 10 mm and ``R4`` to ``R6`` on a row at y = 28 mm, and joins pad ``k`` of ``Rn``
and of ``R(n+3)`` in net ``N<n><A|B>``: six nets with copper on both outer layers and no test point.
``blocked`` adds ``U1``, a bottom part with a courtyard of 14 mm x 14 mm whose two pads, 1.2 mm apart in
its middle, are its net ``HIDDEN``: every bottom site within 5 mm of them lies under that courtyard."""

from __future__ import annotations

import dataclasses

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, mm
from fenolite.model.board import Board, FootprintInstance, Outline
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MM = 1_000_000
CLEARANCE = 200_000
WIDTH = 250_000


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def pin2() -> FootprintDef:
    """The two-pin through-hole part of the bench."""
    footprint = Footprint("Bench", "PIN2", kind="through_hole")
    for number, x in (("1", -1.27), ("2", 1.27)):
        footprint.pad(
            number,
            at=(mm(x), mm(0)),
            size=(mm(1.6), mm(1.6)),
            shape="circle",
            kind="thru_hole",
            drill=mm(0.8),
            layers=("*.Cu", "*.Mask"),
        )
    footprint.rect((mm(-2.3), mm(-1.1)), (mm(2.3), mm(1.1)), layer="F.CrtYd", width=mm(0.05))
    return footprint.definition


def pad14() -> FootprintDef:
    """Two surface pads of 0.8 mm, 1.2 mm apart, in the middle of a courtyard of 14 mm x 14 mm."""
    footprint = Footprint("Bench", "PAD14", kind="smd")
    footprint.pad("1", at=(mm(-0.6), mm(0)), size=(mm(0.8), mm(0.8)))
    footprint.pad("2", at=(mm(0.6), mm(0)), size=(mm(0.8), mm(0.8)))
    footprint.rect((mm(-7), mm(-7)), (mm(7), mm(7)), layer="F.CrtYd", width=mm(0.05))
    return footprint.definition


PIN2 = pin2()
PAD14 = pad14()


@dataclasses.dataclass
class Bench:
    """A created two-layer board; ``join`` puts pads on named nets."""

    width: int = 50 * MM
    height: int = 40 * MM
    components: list[Component] = dataclasses.field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = dataclasses.field(default_factory=lambda: [])
    nets: dict[str, list[PinRef]] = dataclasses.field(default_factory=lambda: {})
    pads: dict[tuple[str, str], str] = dataclasses.field(default_factory=lambda: {})

    def place(self, ref: str, at: Point, defn: FootprintDef, *, side: str = "top") -> None:
        component = Component(
            id=_id("cmp", len(self.components) + 1), ref=ref, value="X", lib_footprint_ref=defn.lib_id
        )
        placed = place_footprint(
            prepare_authored_definition(defn),
            component=component,
            at=at,
            side=side,  # type: ignore[arg-type]
            key=ref,
        )
        self.components.append(component)
        self.footprints.append(placed)

    def join(self, net: str, *pins: tuple[str, str]) -> None:
        ids = {c.ref: c.id for c in self.components}
        self.nets.setdefault(net, []).extend(PinRef(ids[ref], number) for ref, number in pins)
        for pin in pins:
            self.pads[pin] = net

    def build(self) -> Design:
        w, h = self.width, self.height
        classes = (NetClass(id=_id("cls", 1), name="Default", clearance=CLEARANCE, track_width=WIDTH),)
        nets = tuple(
            Net(id=_id("net", n + 1), name=name, netclass_id=classes[0].id, members=tuple(sorted(pins)))
            for n, (name, pins) in enumerate(sorted(self.nets.items()))
        )
        net_ids = {net.name: net.id for net in nets}
        refs = {c.id: c.ref for c in self.components}
        footprints = tuple(
            dataclasses.replace(
                fp,
                pads=tuple(
                    dataclasses.replace(
                        pad, net_id=net_ids.get(self.pads.get((refs[fp.component_id], pad.number), ""))
                    )
                    for pad in fp.pads
                ),
            )
            for fp in self.footprints
        )
        board = Board(
            id=_id("brd", 1),
            outline=Outline(id=_id("out", 1), points=(Point(0, 0), Point(w, 0), Point(w, h), Point(0, h))),
            layers=created_layers(2),
            footprints=footprints,
        )
        base = Design.new("probes", seed=0)
        circuit = Circuit(components=tuple(self.components), nets=nets, netclasses=classes)
        return dataclasses.replace(base, circuit=circuit, board=board)


def _rows(bench: Bench) -> None:
    for n, x in enumerate((10, 25, 40), start=1):
        bench.place(f"R{n}", Point(x * MM, 10 * MM), PIN2)
        bench.place(f"R{n + 3}", Point(x * MM, 28 * MM), PIN2)
    for n in (1, 2, 3):
        bench.join(f"N{n}A", (f"R{n}", "1"), (f"R{n + 3}", "1"))
        bench.join(f"N{n}B", (f"R{n}", "2"), (f"R{n + 3}", "2"))


def covered() -> Design:
    """Six nets on six through-hole parts, room around each."""
    bench = Bench()
    _rows(bench)
    return bench.build()


def blocked() -> Design:
    """``covered`` on a board of 50 mm x 60 mm with ``U1`` on the bottom at (25 mm, 45 mm), its two pads on
    the net ``HIDDEN``."""
    bench = Bench(height=60 * MM)
    _rows(bench)
    bench.place("U1", Point(25 * MM, 45 * MM), PAD14, side="bottom")
    bench.join("HIDDEN", ("U1", "1"), ("U1", "2"))
    return bench.build()


__all__ = ["CLEARANCE", "MM", "PAD14", "PIN2", "WIDTH", "Bench", "blocked", "covered", "pad14", "pin2"]
