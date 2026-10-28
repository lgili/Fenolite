# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The silkscreen bench of change c0212: authored two-layer boards of small two-pad parts whose
designators the command ``fenolite silk --designators`` places. No file is read, nothing comes from a
library, and every value is a round invented one.

``CHIP`` is a two-pad part: pads of 0.9 mm x 1 mm at x = -0.8 mm and +0.8 mm, a courtyard rectangle of
3 mm x 1.5 mm and two silkscreen strokes of 0.5 mm above and below its middle. ``row`` places parts turned
by 90 degrees in a row along x, ``pitch`` apart, with every designator left where the footprint puts it:
on the part's centre, over its pads.

The clip bench of change c0226: ``BOXED`` is a two-pad part whose silkscreen outline, an arc and a circle
cross its own pads; ``DOT`` is a one-pad part that ``clipped`` places under the outline of a ``BOXED``
instance; ``probe`` is a one-pad part with one silkscreen line, for the probes of what KiCad's DRC
measures."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from _ties import MM

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.fields import set_field
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Footprint, mm, nm
from fenolite.geometry import Transform
from fenolite.model.board import Board, FootprintInstance, Graphic, Outline
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

DEG = 1_000_000


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def chip() -> FootprintDef:
    """The two-pad part of the bench."""
    footprint = Footprint("Silk", "CHIP", kind="smd")
    footprint.pad("1", at=(mm(-0.8), mm(0)), size=(mm(0.9), mm(1)))
    footprint.pad("2", at=(mm(0.8), mm(0)), size=(mm(0.9), mm(1)))
    footprint.rect((mm(-1.5), mm(-0.75)), (mm(1.5), mm(0.75)), layer="F.CrtYd", width=mm(0.05))
    footprint.line((mm(-0.25), mm(-0.6)), (mm(0.25), mm(-0.6)), layer="F.SilkS", width=mm(0.1))
    footprint.line((mm(-0.25), mm(0.6)), (mm(0.25), mm(0.6)), layer="F.SilkS", width=mm(0.1))
    return footprint.definition


CHIP = chip()


def hole() -> FootprintDef:
    """A hole of 3 mm that is not plated, with a courtyard circle of 3.5 mm."""
    footprint = Footprint("Silk", "HOLE", kind="through_hole")
    footprint.pad(
        "", at=(mm(0), mm(0)), size=(mm(3), mm(3)), shape="circle", kind="np_thru_hole", drill=mm(3)
    )
    footprint.circle((mm(0), mm(0)), (mm(1.75), mm(0)), layer="F.CrtYd", width=mm(0.05))
    return footprint.definition


HOLE = hole()


def _um(value: int) -> int:
    return value * MM // 1000


def boxed() -> FootprintDef:
    """The two pads of ``CHIP`` under a silkscreen rectangle of 2.2 mm x 0.8 mm, an arc about pad 1 that
    clips its corners, and a circle over the lower right corner of pad 2; a courtyard of 3.2 mm x 2 mm."""
    footprint = Footprint("Silk", "BOXED", kind="smd")
    footprint.pad("1", at=(mm(-0.8), mm(0)), size=(mm(0.9), mm(1)))
    footprint.pad("2", at=(mm(0.8), mm(0)), size=(mm(0.9), mm(1)))
    footprint.rect((mm(-1.6), mm(-1)), (mm(1.6), mm(1)), layer="F.CrtYd", width=mm(0.05))
    footprint.rect((mm(-1.1), mm(-0.4)), (mm(1.1), mm(0.4)), layer="F.SilkS", width=mm(0.1))
    footprint.circle((mm(1.25), mm(0.5)), (mm(1.5), mm(0.5)), layer="F.SilkS", width=mm(0.1))
    definition = footprint.definition
    arc = Graphic(
        id=derived_id("gfx", "fenolite.dsl", f"{definition.lib_id}:graphic:arc"),
        kind="arc",
        layer="F.SilkS",
        points=(Point(_um(-1450), 0), Point(_um(-800), _um(-650)), Point(_um(-150), 0)),
        width=_um(100),
    )
    return dataclasses.replace(definition, graphics=(*definition.graphics, arc))


BOXED = boxed()


def dot() -> FootprintDef:
    """One pad of 0.3 mm x 0.3 mm with a courtyard of 0.6 mm x 0.6 mm and no silkscreen."""
    footprint = Footprint("Silk", "DOT", kind="smd")
    footprint.pad("1", at=(mm(0), mm(0)), size=(mm(0.3), mm(0.3)))
    footprint.rect((mm(-0.3), mm(-0.3)), (mm(0.3), mm(0.3)), layer="F.CrtYd", width=mm(0.05))
    return footprint.definition


DOT = dot()


def probe(line_y: int, *, mask: bool = True, margin: int | None = None) -> FootprintDef:
    """One pad of 1 mm x 1 mm (with its mask opening unless ``mask`` is false, and the mask margin
    ``margin``) and a silkscreen line of 0.8 mm with a 0.1 mm stroke along x, ``line_y`` from the pad's
    centre."""
    footprint = Footprint("Silk", "PROBE" if mask else "PROBE_BARE", kind="smd")
    if mask:
        footprint.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    else:
        footprint.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), layers=("F.Cu",))
    footprint.rect((mm(-1), mm(-1)), (mm(1), mm(1)), layer="F.CrtYd", width=mm(0.05))
    footprint.line((mm(-0.4), nm(line_y)), (mm(0.4), nm(line_y)), layer="F.SilkS", width=mm(0.1))
    definition = footprint.definition
    if margin is None:
        return definition
    pads = tuple(dataclasses.replace(pad, mask_margin=margin) for pad in definition.pads)
    return dataclasses.replace(definition, pads=pads)


@dataclasses.dataclass
class SilkBoard:
    """A created two-layer board of placed ``CHIP`` parts; each pad is on a net of its own."""

    width: int = 40 * MM
    height: int = 30 * MM
    components: list[Component] = dataclasses.field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = dataclasses.field(default_factory=lambda: [])
    nets: list[Net] = dataclasses.field(default_factory=lambda: [])

    def place(
        self,
        ref: str,
        at: Point,
        *,
        rotation: int = 0,
        side: str = "top",
        defn: FootprintDef = CHIP,
        ref_at: Point | None = None,
        ref_angle: int = 0,
    ) -> FootprintInstance:
        """Place ``defn`` with its designator at ``ref_at`` (default: over the part's centre) and the
        board angle ``ref_angle`` in degrees."""
        component = Component(
            id=_id("cmp", len(self.components) + 1), ref=ref, value="1k", lib_footprint_ref=defn.lib_id
        )
        placed = place_footprint(
            prepare_authored_definition(defn),
            component=component,
            at=at,
            rotation=rotation * DEG,
            side=side,  # type: ignore[arg-type]
            key=ref,
        )
        pads = []
        for pad in placed.pads:
            net = Net(id=_id("net", len(self.nets) + 1), name=f"{ref}_{pad.number}")
            self.nets.append(dataclasses.replace(net, members=(PinRef(component.id, pad.number),)))
            pads.append(dataclasses.replace(pad, net_id=net.id))
        placed = dataclasses.replace(placed, pads=tuple(pads))
        placed = set_field(
            placed, "Reference", anchor=at if ref_at is None else ref_at, angle=ref_angle * DEG
        )
        self.components.append(component)
        self.footprints.append(placed)
        return placed

    def build(self) -> Design:
        w, h = self.width, self.height
        classes = (NetClass(id=_id("cls", 1), name="Default", clearance=MM // 5),)
        nets = tuple(dataclasses.replace(net, netclass_id=classes[0].id) for net in self.nets)
        board = Board(
            id=_id("brd", 1),
            outline=Outline(id=_id("out", 1), points=(Point(0, 0), Point(w, 0), Point(w, h), Point(0, h))),
            layers=created_layers(2),
            footprints=tuple(self.footprints),
        )
        base = Design.new("silk", seed=0)
        circuit = Circuit(components=tuple(self.components), nets=nets, netclasses=classes)
        return dataclasses.replace(base, circuit=circuit, board=board)


START = Point(10 * MM, 15 * MM)


def row(count: int = 10, *, pitch: int = 1600 * MM // 1000, at: Point = START) -> Design:
    """``count`` parts ``R1`` ... turned by 90 degrees, in a row along x from ``at``, ``pitch`` apart."""
    board = SilkBoard()
    for index in range(count):
        board.place(f"R{index + 1}", Point(at.x + index * pitch, at.y), rotation=90)
    return board.build()


def mixed(sides: Sequence[str] = ("top", "bottom")) -> Design:
    """Three parts at 0, 90 and 30 degrees on each side in ``sides``, far enough apart that each designator
    has room on every side of its part, and the hole ``H1`` of 3 mm."""
    board = SilkBoard()
    count = 0
    for line, side in enumerate(sides):
        for column, rotation in enumerate((0, 90, 30)):
            count += 1
            board.place(
                f"C{count}", Point((8 + 10 * column) * MM, (8 + 12 * line) * MM), rotation=rotation, side=side
            )
    board.place("H1", Point(35 * MM, 25 * MM), defn=HOLE)
    return board.build()


def clipped(sides: Sequence[str] = ("top", "bottom")) -> Design:
    """Per side in ``sides``, ``BOXED`` at 0, 90 and 30 degrees and a fourth one at 0 degrees with ``DOT``
    under the middle of its upper outline; every designator 2.5 mm below its part in the part's own frame
    and turned with it, off every pad, so that the instances are equal in their own frame."""
    board = SilkBoard(width=50 * MM, height=40 * MM)
    count = 0
    for line, side in enumerate(sides):
        y = (10 + 18 * line) * MM
        for column, rotation in enumerate((0, 90, 30, 0)):
            count += 1
            at = Point((8 + 11 * column) * MM, y)
            below = Transform.placement(at, rotation * DEG).apply(Point(0, _um(2500)))
            board.place(
                f"U{count}", at, rotation=rotation, side=side, defn=BOXED, ref_at=below, ref_angle=rotation
            )
        # the outline's upper side lies at y - 0.4 mm on either side (a bottom part is mirrored in x only)
        spot = Point(41 * MM, y - _um(400))
        board.place(f"TP{line + 1}", spot, side=side, defn=DOT, ref_at=Point(spot.x + 4 * MM, spot.y))
    return board.build()


__all__ = [
    "BOXED",
    "CHIP",
    "DEG",
    "DOT",
    "HOLE",
    "SilkBoard",
    "boxed",
    "chip",
    "clipped",
    "dot",
    "hole",
    "mixed",
    "probe",
    "row",
]
