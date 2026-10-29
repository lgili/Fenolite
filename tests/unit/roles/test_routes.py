# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The critical route plan and the critical copper (change c0244; capability net-roles, "Critical route plan"
and "Critical copper for later phases"; ``docs/roles.md``, "Critical routes")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from _critical import confirmed_copy, plan, roles_of, routed, unconfirmed
from _roleboards import Built, read

from fenolite.core.coords import Point
from fenolite.model.board import Keepout, Track, Via
from fenolite.model.circuit import Net
from fenolite.model.design import Design
from fenolite.model.rules import GateLoop, KelvinPair, RoleSet
from fenolite.roles.kelvin import offset
from fenolite.roles.routes import corridor_name, critical_copper, entry_point, safe_net


def test_routes_of_the_half_bridge(reference: Callable[..., Built]) -> None:
    """Scenario "Routes of the half-bridge"."""
    found = plan(reference("half_bridge", "open"))
    groups = {group.name: group for group in found.groups}
    assert [(g.name, g.kind, g.status) for g in found.groups] == [
        ("gate_Q1", "gate_loop", "planned"),
        ("gate_Q2", "gate_loop", "planned"),
        ("kelvin_R1", "kelvin_pair", "planned"),
    ]
    routes = {route.key: route for route in found.routes}
    (ret,) = [routes[key] for key in groups["gate_Q1"].routes]
    assert (ret.kind, ret.a.label, ret.b.label, ret.net) == ("gate-return", "Q1-2", "U2-6", "SW")
    assert ret.isolated and ret.vias == 2 and ret.layers == ("F.Cu", "In1.Cu") and ret.width == 250_000
    assert ret.aggressors == () and ret.partner == ""
    (out,) = [routes[key] for key in groups["gate_Q2"].routes]
    assert (out.kind, out.a.label, out.b.label, out.net) == ("gate-out", "U2-5", "Q2-1", "GL")
    assert not out.isolated and out.vias == 0 and out.layers == ("F.Cu",)
    assert len(out.loop) > 4  # the return's copper under it, from Q2-2 to U2-4
    pair = [routes[key] for key in groups["kelvin_R1"].routes]
    assert [(r.a.label, r.b.label, r.net) for r in pair] == [("R1-1", "U3-3", "SRC"), ("R1-2", "U3-4", "GND")]
    assert pair[0].partner == pair[1].key and pair[1].partner == pair[0].key
    assert all(r.isolated and r.aggressors == ("SW",) and r.keep_away == 1_000_000 for r in pair)
    assert all(r.width == 200_000 and r.gap == 300_000 and r.tier == 1 for r in pair)
    assert not [route for route in found.routes if route.group.startswith("hot")]


def test_entry_on_the_inner_half(reference: Callable[..., Built]) -> None:
    """Design decision 5: each Kelvin route of the open buck ends inside its sense pad with ``t > 0``."""
    built = reference("buck_shunt", "open")
    _, pads = read(built)
    records = {f"{p.ref}-{p.number}": p for p in pads}
    found = plan(built)
    kelvin = [route for route in found.routes if route.kind == "kelvin"]
    assert len(kelvin) == 2
    for route in kelvin:
        other = records["R12-2" if route.a.label == "R12-1" else "R12-1"]
        mine = records[route.a.label]
        t = offset(route.a.at, mine.position, other.position)
        assert 0 < t <= 900_000 - 100_000 - 2_000, (route.key, t)
    pad = records["R12-1"]
    assert entry_point(pad, records["R12-2"].position, 200_000) == Point(
        pad.position.x + 798_000, pad.position.y
    )


def test_complete_and_skipped(reference: Callable[..., Built]) -> None:
    """A good board plans no route; unconfirmed groups are skipped; a hot loop is phase 1's."""
    good = plan(reference("buck_shunt", "good"))
    assert {(g.name, g.status) for g in good.groups} == {
        ("gate_Q1", "complete"),
        ("gate_Q2", "complete"),
        ("kelvin_R12", "complete"),
    }
    assert good.routes == ()
    built = reference("buck_shunt", "open")
    skipped = plan(built, roles=unconfirmed(roles_of(built)))
    assert {(g.name, g.status, g.reason) for g in skipped.groups} == {
        ("gate_Q1", "skipped", "unconfirmed"),
        ("gate_Q2", "skipped", "unconfirmed"),
        ("kelvin_R12", "skipped", "unconfirmed"),
    }
    named = plan(built, groups=("hot_SW", "kelvin_R12"))
    assert [(g.name, g.kind, g.status, g.reason) for g in named.groups] == [
        ("hot_SW", "hot_loop", "skipped", "phase-1"),
        ("kelvin_R12", "kelvin_pair", "planned", ""),
    ]


def test_missing_pads(reference: Callable[..., Built]) -> None:
    built = reference("bms", "open")
    roles = roles_of(built)
    ghost = RoleSet(
        nets=roles.nets,
        gates=(GateLoop("gate_X", "U9-1", "Q9-1", "Q9-2", "U9-2", origin="confirmed"),),
        kelvins=(KelvinPair("kelvin_X", ("R9-1", "R9-2"), ("U9-3", "U9-4"), origin="declared"),),
    )
    found = plan(built, roles=ghost)
    assert {(g.name, g.status, g.reason) for g in found.groups} == {
        ("gate_X", "unrouted", "pads"),
        ("kelvin_X", "unrouted", "pads"),
    }


def test_corridor_names() -> None:
    assert corridor_name("kelvin_R1", "SNS_P") == "role.corridor.kelvin_R1.SNS_P"
    assert safe_net("/top/V+ (a)") == "_top_V+__a_"


def test_critical_copper_on_a_drawn_board() -> None:
    """``critical_copper`` reads the corridors by name and the locked copper of their net inside them."""
    net = Net(id="net_a", name="VA")
    other = Net(id="net_b", name="VB")
    ring = (Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 2_000_000), Point(0, 2_000_000))
    inside = Track(id="trk_in", start=Point(1_000_000, 1_000_000), end=Point(9_000_000, 1_000_000),
                   width=200_000, layer="F.Cu", net_id="net_a", locked=True)  # fmt: skip
    loose = Track(id="trk_loose", start=Point(1_000_000, 1_000_000), end=Point(2_000_000, 1_000_000),
                  width=200_000, layer="F.Cu", net_id="net_a")  # fmt: skip
    outside = Track(id="trk_out", start=Point(1_000_000, 5_000_000), end=Point(9_000_000, 5_000_000),
                    width=200_000, layer="F.Cu", net_id="net_a", locked=True)  # fmt: skip
    foreign = Track(id="trk_b", start=Point(1_000_000, 1_500_000), end=Point(9_000_000, 1_500_000),
                    width=200_000, layer="F.Cu", net_id="net_b", locked=True)  # fmt: skip
    via = Via(id="via_in", position=Point(5_000_000, 1_000_000), diameter=600_000, drill=300_000,
              layers=("F.Cu", "B.Cu"), net_id="net_a", locked=True)  # fmt: skip
    area = Keepout(
        id="rul_c", outline=ring, layers=("F.Cu",), no_copper_pour=True, name=corridor_name("k", "VA")
    )
    design = Design.new("copper", seed=1)
    assert design.board is not None
    design = replace(
        design,
        circuit=replace(design.circuit, nets=(net, other)),
        board=replace(design.board, tracks=(inside, loose, outside, foreign), vias=(via,), keepouts=(area,)),
    )
    roles = RoleSet(kelvins=(KelvinPair("k", ("R1-1", "R1-2"), ("U1-1", "U1-2")),), gates=())
    found = critical_copper(design, roles)
    group = found.group("k")
    assert group is not None and group.corridors == ("rul_c",) and group.items == ("trk_in", "via_in")


def test_critical_copper_of_a_routed_group(reference: Callable[..., Built], tmp_path: Path) -> None:
    """Scenario "Copper and corridors of a routed group": on the routed open buck read back from its KiCad
    board, ``critical_copper`` gives the Kelvin pair its two corridors and every locked track of its
    branches, and the gate loops no copper written by role mode."""
    built = confirmed_copy(reference("buck_shunt", "open"), tmp_path)
    routed(built.board)
    design, _ = read(built)
    assert design.board is not None
    found = critical_copper(design, roles_of(built))
    kelvin = found.group("kelvin_R12")
    assert kelvin is not None and len(kelvin.corridors) == 2
    locked = sorted(track.id for track in design.board.tracks if track.locked)
    assert locked and list(kelvin.items) == locked
    assert {(g.group, g.items, g.corridors) for g in found.groups if g.kind == "gate_loop"} == {
        ("gate_Q1", (), ()),
        ("gate_Q2", (), ()),
    }
