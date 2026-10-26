# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local topology order, compatible pin alignment and nearby two-pin attachments."""

from __future__ import annotations

from dataclasses import dataclass, replace

from fenolite.schematic.bounds import unit_bounds, visible_envelopes
from fenolite.schematic.composition import (
    GAP,
    GRID,
    Attachment,
    Block,
    Box,
    Flow,
    Placement,
    Unit,
    rotate,
    union,
    up,
)


@dataclass(frozen=True)
class BlockPlan:
    block: Block
    placements: tuple[Placement, ...]
    bounds: Box
    attachments: tuple[Attachment, ...]


def translated(placement: Placement, x: int, y: int) -> Placement:
    return replace(
        placement,
        origin=(placement.origin[0] + x, placement.origin[1] + y),
        bounds=placement.bounds.move(x, y),
        visible=tuple(replace(v, box=v.box.move(x, y)) for v in placement.visible),
    )


def placed(unit: Unit, x: int, y: int, quarter: int, block: str) -> Placement:
    return Placement(
        unit,
        (x, y),
        quarter * 90_000_000,
        unit_bounds(unit, quarter).move(x, y),
        tuple(replace(v, box=v.box.move(x, y)) for v in visible_envelopes(unit, quarter)),
        block,
    )


def shared_nets(a: Unit, b: Unit) -> tuple[str, ...]:
    return tuple(
        sorted(
            {p.net for p in a.pins if p.net is not None and not p.power}
            & {p.net for p in b.pins if p.net is not None and not p.power}
        )
    )


def compose_block(block: Block, flow: Flow) -> BlockPlan:
    """Allocate a main path and align branches with anchor pins, using collision-free cell envelopes."""
    block = replace(block, units=tuple(sorted(block.units, key=lambda u: u.key)))
    pending = {u.key: u for u in block.units}
    if not pending:
        return BlockPlan(block, (), Box(0, 0, 0, 0), ())
    anchor = min(
        pending.values(),
        key=lambda u: (u.component != block.anchor if block.anchor else False, -len(u.pins), u.key),
    )
    main = [u for u in pending.values() if len(u.pins) != 2 or u is anchor]
    main = sorted(main, key=lambda u: (u is not anchor, u.key))
    branches = [u for u in pending.values() if u not in main]
    # Follow connectivity, not declaration order, for the main path; cycles terminate at visited units.
    ordered = [main.pop(0)]
    while main:
        next_unit = min(main, key=lambda u: (not bool(shared_nets(ordered[-1], u)), u.key))
        ordered.append(next_unit)
        main.remove(next_unit)
    found: list[Placement] = []
    attachments: list[Attachment] = []
    cursor = 0
    for unit in ordered:
        bounds = unit_bounds(unit)
        x, y = (
            (cursor - bounds.x0, -bounds.y0) if flow == "left-to-right" else (-bounds.x0, cursor - bounds.y0)
        )
        if found:
            before = found[-1]
            nets = shared_nets(before.unit, unit)
            if nets:
                net = nets[0]
                old = next(p for p in before.unit.pins if p.net == net)
                new = next(p for p in unit.pins if p.net == net)
                if flow == "left-to-right" and (old.at[1] - new.at[1]) % GRID == 0:
                    y = before.origin[1] + old.at[1] - new.at[1]
                elif flow == "top-to-bottom" and (old.at[0] - new.at[0]) % GRID == 0:
                    x = before.origin[0] + old.at[0] - new.at[0]
        item = placed(unit, x, y, 0, block.key)
        found.append(item)
        cursor = (item.bounds.x1 if flow == "left-to-right" else item.bounds.y1) + GAP
    for branch in sorted(branches, key=lambda u: u.key):
        candidates = [(target, net) for target in found for net in shared_nets(target.unit, branch)]
        candidates.sort(
            key=lambda pair: (
                pair[0].unit.component != block.anchor,
                -len(pair[0].unit.pins),
                pair[0].unit.key,
                pair[1],
            )
        )
        if not candidates:
            bounds = unit_bounds(branch)
            envelope = union(tuple(p.bounds for p in found))
            x, y = (envelope.x1 + GAP - bounds.x0, envelope.y0 - bounds.y0)
            found.append(placed(branch, x, y, 0, block.key))
            continue
        target, net = candidates[0]
        anchor_pin = next(p for p in target.unit.pins if p.net == net)
        branch_pin = next(p for p in branch.pins if p.net == net)
        target_quarter = target.rotation // 90_000_000
        direction = (anchor_pin.direction + target_quarter) % 4
        q = (direction + 2 - branch_pin.direction) % 4
        bounds = unit_bounds(branch, q)
        bx, by = rotate(branch_pin.at, q)
        ax, ay = rotate(anchor_pin.at, target_quarter)
        tx, ty = target.origin[0] + ax, target.origin[1] + ay
        all_bounds = union(tuple(p.bounds for p in found))
        if direction == 0:
            x, y = up(all_bounds.x1 + GAP - bounds.x0), up(ty - by)
        elif direction == 2:
            x, y = (all_bounds.x0 - GAP - bounds.x1) // GRID * GRID, up(ty - by)
        elif direction == 1:
            x, y = up(tx - bx), (all_bounds.y0 - GAP - bounds.y1) // GRID * GRID
        else:
            x, y = up(tx - bx), up(all_bounds.y1 + GAP - bounds.y0)
        found.append(placed(branch, x, y, q, block.key))
        attachments.append(
            Attachment(
                branch.key,
                target.unit.key,
                net,
                "explicit-anchor/connectivity/key tie-break"
                if len(candidates) > 1
                else "unique signal attachment",
            )
        )
    # Put block title above the entire drawing; avoid shifting text into a unit envelope.
    all_bounds = union(tuple(p.bounds for p in found))
    shift_x, shift_y = -all_bounds.x0, 3 * GRID - all_bounds.y0
    shifted = tuple(translated(p, shift_x, shift_y) for p in found)
    width = max(all_bounds.width, len(block.title) * 70 * 25_400)
    return BlockPlan(
        block, shifted, Box(0, 0, up(width), up(all_bounds.height + 3 * GRID)), tuple(attachments)
    )
