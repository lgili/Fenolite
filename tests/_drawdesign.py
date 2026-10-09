# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bench board of the drawing kinds (change c0117; capability kicad-oracle, "Drawing facts are
probed"). Authored for Fenolite with round invented values; nothing is downloaded.

A four-copper board of 76 x 92 mm at (100 mm, 100 mm), where a built board sits, written by
``write_board`` for a target. It holds three through vias, one blind via and one micro via, a header with
two plated holes, a part with a plated slot and an unplated hole, catalog chips on both sides (one of them
do-not-populate) and a capacitor whose footprint shows ``${REFERENCE}`` on ``F.Fab``. ``bench_design``
also carries a model stack-up, for the tables; the board text holds none before c0101 writes it.
"""

from __future__ import annotations

import dataclasses
from functools import cache

from fenolite import catalog
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import mm
from fenolite.dsl.footprint import Footprint
from fenolite.model.board import Board, FootprintInstance, Outline, StackLayer, Stackup, Via
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.model.presentation import SheetFrameRef, TitleBlock

NAME = "drawbench"
MM = 1_000_000
ORIGIN = Point(100 * MM, 100 * MM)
WIDTH, HEIGHT = 76 * MM, 92 * MM
COPPER = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
TITLE = TitleBlock(title="Drawing bench", date="2026-10-07", revision="B", organization="Fenolite")
TOP_REFS = ("C1", "H1", "J1", "R1", "R3")
BOTTOM_REFS = ("R2",)
DNP_REF = "R3"
SHOWN_REF = "C1"
"""The part whose footprint shows ``${REFERENCE}`` on ``F.Fab``; every other part shows none there."""
REFERENCE_TEXT = (
    '(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab")'
    ' (uuid "d0a00000-0000-4000-8000-0000000000c1") (effects (font (size 0.5 0.5) (thickness 0.08))))'
)
DRILL_ROWS = (
    (True, "F.Cu", "B.Cu", 300_000, None, 3, ("via",)),
    (True, "F.Cu", "B.Cu", 1_000_000, None, 2, ("pad",)),
    (True, "F.Cu", "B.Cu", 1_000_000, 2_000_000, 1, ("pad",)),
    (False, "F.Cu", "B.Cu", 3_200_000, None, 1, ("pad",)),
    (True, "F.Cu", "In1.Cu", 100_000, None, 1, ("via",)),
    (True, "F.Cu", "In1.Cu", 200_000, None, 1, ("via",)),
)
"""The drill rows of the bench: plated, first and last layer, drill, slot length, count and kinds."""


def _at(x: int, y: int) -> Point:
    return Point(ORIGIN.x + x * MM, ORIGIN.y + y * MM)


def _id(kind: str, key: str) -> str:
    return derived_id(kind, "fenolite.drawbench", key)


@cache
def capacitor() -> FootprintDef:
    """An authored two-pad chip with a fabrication outline and a courtyard."""
    fp = Footprint("Bench", "Cap_2x1", kind="smd")
    fp.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1.2)))
    fp.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1.2)))
    fp.rect((mm(-1), mm(-0.6)), (mm(1), mm(0.6)), layer="F.Fab", width=mm(0.1))
    fp.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer="F.CrtYd", width=mm(0.05))
    return fp.definition


@cache
def holes() -> FootprintDef:
    """An authored part with one plated slot of 1 x 2 mm and one unplated hole of 3.2 mm."""
    fp = Footprint("Bench", "Slot_Hole", kind="through_hole")
    fp.pad(
        "1", at=(mm(-4), mm(0)), size=(mm(2), mm(3)), shape="oval", drill=mm(1), drill_shape="slot",
        drill_length=mm(2), drill_rotation=90,
    )  # fmt: skip
    fp.pad(
        "2", at=(mm(4), mm(0)), size=(mm(3.2), mm(3.2)), shape="circle", kind="np_thru_hole", drill=mm(3.2)
    )
    fp.rect((mm(-6), mm(-2)), (mm(6), mm(2)), layer="F.Fab", width=mm(0.1))
    fp.rect((mm(-7), mm(-3)), (mm(7), mm(3)), layer="F.CrtYd", width=mm(0.05))
    return fp.definition


def _placed(
    ref: str, defn: FootprintDef, x: int, y: int, side: str = "top"
) -> tuple[Component, FootprintInstance]:
    component = Component(
        id=_id("cmp", ref), ref=ref, value=f"V{ref}", path=f"/{ref}", lib_footprint_ref=defn.lib_id
    )
    defn = prepare_authored_definition(defn)
    placed = place_footprint(defn, component=component, at=_at(x, y), side=side, key=ref, copper=COPPER)  # type: ignore[arg-type]
    if ref == DNP_REF:
        placed = dataclasses.replace(placed, attributes=(*placed.attributes, "dnp"))
    return component, placed


def stackup() -> Stackup:
    """A four-copper stack-up of 1.58 mm with round invented values."""

    def layer(name: str, kind: str, thickness: int, material: str = "", er: str = "") -> StackLayer:
        return StackLayer(id=_id("sly", name), name=name, kind=kind, thickness=thickness, material=material,
                          epsilon_r=er)  # type: ignore[arg-type]  # fmt: skip

    return Stackup(
        id=_id("stk", "stackup"),
        layers=(
            layer("F.SilkS", "silkscreen", 0),
            layer("F.Mask", "soldermask", 10_000),
            layer("F.Cu", "copper", 35_000),
            layer("dielectric 1", "dielectric", 200_000, "FR4", "4.5"),
            layer("In1.Cu", "copper", 35_000),
            layer("dielectric 2", "dielectric", 1_020_000, "FR4", "4.5"),
            layer("In2.Cu", "copper", 35_000),
            layer("dielectric 3", "dielectric", 200_000, "FR4", "4.5"),
            layer("B.Cu", "copper", 35_000),
            layer("B.Mask", "soldermask", 10_000),
            layer("B.SilkS", "silkscreen", 0),
        ),
        finish="ENIG",
    )


@cache
def bench_design(*, bottom: bool = True) -> Design:
    """The bench as a model, with its stack-up; without the bottom part when ``bottom`` is false."""
    design = Design.new(NAME, seed=117)
    gnd = Net(id=_id("net", "GND"), name="GND")
    parts = [
        _placed("R1", catalog.get_footprint("Fenolite:Chip_0603"), 20, 20),
        _placed("R3", catalog.get_footprint("Fenolite:Chip_0805"), 40, 20),
        _placed("J1", catalog.get_footprint("Fenolite:Header_1x2_P2.5"), 20, 50),
        _placed("H1", holes(), 50, 50),
        _placed("C1", capacitor(), 20, 70),
    ]
    if bottom:
        parts.append(_placed("R2", catalog.get_footprint("Fenolite:Chip_0603"), 60, 20, "bottom"))

    def via(n: int, x: int, y: int, drill: int, layers: tuple[str, str], kind: str = "through") -> Via:
        return Via(id=_id("via", str(n)), position=_at(x, y), diameter=drill + 300_000, drill=drill,
                   layers=layers, net_id=gnd.id, via_type=kind)  # type: ignore[arg-type]  # fmt: skip

    vias = (
        via(1, 10, 80, 300_000, ("F.Cu", "B.Cu")),
        via(2, 15, 80, 300_000, ("F.Cu", "B.Cu")),
        via(3, 20, 80, 300_000, ("F.Cu", "B.Cu")),
        via(4, 30, 80, 200_000, ("F.Cu", "In1.Cu"), "blind"),
        via(5, 35, 80, 100_000, ("F.Cu", "In1.Cu"), "micro"),
    )
    corners = (_at(0, 0), _at(76, 0), _at(76, 92), _at(0, 92))
    assert design.board is not None
    board = Board(
        id=design.board.id,
        outline=Outline(id=_id("out", "outline"), points=corners),
        layers=created_layers(4),
        stackup=stackup(),
        footprints=tuple(placed for _, placed in parts),
        vias=vias,
        sheet=SheetFrameRef("A4"),
        title_block=TITLE,
    )
    circuit = Circuit(components=tuple(component for component, _ in parts), nets=(gnd,))
    return dataclasses.replace(design, circuit=circuit, board=board)


@cache
def bench_text(target: int, *, bottom: bool = True) -> str:
    """The bench written for ``target``, with the ``${REFERENCE}`` text added to ``C1`` by token edit."""
    text = write_board(bench_design(bottom=bottom), target=target).text
    start = text.index(f'(property "Reference" "{SHOWN_REF}"')
    return text[:start] + REFERENCE_TEXT + "\n\t\t" + text[start:]


__all__ = [
    "BOTTOM_REFS",
    "COPPER",
    "DNP_REF",
    "DRILL_ROWS",
    "HEIGHT",
    "NAME",
    "ORIGIN",
    "SHOWN_REF",
    "TOP_REFS",
    "WIDTH",
    "bench_design",
    "bench_text",
    "capacitor",
    "holes",
    "stackup",
]
