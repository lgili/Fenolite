# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored topology benches with round integer geometry; no external library or board data.

The default path is 30 mm on F.Cu, a via, and 20 mm on In1.Cu. The hand-computed delay is
30 * 5900 + 10000 + 20 * 6900 = 325000 fs. All example inputs are invented for this bench.
"""

from dataclasses import replace

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, FootprintInstance, Layer, Pad, Track, Via
from fenolite.model.circuit import Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.rules import LayerLoss, Propagation, RuleSet, Topology, TopologyConstraint, TopologyEdge

MM = 1_000_000


def ident(prefix: str, name: str) -> str:
    return derived_id(prefix, "topology-bench", name)


def bench(*, max_fs: int = 400_000) -> Design:
    design = Design.new("timed", seed=0)
    components = tuple(
        Component(
            id=ident("cmp", f"U{i}"),
            ref=f"U{i}",
            path=f"U{i}",
            pins=(Pin(id=ident("pin", f"U{i}-1"), number="1"),),
        )
        for i in (1, 2)
    )
    net = Net(id=ident("net", "CLK"), name="CLK", members=tuple(PinRef(part.id, "1") for part in components))
    footprints = tuple(
        FootprintInstance(
            id=ident("fp", part.ref),
            component_id=part.id,
            lib_ref="authored",
            position=Point(x * MM, 0),
            pads=(
                Pad(
                    id=ident("pad", part.ref),
                    number="1",
                    shape="circle",
                    size=Size(MM, MM),
                    position=Point(0, 0),
                    layers=(layer,),
                    net_id=net.id,
                ),
            ),
        )
        for part, x, layer in zip(components, (0, 50), ("F.Cu", "In1.Cu"), strict=True)
    )
    topology = Topology(
        id=ident("top", "clk"),
        name="clk",
        nodes=("U1-1", "U2-1"),
        edges=(TopologyEdge("U1-1", "U2-1", net="CLK"),),
        constraints=(TopologyConstraint("delay", ("U1-1", "U2-1"), max_fs=max_fs),),
    )
    return replace(
        design,
        circuit=replace(design.circuit, components=components, nets=(net,)),
        board=Board(
            id=ident("brd", "bench"),
            layers=tuple(
                Layer(id=ident("lay", layer), name=layer, kind="copper", ordinal=index)
                for index, layer in enumerate(("F.Cu", "In1.Cu", "B.Cu"))
            ),
            footprints=footprints,
            tracks=(
                Track(
                    id=ident("trk", "front"),
                    start=Point(0, 0),
                    end=Point(30 * MM, 0),
                    width=MM // 4,
                    layer="F.Cu",
                    net_id=net.id,
                ),
                Track(
                    id=ident("trk", "inner"),
                    start=Point(30 * MM, 0),
                    end=Point(50 * MM, 0),
                    width=MM // 4,
                    layer="In1.Cu",
                    net_id=net.id,
                ),
            ),
            vias=(
                Via(
                    id=ident("via", "one"),
                    position=Point(30 * MM, 0),
                    diameter=600_000,
                    drill=300_000,
                    layers=("F.Cu", "In1.Cu"),
                    net_id=net.id,
                ),
            ),
        ),
        rules=RuleSet(
            id=ident("rst", "bench"),
            topologies=(topology,),
            propagation=(
                Propagation("F.Cu", 5_900),
                Propagation("In1.Cu", 6_900),
                Propagation(via_fs=10_000),
            ),
            losses=(LayerLoss("F.Cu", 4), LayerLoss("In1.Cu", 6), LayerLoss(via_mdb=2)),
        ),
    )
