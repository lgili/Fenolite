# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local wires preserve endpoints, avoid obstacles and fall back deterministically."""

from dataclasses import replace

from fenolite.schematic.composition import GRID, Box, CompositionPlan, Pin, Placement, Unit, Visible
from fenolite.schematic.wires import paths, route_local


def plan():
    a = Unit(
        "U1#1",
        "U1",
        1,
        "root",
        "U1",
        "",
        Box(0, 0, GRID, GRID),
        (Pin("1", "", (2 * GRID, 0), (GRID, 0), 0, "SIGNAL"),),
    )
    b = replace(a, key="U2#1", component="U2", pins=(Pin("1", "", (-GRID, 0), (0, 0), 2, "SIGNAL"),))
    placements = (
        Placement(
            a,
            (GRID, 5 * GRID),
            0,
            Box(0, 0, 4 * GRID, 10 * GRID),
            (Visible(a.key, "body", Box(GRID, 5 * GRID, 2 * GRID, 6 * GRID)),),
            "core",
        ),
        Placement(
            b,
            (10 * GRID, 5 * GRID),
            0,
            Box(8 * GRID, 0, 14 * GRID, 10 * GRID),
            (Visible(b.key, "body", Box(10 * GRID, 5 * GRID, 11 * GRID, 6 * GRID)),),
            "core",
        ),
    )
    return CompositionPlan("root", "left-to-right", Box(0, 0, 20 * GRID, 20 * GRID), (), (), placements)


def test_aligned_connection_and_candidate_determinism():
    result = route_local(plan())
    assert len(result.wires) == 1 and len(result.wires[0].points) == 2
    assert result.wires[0].net == "SIGNAL" and result.issues == ()
    assert paths((0, 0), (2 * GRID, 3 * GRID)) == paths((0, 0), (2 * GRID, 3 * GRID))


def test_obstacle_and_exhausted_budget_retain_labels():
    p = replace(plan(), reserved=(Box(4 * GRID, 0, 8 * GRID, 20 * GRID),))
    blocked = route_local(p)
    assert blocked.wires == () and blocked.issues[0].code == "composition.label-fallback"
    assert blocked.issues[0].where and blocked.issues[0].hint
    assert route_local(plan(), budget=0).issues


def test_foreign_pin_prevents_accidental_junction():
    p = plan()
    foreign = replace(
        p.placements[0],
        unit=replace(
            p.placements[0].unit,
            key="R3#1",
            component="R3",
            pins=(Pin("1", "", (5 * GRID, 0), (5 * GRID, 0), 0, "OTHER"),),
        ),
        visible=(),
    )
    p = replace(p, placements=(*p.placements, foreign))
    result = route_local(p)
    assert not result.wires or len(result.wires[0].points) > 2
