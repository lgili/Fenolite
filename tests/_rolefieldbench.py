# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored inputs to c0366's field compiler and search; no external board data."""

from dataclasses import replace

from _searchbench import bench, point, wall

from fenolite.model.board import Outline, Zone, ZoneFill, ZoneSettings
from fenolite.model.circuit import Net
from fenolite.model.rules import NetRole, RoleSet


def field_bench(
    *, four: bool = False, ground: str = "valid", sensitive: bool = True, switch: str = "declared"
):
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") if four else ("F.Cu", "B.Cu")
    job, subject, _ = bench(layers=layers, tracks=(wall("switch", 6, 4, 6, width=100_000),))
    assert job.design.board is not None
    ring = (point(1, 1), point(11, 1), point(11, 9), point(1, 9))
    reference = layers[1]
    zone = Zone(
        id="zon_ground",
        name="reference",
        net_id="net_gnd",
        layers=(reference,),
        outline=ring,
        filled=True,
        fills=(ZoneFill(reference, ring),),
        settings=ZoneSettings(clearance=100_000, island_removal="never"),
    )
    if ground == "missing":
        zone = replace(zone, filled=False, fills=())
    if ground == "stale":
        zone = replace(
            zone, fills=(ZoneFill(reference, (point(-1, 1), point(11, 1), point(11, 9), point(-1, 9))),)
        )
    if ground == "island":
        zone = replace(zone, fills=(ZoneFill(reference, ring, island=True),))
    board = replace(
        job.design.board, outline=Outline(id="out_fields", points=job.extra["outline"][0]), zones=(zone,)
    )
    circuit = replace(job.design.circuit, nets=(*job.design.circuit.nets, Net(id="net_gnd", name="GND")))
    design = replace(job.design, board=board, circuit=circuit)
    roles = RoleSet(
        nets=(
            NetRole("SIG", "signal", "declared", sensitive=sensitive),
            NetRole("WALL", "switch_node", switch, confidence="high" if switch == "inferred" else ""),
            NetRole("GND", "ground", "declared"),
        )
    )
    return replace(job, design=design), subject, roles
