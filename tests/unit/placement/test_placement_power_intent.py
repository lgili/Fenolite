# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.model.rules import GateLoop, HotLoop, KelvinPair, RoleSet
from fenolite.placement.power_intent import (
    BootstrapBinding,
    IsolationBinding,
    power_objectives,
    projected_loop_area2,
)
from fenolite.placement.topology import PadIdentity


def pad(ref, number, net=None):
    return BoardPad(ref, ref, f"/{ref}", number, number, "smd", Point(0, 0), 0, "top", ("F.Cu",), net, net)


def test_overlapping_role_groups_keep_drive_return_and_force_pad_identities():
    roles = RoleSet(
        loops=(HotLoop("switching", ("Q-2", "Q-3", "C-1", "C-2")),),
        gates=(GateLoop("drive", "D-1", "Q-1", "Q-3", "D-2", ("R-1", "R-2")),),
        kelvins=(KelvinPair("sense", ("S-1", "S-2"), ("D-3", "D-4"), ("S-3", "S-4")),),
    )
    pads = tuple(
        pad(ref, n)
        for ref, numbers in (("Q", "123"), ("C", "12"), ("D", "1234"), ("R", "12"), ("S", "1234"))
        for n in numbers
    )
    gate, hot, kelvin = power_objectives(roles, pads)
    assert gate.legs == (
        (PadIdentity("D", "1"), PadIdentity("R", "1")),
        (PadIdentity("R", "2"), PadIdentity("Q", "1")),
        (PadIdentity("Q", "3"), PadIdentity("D", "2")),
    )
    assert hot.loop[1] == gate.legs[-1][0]
    assert kelvin.force_pads == (PadIdentity("S", "3"), PadIdentity("S", "4"))
    assert kelvin.legs[-1] == (PadIdentity("S", "2"), PadIdentity("D", "4"))
    duplicated = replace(pad("Q", "3"), footprint_id="another-q", path="/another/Q")
    result = power_objectives(roles, (*pads, duplicated))
    assert result[0].unresolved == result[1].unresolved == ("Q-3",)


def test_inferred_groups_are_inactive_and_invalid_loop_sketch_is_unknown():
    names = ("A-1", "B-1", "C-1", "D-1")
    roles = RoleSet(
        loops=(HotLoop("active", names), HotLoop("suggestion", names, origin="inferred", confidence="high"))
    )
    pads = tuple(pad(ref, "1") for ref in "ABCD")
    (objective,) = power_objectives(roles, pads)
    square = dict(zip(objective.loop, (Point(0, 0), Point(3, 0), Point(3, 2), Point(0, 2)), strict=True))
    assert projected_loop_area2(objective, square) == 12
    square[objective.loop[1]] = Point(3, 3)
    square[objective.loop[2]] = Point(2, 0)
    assert projected_loop_area2(objective, square) is None
    assert projected_loop_area2(objective, {}) is None


def test_bootstrap_and_isolation_require_explicit_endpoints_and_rules():
    a, b, c, d = (PadIdentity(ref, n) for ref, n in (("C", "1"), ("U", "1"), ("C", "2"), ("U", "2")))
    pads = (pad("C", "1", "boot"), pad("U", "1", "boot"), pad("C", "2", "sw"), pad("U", "2", "sw"))
    boot = BootstrapBinding("supply", (a, b), (c, d), "authored")
    barrier = IsolationBinding("barrier", (a, d), "boundary-rule", "authored")
    first, second = power_objectives(RoleSet(), pads, bootstrap=(boot,), isolation=(barrier,))
    assert first.loop == (a, b, d, c)
    assert second.unresolved == ("missing_isolation_rule",)
    bad_return = (*pads[:-1], replace(pads[-1], net_id="gnd"))
    first, second = power_objectives(
        RoleSet(),
        bad_return,
        bootstrap=(boot,),
        isolation=(barrier,),
        isolation_rules=frozenset({"boundary-rule"}),
    )
    assert first.unresolved == ("invalid_bootstrap_binding",)
    assert second.isolation_rule == "boundary-rule" and second.legs == ((a, d),)
