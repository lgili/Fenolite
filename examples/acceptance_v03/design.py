# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""Authored v0.3 acceptance tree; every dimension is a Fenolite test choice.

The runner adds the neutral-model bus through acceptance_model: the DSL has no
arbitrary ranged-bus declaration. No external component library is required.
"""

from dataclasses import replace

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Footprint, Module, Net, Part, connect, mm, stack
from fenolite.model.board import ComponentBody, Hole, Layer
from fenolite.model.circuit import Bus, BusMember
from fenolite.model.design import Design as ModelDesign
from fenolite.model.library import FootprintDef


class AcceptanceLand(Footprint):
    @property
    def definition(self) -> FootprintDef:
        return replace(
            super().definition,
            bodies=(
                ComponentBody(
                    id=derived_id("bdy", "acceptance", "resistor"),
                    kind="extruded",
                    height=500_000,
                    outline=(
                        Point(-1_000_000, -500_000),
                        Point(1_000_000, -500_000),
                        Point(1_000_000, 500_000),
                        Point(-1_000_000, 500_000),
                    ),
                    layer="F.Fab",
                ),
            ),
        )


design = Design("acceptance_v03")
design.board(mm(60), mm(40), copper=6)
entries = []
for index in range(6):
    entries.append(stack.copper(mm("0.035")))
    if index < 5:
        entries.append(stack.core(mm("0.25"), material="TEST", epsilon_r="4"))
design.stackup(*entries)
design.sheet("A4", drawing_sheet="acceptance.sheet.toml")
land = AcceptanceLand("Acceptance", "TwoPin", kind="smd")
land.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1)))
land.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
land.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer="F.SilkS", width=mm("0.12"))
design.add_footprint(land)
parts = [Part(f"R{index + 1}", "Fenolite:Resistor", footprint=land.lib_id, value="1k") for index in range(4)]
front = Module("front")
stage = Module("stage")
stage.add(parts[2], parts[3])
front.add(parts[1], stage)
design.add(parts[0], front)
nets = [Net("D0"), Net("D1"), Net("GND")]
connect(nets[0], parts[0][1], parts[2][1])
connect(nets[1], parts[1][1], parts[3][1])
connect(nets[2], *(part[2] for part in parts))
for index, part in enumerate(parts):
    part.place(mm(10 + index * 10), mm(10))
# Sparse, isolated copper exercises representations; this is not a routed production board.
design.track("signal", (mm(5), mm(20)), (mm(15), mm(20)), net=nets[0], width=mm("0.25"))
for key, x, kind, layers in [
    ("through", 20, "through", None),
    ("blind", 25, "blind", ("F.Cu", "In1.Cu")),
    ("buried", 30, "buried", ("In1.Cu", "In2.Cu")),
]:
    design.via(key, mm(x), mm(20), net=nets[2], diameter=mm("0.6"), drill=mm("0.3"), kind=kind, layers=layers)
design.text("title", "V03 ACCEPTANCE", (mm(5), mm(5)))
design.rule_area(
    "keepout",
    [(mm(45), mm(25)), (mm(50), mm(25)), (mm(50), mm(30)), (mm(45), mm(30))],
    forbid=("tracks", "vias"),
)
design.zone(
    nets[2],
    layers=("F.Cu",),
    name="ground",
    outline=[(mm(2), mm(25)), (mm(15), mm(25)), (mm(15), mm(35)), (mm(2), mm(35))],
)
for kind, limits in {
    "clearance": {"min": mm("0.1")},
    "track_width": {"min": mm("0.1"), "opt": mm("0.25"), "max": mm(2)},
    "via_diameter": {"min": mm("0.4"), "opt": mm("0.6"), "max": mm(2)},
    "via_drill": {"min": mm("0.2"), "max": mm(1)},
    "hole_size": {"min": mm("0.2"), "max": mm(3)},
    "edge_clearance": {"min": mm("0.1")},
    "hole_to_hole": {"min": mm("0.1")},
    "annular_width": {"min": mm("0.1")},
}.items():
    design.rules.rule("acceptance_" + kind, kind, **limits)


def acceptance_model(model: ModelDesign) -> ModelDesign:
    ids = {net.name: net.id for net in model.circuit.nets}
    bus = Bus(
        id=derived_id("bus", "acceptance", "D"),
        name="D",
        members=tuple(BusMember(index, ids[f"D{index}"]) for index in range(2)),
    )
    return replace(
        model,
        circuit=replace(model.circuit, buses=(bus,)),
        board=replace(
            model.board,
            layers=model.board.layers
            or tuple(
                Layer(id=derived_id("lay", "acceptance", name), name=name, kind="copper", ordinal=index)
                for index, name in enumerate(("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"))
            ),
            footprints=tuple(
                replace(
                    fp,
                    bodies=tuple(
                        replace(body, id=derived_id("bdy", "acceptance", fp.id))
                        for body in land.definition.bodies
                    ),
                )
                for fp in model.board.footprints
            ),
            holes=(
                Hole(
                    id=derived_id("hol", "acceptance", "free"),
                    position=Point(BOARD_ORIGIN.x + 55_000_000, BOARD_ORIGIN.y + 35_000_000),
                    drill=2_000_000,
                ),
            ),
        ),
    )
