# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""High-voltage role copper (change c0243, decision 7; capability net-roles, "High-voltage copper",
scenario "The bus keeps the user's distance")."""

from __future__ import annotations

from collections.abc import Callable

from _roleboards import Built
from _rolecopper import board, outcome, plan_on, resolved

from fenolite.analysis.requirements import load_requirements
from fenolite.geometry import Thick, thick_closer_than
from fenolite.roles import copper

MM = 1_000_000
THREE_MM = """\
schema = "fenolite.requirements.v0"

[[distance]]
a = { net = "VBUS" }
b = { net = "*" }
clearance_nm = 3000000
creepage_nm = 3000000
"""


def test_the_bus_keeps_the_users_distance(role_copper: Callable[..., Built]) -> None:
    built = role_copper("half_bridge", "good")
    held, found = resolved(built)
    requirements = load_requirements(THREE_MM, file="requirements.toml")
    plan = copper.plan(held.design, held.pads, found.resolved.roles, requirements=requirements,
                       classes=found.resolved.classes)  # fmt: skip
    (rule,) = [r for r in plan.rules if r.name == "role.hv.VBUS"]
    assert rule.min == 3 * MM and rule.kind == "clearance"
    (barrier,) = [r for r in plan.records if isinstance(r, copper.RoleBarrier)]
    assert barrier.nets == ("VBUS",) and barrier.setback == 3 * MM and barrier.pieces
    vbus_band = [r for r in plan.records if isinstance(r, copper.RoleBand) and r.net == "VBUS"]
    assert vbus_band and all(r.max_width == r.width for r in vbus_band)  # a high-voltage net does not widen
    # the build at the board's own 1.2 mm row: the barrier holds the bus band, nothing else comes near it
    held = board(built)
    assert held.design.board is not None
    names = {net.id: net.name for net in held.design.circuit.nets}
    bus = [
        z
        for z in held.design.board.zones
        if z.name.startswith("role.") and names.get(z.net_id or "") == "VBUS"
    ]
    areas = [k for k in held.design.board.keepouts if k.name.startswith("role.hv.VBUS.")]
    assert bus and areas and all(k.no_copper_pour and k.no_tracks and k.no_vias for k in areas)
    xs = [p.x for k in areas for p in k.outline]
    ys = [p.y for k in areas for p in k.outline]
    for zone in bus:
        for point in zone.outline:
            assert min(xs) <= point.x <= max(xs) and min(ys) <= point.y <= max(ys)
    others = [
        z for z in held.design.board.zones
        if z.name.startswith("role.") and names.get(z.net_id or "") not in ("VBUS", "GND")
    ]  # fmt: skip
    for zone in bus:
        shape = Thick(tuple(zone.outline), 0, filled=True)
        for other in others:
            if set(other.layers) & set(zone.layers):
                assert not thick_closer_than(shape, Thick(tuple(other.outline), 0, filled=True), 1_200_000)


def test_no_row_no_copper(role_copper: Callable[..., Built]) -> None:
    """Without a distance row the bus gets nothing and ``roles.limit-missing``."""
    built = role_copper("half_bridge", "good")
    plan = plan_on(built, "bms")  # the BMS board has no requirements file
    assert not [
        r for r in plan.records if getattr(r, "net", "") == "VBUS" or getattr(r, "nets", ()) == ("VBUS",)
    ]
    (missing,) = [i for i in plan.issues if i.code == "roles.limit-missing"]
    assert missing.where == "VBUS" and missing.severity == "warning"
    assert not [r for r in plan.rules if r.name.startswith("role.hv.")]
    assert [r.name for r in outcome(built).plan.rules] == ["role.hv.VBUS"]  # with its row, the build has it
