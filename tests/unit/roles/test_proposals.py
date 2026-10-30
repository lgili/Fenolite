# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The subjects of the proposals of phase 4 (change c0280; capability net-roles, "Leftover opens of role
copper are proposed" and "Role-net candidates are labelled"; ``docs/roles.md``, "Proposals after the
critical routes")."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from _critical import board
from _proposals import subject_bench
from _roleboards import Built, judge

from fenolite.core.coords import Point
from fenolite.roles.proposals import Attach, OpenGroup, SubjectPlan, subjects


def plan_of(built: Built, groups: tuple[OpenGroup, ...] = ()) -> SubjectPlan:
    design, pads = board(built)
    roles = judge(built, check=False).resolved.roles
    return subjects(
        design, pads, roles=roles, groups=groups, widths={n.name: 250_000 for n in design.circuit.nets}
    )


@pytest.fixture(scope="module")
def bench_board(tmp_path_factory: pytest.TempPathFactory) -> Built:
    return subject_bench(tmp_path_factory.mktemp("subjects"))


def test_each_kind_on_the_bench(bench_board: Built) -> None:
    """One subject per open connection, of the first kind that fits, sorted by kind then key; the proposal
    ids do not change between two runs."""
    plan = plan_of(bench_board)
    assert [(s.kind, s.key) for s in plan.subjects] == [
        ("fanout", "fanout:GND:R3-2"),
        ("join", "join:PWR:R5-1~role.power.PWR.F.Cu"),
        ("role-net", "role-net:VS:R6-1~R7-1"),
        ("connection", "connection:SIG:R1-1~R2-1"),
    ]
    assert plan.open == 4 and plan.fill == "simulated"
    fanout, join, role_net, connection = plan.subjects
    assert (fanout.a.kind, fanout.a.name, fanout.b.kind, fanout.b.layers) == (
        "pad",
        "R3-2",
        "zone",
        ("B.Cu",),
    )
    assert (join.b.kind, join.b.name, join.b.layers) == ("zone", "role.power.PWR.F.Cu", ("F.Cu",))
    assert join.b.at.x < join.a.at.x and join.b.at.x <= 130_000_000 - 125_000 - 300_000
    assert role_net.inferred == "power" and connection.inferred == ""
    again = plan_of(bench_board)
    assert [s.proposal for s in again.subjects] == [s.proposal for s in plan.subjects]
    assert all(s.proposal.startswith("p-") and len(s.proposal) == 18 for s in plan.subjects)


def test_group_subjects(bench_board: Built) -> None:
    """A group that phase 2 left ``unrouted`` or ``refused`` is one ``group`` subject; a missing pad gives the
    reason ``pads``; a ``complete`` group none."""
    a = Attach("pad", "VS", Point(106_800_000, 124_000_000), ("F.Cu",), "R6-1")
    b = Attach("pad", "VS", Point(113_200_000, 124_000_000), ("F.Cu",), "R7-1")
    groups = (
        OpenGroup("gate_X", "unrouted", "no-room", (("gate_X:gate-out:R6-1:R7-1", "VS", a, b),)),
        OpenGroup("kelvin_Y", "unrouted", "pads", (("kelvin_Y:kelvin:R6-1:R7-1", "VS", a, b),)),
        OpenGroup("gate_Z", "complete", "", (("gate_Z:gate-out:R6-1:R7-1", "VS", a, b),)),
    )
    plan = plan_of(bench_board, groups)
    found = {s.key: s for s in plan.subjects if s.kind == "group"}
    assert sorted(found) == ["group:gate_X", "group:kelvin_Y"]
    assert (
        found["group:gate_X"].routes == ("gate_X:gate-out:R6-1:R7-1",) and found["group:gate_X"].reason == ""
    )
    assert found["group:kelvin_Y"].reason == "pads"
    kinds = [s.kind for s in plan.subjects]
    assert kinds.index("group") > kinds.index("role-net") and kinds[-1] == "connection"


LEFTOVERS = {
    ("buck_shunt", "bad"): ["fanout:GND:C3-2", "join:VOUT:C3-1~role.power.VOUT.F.Cu"],
    ("half_bridge", "good"): ["join:SRC:Q2-2~role.power.SRC.F.Cu", "join:SW:Q1-2~role.switch_node.SW.F.Cu"],
    ("bms", "good"): ["role-net:FET_S:Q1-2~Q1-3", "role-net:FET_S:Q2-2~Q2-3"],
}


@pytest.mark.parametrize(("name", "variant"), sorted(LEFTOVERS))
def test_leftover_subjects_of_role_copper(
    role_copper: Callable[..., Built], name: str, variant: str, tmp_path: Path
) -> None:
    """The opens that phase 1 leaves (task 0.1), as subjects: the buck's ``C3-2`` a fan-out, the half-bridge's
    Kelvin-source pads joins into their pours, the bms ``FET_S`` two role-net subjects."""
    plan = plan_of(role_copper(name, variant))
    assert [s.key for s in plan.subjects] == LEFTOVERS[name, variant]
