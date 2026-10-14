# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""Authored acceptance circuit, with a model hook for its bus, stack and bodies (c0092).

All dimensions and labels are invented for Fenolite. No organisation's circuit is used.
The acceptance runner applies the hook after building the same circuit for both targets.
"""

from dataclasses import replace

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Module, Net, Part, connect, mm
from fenolite.model.board import ComponentBody, Hole, StackLayer, Stackup
from fenolite.model.circuit import Bus, BusMember

design = Design("acceptance_v03")
design.board(mm(50), mm(30), copper=6)
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="2k")
io = Module("io")
outputs = Module("outputs")
outputs.add(r2)
io.add(r1, outputs)
design.add(j1, io)
d0, d1 = Net("D0"), Net("D1")
connect(d0, j1[1], r1[1], r2[1])
connect(d1, j1[2], r1[2], r2[2])
j1.place(mm(6), mm(15))
r1.place(mm(20), mm(15), rot=90)
r2.place(mm(35), mm(15), rot=90)
design.hole("H1", mm(45), mm(25), drill=mm(3.2))
design.text("legend", "FENOLITE ACCEPTANCE", (mm(20), mm(26)), layer="F.SilkS")
design.rule_area(
    "reserve",
    ((mm(40), mm(2)), (mm(47), mm(2)), (mm(47), mm(7)), (mm(40), mm(7))),
    forbid=("tracks", "vias", "pours"),
)
design.zone(
    d1, layers=("B.Cu",), outline=((mm(1), mm(1)), (mm(49), mm(1)), (mm(49), mm(29)), (mm(1), mm(29)))
)
design.via("through", mm(10), mm(18), net=d0, diameter=mm(0.6), drill=mm(0.3))
design.via(
    "blind", mm(15), mm(18), net=d0, kind="blind", layers=("F.Cu", "In1.Cu"), diameter=mm(0.6), drill=mm(0.3)
)
design.via(
    "buried",
    mm(15),
    mm(21),
    net=d0,
    kind="buried",
    layers=("In1.Cu", "In2.Cu"),
    diameter=mm(0.6),
    drill=mm(0.3),
)
design.track("inner", (mm(15), mm(18)), (mm(15), mm(21)), net=d0, layer="In1.Cu", width=mm(0.25))
for index, (net, pin, row) in enumerate(((d0, 1, 18), (d1, 2, 12))):
    for part, x in ((j1, 6), (r1, 20), (r2, 35)):
        design.track(f"branch-{index}-{part.ref}", part.pad(pin), (mm(x), mm(row)), net=net, width=mm(0.25))
    design.track(f"rail-{index}", (mm(6), mm(row)), (mm(35), mm(row)), net=net, width=mm(0.25))
design.rules.rule("gap", "clearance", min=mm(0.15))
design.rules.rule("width", "track_width", min=mm(0.15), opt=mm(0.25), max=mm(2))
design.rules.rule("via-size", "via_diameter", min=mm(0.5), opt=mm(0.6), max=mm(1))
design.rules.rule("via-hole", "via_drill", min=mm(0.2), max=mm(0.6))
design.rules.rule("hole", "hole_size", min=mm(0.2), max=mm(4))
design.rules.rule("edge", "edge_clearance", min=mm(0.2))
design.rules.rule("hole-gap", "hole_to_hole", min=mm(0.2))
design.rules.rule("ring", "annular_width", min=mm(0.1))


def acceptance_model(model):
    """The bus, six-layer physical stack and one authored extruded body per footprint."""
    bus = Bus(
        id=derived_id("bus", "acceptance", "D"),
        name="D",
        members=tuple(
            BusMember(index, next(net.id for net in model.circuit.nets if net.name == f"D{index}"))
            for index in range(2)
        ),
    )
    stack = []
    copper = [layer for layer in model.board.layers if layer.kind == "copper"]
    for index, layer in enumerate(copper):
        stack.append(
            StackLayer(
                id=derived_id("sly", "acceptance", layer.name),
                name=layer.name,
                kind="copper",
                thickness=35000,
            )
        )
        if index < len(copper) - 1:
            stack.append(
                StackLayer(
                    id=derived_id("sly", "acceptance", f"dielectric-{index}"),
                    name=f"dielectric {index + 1}",
                    kind="dielectric",
                    thickness=278000,
                    material="FR4",
                    epsilon_r="4.2",
                )
            )
    hole_ids = {component.id for component in model.circuit.components if component.ref == "H1"}
    holes = tuple(
        Hole(id=derived_id("hol", "acceptance", fp.id), position=fp.position, drill=fp.pads[0].drill)
        for fp in model.board.footprints
        if fp.component_id in hole_ids
    )
    footprints = tuple(
        replace(
            fp,
            bodies=(
                ComponentBody(
                    id=derived_id("bdy", "acceptance", fp.id),
                    kind="extruded",
                    height=1000000,
                    outline=(
                        Point(-500000, -500000),
                        Point(500000, -500000),
                        Point(500000, 500000),
                        Point(-500000, 500000),
                    ),
                    layer="F.Fab",
                ),
            ),
        )
        for fp in model.board.footprints
        if fp.component_id not in hole_ids
    )
    return replace(
        model,
        circuit=replace(
            model.circuit,
            buses=(bus,),
            components=tuple(
                component for component in model.circuit.components if component.id not in hole_ids
            ),
            no_connects=tuple(
                member for member in model.circuit.no_connects if member.component_id not in hole_ids
            ),
            modules=tuple(
                replace(
                    module,
                    component_ids=tuple(ident for ident in module.component_ids if ident not in hole_ids),
                )
                for module in model.circuit.modules
            ),
        ),
        board=replace(
            model.board,
            footprints=footprints,
            holes=(*model.board.holes, *holes),
            stackup=Stackup(id=derived_id("stk", "acceptance", "six"), layers=tuple(stack)),
        ),
    )
