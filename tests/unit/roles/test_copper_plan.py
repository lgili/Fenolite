# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role copper plan on the reference boards (change c0243; capability net-roles, "Role copper plan",
"Power and switch-node copper", "Switch node kept from sensitive copper" and "Pad connections per role")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from _roleboards import Built
from _rolecopper import board, outcome, plan_on, resolved

from fenolite.geometry import Polygon, Thick, polygons_intersect, thick_closer_than
from fenolite.model.rules import NetRole, RoleLimit
from fenolite.roles.copper import POUR_GRID_NM, Request, RoleBand

MM = 1_000_000


def _zones(built: Built) -> dict[str, list[object]]:
    held = board(built)
    assert held.design.board is not None
    names = {net.id: net.name for net in held.design.circuit.nets}
    found: dict[str, list[object]] = {}
    for zone in held.design.board.zones:
        if zone.name.startswith("role."):
            found.setdefault(names.get(zone.net_id or "", ""), []).append(zone)
    return found


def test_zones(role_copper: Callable[..., Built]) -> None:
    """Scenario "One zone per net and layer": the bare good buck."""
    built = role_copper("buck_shunt", "good")
    zones = _zones(built)
    for net in ("VIN", "SW", "VL", "VOUT"):
        on_top = [zone for zone in zones[net] if zone.layers == ("F.Cu",)]  # type: ignore[attr-defined]
        assert len(on_top) == 1, (net, [z.name for z in zones[net]])  # type: ignore[attr-defined]
        assert on_top[0].locked  # type: ignore[attr-defined]
    held = board(built)
    assert held.design.board is not None
    every = held.design.board.zones
    for i, a in enumerate(every):
        for b in every[i + 1 :]:
            same = a.net_id == b.net_id and a.priority == b.priority and set(a.layers) & set(b.layers)
            if same and len(a.outline) >= 3 and len(b.outline) >= 3:
                assert not polygons_intersect(Polygon(a.outline), Polygon(b.outline)), (a.name, b.name)
    done = outcome(built)
    sw = [r for r in done.plan.records if isinstance(r, RoleBand) and r.net == "SW"]
    (net_plan,) = [n for n in done.plan.nets if n.net == "SW"]
    assert sw and net_plan.width is not None
    assert all(r.width == r.max_width == net_plan.width + POUR_GRID_NM for r in sw)


def test_unconfirmed(role_copper: Callable[..., Built]) -> None:
    """Scenario "Only confirmed roles get copper"."""
    built = role_copper("buck_shunt", "good")
    _, found = resolved(built)
    roles = found.resolved.roles
    nets = tuple(replace(r, source="inferred") if r.net == "VOUT" else r for r in roles.nets)
    plan = plan_on(built, "buck_shunt", roles=replace(roles, nets=nets))
    keys = [r.key for r in plan.records] + [z.name for z in plan.zones] + [k.name for k in plan.keepouts]
    assert not [key for key in keys if "VOUT" in key and not key.startswith("role.corridor.")]
    (skipped,) = [i for i in plan.issues if i.code == "roles.copper-skipped" and i.where == "VOUT"]
    assert skipped.severity == "info" and "unconfirmed" in skipped.message


def test_victims(role_copper: Callable[..., Built]) -> None:
    """Scenario "Sense pair not under the switch node": the switch-node zone of the bad half-bridge keeps
    1 mm from the sense pair on its layer and on the layer under it; a victim net of its own gets the
    clearance rule ``role.sw.<net>``."""
    built = role_copper("half_bridge", "bad")
    held = board(built)
    assert held.design.board is not None
    names = {net.id: net.name for net in held.design.circuit.nets}
    sense = {pad.position for pad in held.pads if pad.ref == "U3" and pad.number in ("3", "4")}
    tracks = [t for t in held.design.board.tracks if t.start in sense or t.end in sense]
    assert len(tracks) >= 2
    sw = [z for z in held.design.board.zones if z.name.startswith("role.switch_node.")]
    assert sw and all(names.get(z.net_id or "") == "SW" for z in sw)
    for zone in sw:
        shape = Thick(tuple(zone.outline), 0, filled=True)
        for track in tracks:
            assert not thick_closer_than(shape, Thick((track.start, track.end), track.width), MM)
    assert not [
        r for r in outcome(built).plan.rules if r.name.startswith("role.sw.")
    ]  # its victims are branches
    buck = role_copper("buck_shunt", "good")
    _, found = resolved(buck)
    roles = found.resolved.roles
    nets = tuple(r for r in roles.nets if r.net != "ISNS") + (
        NetRole("ISNS", "signal", "declared", sensitive=True),
    )
    plan = plan_on(buck, "buck_shunt", roles=replace(roles, nets=nets))
    (rule,) = [r for r in plan.rules if r.name == "role.sw.SW"]
    assert rule.min == MM and rule.selector_b is not None and rule.selector_b.value == "ISNS"


def test_placement(role_copper: Callable[..., Built]) -> None:
    """A hot loop whose placement bound is over the user's ``loop_max`` gives ``roles.copper-placement``."""
    built = role_copper("buck_shunt", "bad")
    _, found = resolved(built)
    roles = found.resolved.roles
    limited = replace(roles, limits=(*roles.limits, RoleLimit("loop_max", 10 * MM * MM)))
    plan = plan_on(built, "buck_shunt", roles=limited)
    (fault,) = [i for i in plan.issues if i.code == "roles.copper-placement"]
    assert fault.where == "hot_SW" and fault.severity == "warning" and "10 mm²" in fault.message
    assert any(isinstance(r, RoleBand) for r in plan.records)  # the copper is still drawn
    assert not [i for i in outcome(built).issues if i.code == "roles.copper-placement"]


def test_connection(role_copper: Callable[..., Built]) -> None:
    """Scenario "Ground reliefs on through-hole pads": the bare good BMS."""
    built = role_copper("bms", "good")
    zones = _zones(built)
    assert zones["GND"] and all(z.settings.connection == "thru_hole_only" for z in zones["GND"])  # type: ignore[attr-defined]
    for net in ("BAT_P", "PACK_N", "SHUNT_N"):
        assert zones[net] and all(z.settings.connection == "solid" for z in zones[net])  # type: ignore[attr-defined]
    plan = plan_on(built, "bms", request=Request(connection={"ground": "solid"}))
    ground = [z for z in plan.zones if z.name.startswith("role.ground.")]
    bands = [r for r in plan.records if isinstance(r, RoleBand) and r.net == "GND"]
    assert ground and all(z.settings.connection == "solid" for z in ground)
    assert all(r.connection == "solid" for r in bands)


def test_loose_ends_joined(role_copper: Callable[..., Built]) -> None:
    """Scenario "Loose ends joined": the switch node of the bare good buck reaches the loose end of its
    track by a band; the bare good BMS joins its loose ends by locked tracks of the tracks' width."""
    buck = outcome(role_copper("buck_shunt", "good"))
    assert [r.key for r in buck.plan.records if ".join" in r.key] == ["role.switch_node.SW.F.Cu.join0"]
    built = role_copper("bms", "good")
    done = outcome(built)
    assert done.plan.tracks and all(t.locked for t in done.plan.tracks)
    held = board(built)
    assert held.design.board is not None
    written = {(t.start, t.end, t.width, t.layer) for t in held.design.board.tracks if t.locked}
    assert {(t.start, t.end, t.width, t.layer) for t in done.plan.tracks} <= written
