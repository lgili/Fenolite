# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ground planes and stitching of the role copper (change c0243, decision 5; capability net-roles, "Ground
copper and stitching", scenario "Ground joined in pieces"; hypothesis ``H-G-ROLE-COPPER-STITCH``)."""

from __future__ import annotations

from pathlib import Path

from _rolecopper import board, build_role, outcome, variant

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.pour import pour_copper
from fenolite.analysis.practice import analyze_dead
from fenolite.geometry import Location, Polygon, point_in_ring, polygons_intersect
from fenolite.roles.copper import STITCH_MIN_VIAS, with_simulated_fills


def test_ground_joined_in_pieces(tmp_path: Path) -> None:
    script = variant(
        tmp_path,
        "half_bridge",
        'design = make(Design("half_bridge_two_planes"), "good", power=False)\n'
        'gnd = design.nets["GND"]\n'
        'design.net_role(gnd, "ground")\n'
        'design.net_role(design.nets["SRC"], "power", current=amp(5))\n'
        'design.net_role(design.nets["SW"], "switch_node", current=amp(5))\n'
        "design.role_limits(net=gnd, milliamps_per_via=amp(4))\n"
        'design.role_copper(ground_layers=("In1.Cu", "B.Cu"))',  # no distance row: the bus is left out
    )
    built = build_role(script, tmp_path / "out")
    held = board(built)
    found = held.design.board
    assert found is not None
    gnd = next(net.id for net in held.design.circuit.nets if net.name == "GND")
    planes = [z for z in found.zones if z.net_id == gnd and z.name.startswith("role.ground.GND.")]
    layers = {layer for zone in planes for layer in zone.layers}
    assert {"In1.Cu", "B.Cu"} <= layers
    vias = [via.position for via in found.vias if via.net_id == gnd]
    checked = 0
    for i, a in enumerate(planes):
        for b in planes[i + 1 :]:
            if set(a.layers) == set(b.layers) or not polygons_intersect(
                Polygon(a.outline), Polygon(b.outline)
            ):
                continue
            inside = [
                v
                for v in vias
                if point_in_ring(v, a.outline) is Location.INSIDE
                and point_in_ring(v, b.outline) is Location.INSIDE
            ]
            assert len(inside) >= STITCH_MIN_VIAS, (a.name, b.name, len(inside))
            checked += 1
    assert checked
    assert not [i for i in outcome(built).issues if i.code == "kicad.generate.stitch-short"]
    filled = with_simulated_fills(held.design, held.pads)
    assert filled.board is not None
    pour = pour_copper(filled, pads=held.pads, boundary=board_boundary(filled.board))
    dead = analyze_dead(filled, pads=held.pads, pour=pour)
    names = {zone.id: zone.name for zone in filled.board.zones}
    role_ids = {zid for zid, name in names.items() if name.startswith("role.ground.")}
    assert not [
        row for row in dead.rows if any(zid in row.where for zid in role_ids) or "role.ground" in row.where
    ]
    assert not [i for i in dead.issues if i.code == "analysis.copper-dead" and "GND" in i.message]
