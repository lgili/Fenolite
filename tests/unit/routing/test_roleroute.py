# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role mode of the octilinear router (change c0244; capability routing, "Role routes in a routing job"
and the requirements after it; ``docs/routing.md``, "Role mode"), on authored benches built like the
reference boards of the net roles.

The Kelvin bench: a 2512 shunt ``R1`` turned 90° at (8, 8) mm, its sense pads one above the other, and the
amplifier ``U1`` turned 90° at (28, 20) mm, its inputs one above the other, so that the pair leaves the shunt
and enters the amplifier sideways. The gate bench: two 0603 parts standing for the switch (``R5``: gate,
source) and the driver (``R6``: drive, return), declared as one gate loop. Coordinates in the scripts are
millimetres in the frame of ``place()``; the board frame adds 100 mm on each axis.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROLES_TESTS = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))

from _critical import bench, board, route_job  # noqa: E402
from _roleboards import Built  # noqa: E402

from fenolite.core.coords import Point  # noqa: E402
from fenolite.geometry import Thick, thick_closer_than, thick_touch  # noqa: E402
from fenolite.model.board import Track  # noqa: E402
from fenolite.roles.kelvin import offset  # noqa: E402
from fenolite.routing.codes import ISSUE_CODES  # noqa: E402
from fenolite.routing.octilinear import shapes  # noqa: E402
from fenolite.routing.protocol import RoleOutcome, RoutingResult  # noqa: E402
from fenolite.routing.roleroute import corridor_rings, role_options  # noqa: E402

ROLE_CODES = {
    "route.role-unrouted": "warning",
    "route.role-refused": "warning",
    "route.role-unconfirmed": "info",
    "route.role-kept": "info",
    "route.role-placement": "info",
    "route.role-none": "info",
}
MM = 1_000_000
OFF = 100 * MM
"""The board frame's offset from the frame of ``place()``."""


def at(x: float, y: float) -> Point:
    """A point of the scripts' frame (millimetres) in the board frame."""
    return Point(OFF + round(x * MM), OFF + round(y * MM))


KELVIN = """
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("{name}")
design.board(mm(40), mm(30))
r1 = Part("R1", "Fenolite:Resistor", footprint="Roles:Roles_Shunt_2512", value="5m")
u1 = Part("U1", "Roles:Roles_Sense_Amplifier", footprint="Fenolite:SOT23_5", value="AMP")
j9 = Part("J9", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="SW")
design.add(r1, u1, j9)
va, vb, sw = Net("VA"), Net("VB"), Net("SW")
connect(va, r1[1], u1["IN+"])
connect(vb, r1[2], u1["IN-"])
connect(sw, j9[1], j9[2])
design.net_role(va, "power")
design.net_role(vb, "power")
design.net_role(sw, "switch_node")
design.kelvin("kelvin_R1", (r1.pad(1), r1.pad(2)), (u1.pad(3), u1.pad(4)))
r1.place(mm(8), mm(8), rot=90)  # VA at (8, 10.9), VB at (8, 5.1)
u1.place(mm(28), mm(20), rot=90{side})  # IN+ (VA) below IN- (VB)
j9.place(mm(30), mm(26))


def box(net, name, x0, y0, x1, y1, layer):
    ring = tuple((mm(str(x)), mm(str(y))) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    design.zone(net, layers=(layer,), name=name, outline=ring, clearance=mm("0.3"), connection="solid")


{extra}
"""

GATE = """
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("{name}")
design.board(mm(40), mm(30))
r5 = Part("R5", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="SWITCH")
r6 = Part("R6", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="DRIVER")
j9 = Part("J9", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="FENCE")
design.add(r5, r6, j9)
gh, sw, fence = Net("GH"), Net("SW"), Net("FENCE")
connect(gh, r5[1], r6[1])
connect(sw, r5[2], r6[2])
connect(fence, j9[1], j9[2])
design.net_role(gh, "gate")
design.net_role(sw, "{sw}")
design.gate_loop("gate_R5", drive=r6.pad(1), gate=r5.pad(1), source=r5.pad(2), ret=r6.pad(2))
r5.place(mm(10), mm(20))  # gate at (9.2, 20), source at (10.8, 20)
r6.place(mm(25), mm(10), rot=270)  # drive at (25, 9.2), return at (25, 10.8)
j9.place(mm(30), mm(26))
w = mm("0.25")


def p(x, y):
    return (mm(str(x)), mm(str(y)))


# the drive, drawn: up from the gate, then right to the driver
design.track("gh", r5.pad(1), p(9.2, 9.2), r6.pad(1), width=w)
{extra}
"""

FENCES = """
a = (p(10.0, 18.6), p(13.4, 18.6), p(13.4, 21.4), p(10.0, 21.4), p(10.0, 18.6))
b = (p(23.6, 10.0), p(26.4, 10.0), p(26.4, 13.4), p(23.6, 13.4), p(23.6, 10.0))
design.track("ring_a", *a, width=w, net=fence)
design.track("ring_b", *b, width=w, net=fence)
"""


@pytest.fixture(scope="module")
def benches(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., Built]:
    made: dict[tuple[str, str, str, str], Built] = {}

    def get(kind: str, extra: str = "", side: str = "", sw: str = "switch_node") -> Built:
        key = (kind, extra, side, sw)
        if key not in made:
            name = f"{kind}_{len(made)}"
            text = (KELVIN if kind == "kelvin" else GATE).format(name=name, extra=extra, side=side, sw=sw)
            made[key] = bench(tmp_path_factory.mktemp(name), name, text)
        return made[key]

    return get


def outcomes(result: RoutingResult) -> dict[str, RoleOutcome]:
    return {item.key: item for item in result.roles}


def net_tracks(built: Built, result: RoutingResult, net: str) -> list[Track]:
    design, _ = board(built)
    ids = {item.id for item in design.circuit.nets if item.name == net}
    return [track for track in result.tracks if track.net_id in ids]


def test_role_codes() -> None:
    """Scenario "Codes explained" of "Role route codes" (the codes' part; ``test_explain_cmd`` checks the
    entries and the documented rows)."""
    assert {code: ISSUE_CODES[code] for code in ROLE_CODES} == ROLE_CODES


def test_options() -> None:
    issues: list[object] = []
    given = {"z-shapes": "off", "kelvin-vias": "2", "keep-away": "1.5mm", "hot-vias": "1"}
    found = role_options(given, issues)  # type: ignore[arg-type]
    assert (found.z_shapes, found.kelvin_vias, found.keep_away) == (False, 2, 1_500_000)
    assert found.max_length is None
    assert [getattr(item, "where", "") for item in issues] == ["hot-vias"]


def test_entry_on_the_inner_half(benches: Callable[..., Built]) -> None:
    """Scenario "Entry on the inner half": each branch ends inside its sense pad, ``t > 0`` toward the other
    sense pad, and the pair is locked."""
    built = benches("kelvin")
    result = route_job(built)
    assert {o.status for o in result.roles} == {"routed"} and {o.form for o in result.roles} == {"pair"}
    assert result.tracks and all(track.locked for track in result.tracks)
    _, pads = board(built)
    records = {f"{p.ref}-{p.number}": p for p in pads}
    for net, mine, other in (("VA", "R1-1", "R1-2"), ("VB", "R1-2", "R1-1")):
        ends = [point for track in net_tracks(built, result, net) for point in (track.start, track.end)]
        pad = records[mine]
        inside = [
            point
            for point in ends
            if abs(point.x - pad.position.x) <= 1_700_000 and abs(point.y - pad.position.y) <= 900_000
        ]
        assert inside, net
        t = offset(inside[0], pad.position, records[other].position)
        assert t > 0, (net, t)


def test_tiers(benches: Callable[..., Built]) -> None:
    """Scenario "Kelvin pair after the gate return": a gate loop across the pair's shortest path is routed
    first (tier 0) and straight, and the pair (tier 1) keeps clear of it."""
    extra = """
r5 = Part("R5", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="SWITCH")
r6 = Part("R6", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="DRIVER")
design.add(r5, r6)
gh, sws = Net("GH"), Net("SWS")
connect(gh, r5[1], r6[1])
connect(sws, r5[2], r6[2])
design.net_role(gh, "gate")
design.net_role(sws, "switch_node")
design.gate_loop("gate_R5", drive=r6.pad(1), gate=r5.pad(1), source=r5.pad(2), ret=r6.pad(2))
r5.place(mm(12), mm(13), rot=270)
r6.place(mm(18), mm(13), rot=270)
"""
    built = benches("kelvin", extra)
    result = route_job(built)
    found = outcomes(result)
    ret = found["gate_R5:gate-return:R5-2:R6-2"]
    assert ret.status == "routed" and len(ret.runs) == 1 and len(ret.runs[0][2]) == 2  # straight
    assert {o.status for o in result.roles} == {"routed"}
    ids = {n.id for n in board(built)[0].circuit.nets if n.name in ("GH", "SWS")}
    gate = [t for t in result.tracks if t.net_id in ids]
    pair = [t for t in result.tracks if t not in gate]
    for one in pair:
        for other in gate:
            if one.layer == other.layer:
                assert not thick_touch(
                    Thick((one.start, one.end), one.width), Thick((other.start, other.end), other.width)
                )


def test_isolated(benches: Callable[..., Built]) -> None:
    """Scenario "A sense branch beside its own pour": the straight shapes of the pair cross the outline of a
    zone of ``VB``; the placed ``VB`` branch keeps clear of that outline."""
    extra = 'box(vb, "VB_POUR", 12, 11, 24, 17, "F.Cu")'
    built = benches("kelvin", extra)
    result = route_job(built)
    assert {o.status for o in result.roles} == {"routed"}
    outline = Thick(tuple(at(x, y) for x, y in ((12, 11), (24, 11), (24, 17), (12, 17))), 0, True)
    for track in net_tracks(built, result, "VB"):
        assert not thick_closer_than(Thick((track.start, track.end), track.width), outline, 2_000)


def test_keepaway(benches: Callable[..., Built]) -> None:
    """Scenario "A pair over a switch-node pour", ``H-G-CRIT-KEEPAWAY``: with ``z-shapes=off`` every shape
    runs over the switch-node zone on ``B.Cu`` (``near-switching``); with the Z shapes the pair passes
    clear."""
    extra = 'box(sw, "SW_B", 12, 11, 24, 17, "B.Cu")'
    built = benches("kelvin", extra)
    off = route_job(built, options={"z-shapes": "off"})
    assert {(o.status, o.reason) for o in off.roles} == {("unrouted", "near-switching")}
    assert not off.tracks and any("SW_B" in b for o in off.roles for b in o.blockers)
    on = route_job(built)
    assert {o.status for o in on.roles} == {"routed"}
    outline = Thick(tuple(at(x, y) for x, y in ((12, 11), (24, 11), (24, 17), (12, 17))), 0, True)
    for track in on.tracks:
        assert not thick_touch(Thick((track.start, track.end), track.width), outline)
    assert max(len(o.runs[0][2]) for o in on.roles) >= 4  # a Z shape, with its entries


def test_smaller_loop(benches: Callable[..., Built]) -> None:
    """Scenario "The smaller loop wins": of the return's clear shapes, the L that runs inside the drive's L
    encloses the least and is kept, where c0228 would keep the first shape that passes."""
    built = benches("gate")
    result = route_job(built)
    (found,) = result.roles
    assert found.status == "routed" and found.form == "side-by-side" and found.vias == 0
    assert found.runs[0][2] == (at(10.8, 20), at(10.8, 10.8), at(25, 10.8))
    assert shapes(at(10.8, 20), at(25, 10.8))[0] != found.runs[0][2]


def test_gate_stacked(benches: Callable[..., Built]) -> None:
    """Scenario "Stacked when the side is blocked": rings of another net around the source and the return pad
    leave no shape on ``F.Cu``, so the return runs under the drive on ``B.Cu`` with one via at each end; with
    ``gate-vias=0`` it stays unrouted."""
    built = benches("gate", FENCES)
    result = route_job(built)
    (found,) = result.roles
    assert found.status == "routed" and found.form == "stacked" and found.vias == 2
    assert len(result.vias) == 2 and all(via.locked for via in result.vias)
    assert {layer for layer, _, _ in found.runs} == {"F.Cu", "B.Cu"}
    blocked = route_job(built, options={"gate-vias": "0"})
    assert [(o.status, o.reason) for o in blocked.roles] == [("unrouted", "no-room")]


def test_vias(benches: Callable[..., Built]) -> None:
    """Scenario "No common layer": the amplifier on ``B.Cu`` and the shunt on ``F.Cu`` give ``no-layer``;
    ``kelvin-vias=2`` places one via per branch."""
    built = benches("kelvin", "", ', side="bottom"')
    plain = route_job(built)
    assert {(o.status, o.reason) for o in plain.roles} == {("unrouted", "no-layer")}
    allowed = route_job(built, options={"kelvin-vias": "2"})
    assert {o.status for o in allowed.roles} == {"routed"}
    assert sorted(o.vias for o in allowed.roles) == [1, 1] and len(allowed.vias) == 2


def test_refused(benches: Callable[..., Built]) -> None:
    """Scenario "A worse group is removed": a role check that finds a new ``roles.near-switching`` on the
    pair once it is routed removes both branches."""
    built = benches("kelvin")

    def check(design: object) -> tuple[tuple[str, str, str, int | None], ...]:
        board_of = getattr(design, "board", None)
        routed = any(track.locked for track in getattr(board_of, "tracks", ()))
        return (("roles.near-switching", "kelvin_R1", "warning", None),) if routed else ()

    result = route_job(built, role_check=check)
    assert not result.tracks
    assert {(o.status, o.reason) for o in result.roles} == {("refused", "role-check")}
    assert all("roles.near-switching" in o.detail for o in result.roles)


def test_corridor_rings() -> None:
    """A corridor is the band of half width ``grow`` around the polyline, closed flat at its ends."""
    (ring,) = corridor_rings((Point(0, 0), Point(10, 0), Point(10, 10)), 2)
    assert ring == (Point(0, 2), Point(8, 2), Point(8, 10), Point(12, 10), Point(12, -2), Point(0, -2))


def test_plane_return(benches: Callable[..., Built]) -> None:
    """A return of a ground net with a zone of its net under the whole drive on the adjacent layer is not
    routed: the plane carries it (``plane-return``)."""
    extra = """
ring = tuple((mm(str(x)), mm(str(y))) for x, y in ((1, 1), (39, 1), (39, 23), (1, 23)))
design.zone(sw, layers=("B.Cu",), name="RET", outline=ring, clearance=mm("0.3"), connection="solid")
"""
    built = benches("gate", extra, sw="ground")
    result = route_job(built)
    (found,) = result.roles
    assert (found.status, found.form) == ("plane-return", "plane-return") and not result.tracks
