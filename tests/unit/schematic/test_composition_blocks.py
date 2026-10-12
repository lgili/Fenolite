# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local alignment and branch placement with deterministic geometry."""

from dataclasses import replace

from fenolite.schematic.blocks import compose_block
from fenolite.schematic.composition import GRID, Block, Box, Pin, Unit
from fenolite.schematic.wires import pin_point


def circuit():
    core = Unit(
        "U1#1",
        "U1",
        1,
        "root",
        "U1",
        "Core",
        Box(0, 0, 4 * GRID, 4 * GRID),
        (
            Pin("1", "", (5 * GRID, GRID), (4 * GRID, GRID), 0, "A"),
            Pin("2", "", (5 * GRID, 2 * GRID), (4 * GRID, 2 * GRID), 0, "B"),
            Pin("3", "", (-GRID, GRID), (0, GRID), 2, "IN"),
        ),
    )
    passive = Unit(
        "R1#1",
        "R1",
        1,
        "root",
        "R1",
        "1k",
        Box(0, 0, GRID, 2 * GRID),
        (Pin("1", "", (0, -GRID), (0, 0), 1, "A"), Pin("2", "", (0, 3 * GRID), (0, 2 * GRID), 3, "OUT")),
    )
    return core, passive


def test_passive_is_rotated_near_anchor_and_text_stays_horizontal():
    core, resistor = circuit()
    plan = compose_block(Block("core", "Core", (resistor, core), "U1"), "left-to-right")
    assert plan.attachments[0].anchor == core.key
    branch = next(p for p in plan.placements if p.unit.key == resistor.key)
    assert branch.rotation == 90_000_000
    assert not plan.placements[0].bounds.overlaps(branch.bounds)
    assert all(plan.bounds.contains(p.bounds) for p in plan.placements)
    assert all(v.box.height == GRID for v in branch.visible if v.kind in ("reference", "value"))


def test_staggered_branches_and_permutation():
    core, resistor = circuit()
    other = replace(
        resistor,
        key="R2#1",
        component="R2",
        ref="R2",
        pins=tuple(replace(p, net="B" if p.net == "A" else p.net) for p in resistor.pins),
    )
    block = Block("core", "Core", (core, resistor, other), "U1")
    a = compose_block(block, "left-to-right")
    b = compose_block(replace(block, units=tuple(reversed(block.units))), "left-to-right")
    assert a == b
    assert all(
        not x.bounds.overlaps(y.bounds) for i, x in enumerate(a.placements) for y in a.placements[i + 1 :]
    )


def test_vertical_flow_keeps_every_unit():
    core, passive = circuit()
    assert len(compose_block(Block("core", "Core", (core, passive)), "top-to-bottom").placements) == 2


def test_branch_chain_attaches_to_transformed_pin_of_previous_branch():
    core, first = circuit()
    second = replace(
        first,
        key="R2#1",
        component="R2",
        ref="R2",
        pins=(replace(first.pins[0], net="OUT"), replace(first.pins[1], net="NEXT")),
    )
    plan = compose_block(Block("core", "Core", (core, first, second), "U1"), "left-to-right")
    a = next(p for p in plan.placements if p.unit.key == first.key)
    b = next(p for p in plan.placements if p.unit.key == second.key)
    assert a.rotation == b.rotation == 90_000_000
    assert pin_point(a, "2")[1] == pin_point(b, "1")[1]
    assert b.bounds.x0 > a.bounds.x1
