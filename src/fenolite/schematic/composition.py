# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer presentation geometry and bounded deterministic composition (c0165)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.schematic.intent import BlockIntent, CompositionIntent, Flow

ALGORITHM = "blocks-v1"
SCHEMA = "fenolite.schematic-composition.v0"
NM_PER_MIL = 25_400
GRID = 100 * NM_PER_MIL
PIN_GRID = 10 * NM_PER_MIL
GAP = 400 * NM_PER_MIL
TEXT_HEIGHT = 100 * NM_PER_MIL
CHAR_WIDTH = 70 * NM_PER_MIL
FANOUT_LIMIT = 8
PLACEMENT_BUDGET = 10_000
WIRE_BUDGET = 64
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "composition.invalid-intent": "error",
        "composition.overflow": "error",
        "composition.overlap": "error",
        "composition.template-unverified": "error",
        "composition.transform-unsupported": "error",
        "composition.connectivity-changed": "error",
        "composition.budget-exhausted": "error",
        "composition.label-fallback": "info",
    }
)


class CompositionError(FenoliteError):
    """A hard composition constraint prevents all output writes."""

    def __init__(self, code: str, message: str, where: str, hint: str) -> None:
        super().__init__(message)
        self.issues = (Issue(code, ISSUE_CODES[code], message, where=where, hint=hint),)


def fail(code: str, message: str, where: str, hint: str) -> CompositionError:
    return CompositionError(f"composition.{code}", message, where, hint)


def up(value: int, grid: int = GRID) -> int:
    return -(-value // grid) * grid


def rotate(point: tuple[int, int], quarter: int) -> tuple[int, int]:
    """Counterclockwise quarter-turns in the sheet frame (X right, Y down)."""
    x, y = point
    return ((x, y), (y, -x), (-x, -y), (-y, x))[quarter % 4]


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("box corners are reversed")

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def move(self, x: int, y: int) -> Box:
        return Box(self.x0 + x, self.y0 + y, self.x1 + x, self.y1 + y)

    def contains(self, other: Box) -> bool:
        return self.x0 <= other.x0 <= other.x1 <= self.x1 and self.y0 <= other.y0 <= other.y1 <= self.y1

    def overlaps(self, other: Box) -> bool:
        return self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1

    def expanded(self, amount: int) -> Box:
        return Box(self.x0 - amount, self.y0 - amount, self.x1 + amount, self.y1 + amount)


def union(boxes: tuple[Box, ...]) -> Box:
    if not boxes:
        return Box(0, 0, 0, 0)
    return Box(
        min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes)
    )


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    at: tuple[int, int]
    body_at: tuple[int, int]
    direction: int
    net: str | None = None
    power: bool = False
    number_shown: bool = True
    hidden: bool = False
    power_style: str = "bar"


@dataclass(frozen=True)
class Primitive:
    kind: str
    points: tuple[tuple[int, int], ...]
    radius: int = 0
    filled: bool = False


@dataclass(frozen=True)
class Unit:
    key: str
    component: str
    part: int
    sheet: str
    ref: str
    value: str
    body: Box
    pins: tuple[Pin, ...]
    primitives: tuple[Primitive, ...] = ()


@dataclass(frozen=True)
class Visible:
    key: str
    kind: str
    box: Box


@dataclass(frozen=True)
class Placement:
    unit: Unit
    origin: tuple[int, int]
    rotation: int
    bounds: Box
    visible: tuple[Visible, ...]
    block: str


@dataclass(frozen=True)
class Block:
    key: str
    title: str
    units: tuple[Unit, ...]
    anchor: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class PlacedBlock:
    key: str
    title: str
    bounds: Box


@dataclass(frozen=True)
class Wire:
    net: str
    start: tuple[str, str]
    end: tuple[str, str]
    points: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Attachment:
    unit: str
    anchor: str
    net: str
    reason: str


@dataclass(frozen=True)
class CompositionPlan:
    sheet: str
    flow: Flow
    region: Box
    reserved: tuple[Box, ...]
    blocks: tuple[PlacedBlock, ...]
    placements: tuple[Placement, ...]
    wires: tuple[Wire, ...] = ()
    attachments: tuple[Attachment, ...] = ()
    issues: tuple[Issue, ...] = ()
    candidates: int = 0
    intent_sha256: str = ""
    connection_candidates: int = 0


__all__ = ["BlockIntent", "CompositionIntent", "CompositionPlan", "ISSUE_CODES"]


def validate_plan(plan: CompositionPlan) -> None:
    for placement in plan.placements:
        where = f"{plan.sheet}/{placement.block}/{placement.unit.key}"
        if not plan.region.contains(placement.bounds):
            raise fail("overflow", "unit envelope leaves usable paper", where, "use a larger sheet")
        if any(placement.bounds.overlaps(r) for r in plan.reserved):
            raise fail("overlap", "unit intersects reserved sheet content", where, "move or split its block")
    for index, placement in enumerate(plan.placements):
        for other in plan.placements[index + 1 :]:
            if placement.bounds.overlaps(other.bounds):
                raise fail(
                    "overlap",
                    f"unit intersects {other.unit.key}",
                    f"{plan.sheet}/{placement.block}/{placement.unit.key}",
                    "separate the affected units",
                )


def compose_sheet(
    units: tuple[Unit, ...],
    intent: CompositionIntent,
    *,
    sheet: str,
    region: Box,
    reserved: tuple[Box, ...] = (),
    component_sheets: Mapping[str, str] | None = None,
    budget: int = PLACEMENT_BUDGET,
) -> CompositionPlan:
    """Pack complete block envelopes in reading order, with a deterministic candidate limit."""
    from fenolite.schematic.blocks import compose_block, translated

    groups = tuple(
        b for b in group_units(units, intent, component_sheets=component_sheets) if b.units[0].sheet == sheet
    )
    placements: list[Placement] = []
    blocks: list[PlacedBlock] = []
    attachments: list[Attachment] = []
    candidates = 0
    cursor_x, cursor_y = up(region.x0), up(region.y0)
    for block in groups:
        local = compose_block(block, intent.flow)
        if local.bounds.width > region.width or local.bounds.height > region.height:
            raise fail(
                "overflow",
                "block envelope exceeds usable sheet",
                f"{sheet}/{block.key}",
                "use a larger fixed paper or split the block",
            )
        x, y = cursor_x, cursor_y
        while True:
            if candidates >= budget:
                raise fail(
                    "budget-exhausted",
                    "placement candidate budget exhausted",
                    f"{sheet}/{block.key}",
                    "reduce congestion or split blocks",
                )
            candidates += 1
            box = local.bounds.move(x, y)
            if (
                region.contains(box)
                and not any(box.overlaps(b.bounds) for b in blocks)
                and not any(box.overlaps(r) for r in reserved)
            ):
                break
            if intent.flow == "left-to-right":
                x += GRID
                if x + local.bounds.width > region.x1:
                    x, y = up(region.x0), y + GRID
            else:
                y += GRID
                if y + local.bounds.height > region.y1:
                    x, y = x + GRID, up(region.y0)
            if y + local.bounds.height > region.y1 or x + local.bounds.width > region.x1:
                raise fail(
                    "overflow",
                    "no legal region for block",
                    f"{sheet}/{block.key}",
                    "use a larger fixed paper or split blocks",
                )
        blocks.append(PlacedBlock(block.key, block.title, box))
        placements.extend(translated(p, x, y) for p in local.placements)
        attachments.extend(local.attachments)
        if intent.flow == "left-to-right":
            cursor_x, cursor_y = x + local.bounds.width + GAP, y
            if cursor_x >= region.x1:
                cursor_x, cursor_y = up(region.x0), y + GRID
        else:
            cursor_x, cursor_y = x, y + local.bounds.height + GAP
            if cursor_y >= region.y1:
                cursor_x, cursor_y = x + GRID, up(region.y0)
    plan = CompositionPlan(
        sheet,
        intent.flow,
        region,
        reserved,
        tuple(blocks),
        tuple(placements),
        attachments=tuple(attachments),
        candidates=candidates,
    )
    validate_plan(plan)
    return plan


def group_units(
    units: tuple[Unit, ...],
    intent: CompositionIntent,
    *,
    component_sheets: Mapping[str, str] | None = None,
) -> tuple[Block, ...]:
    """Resolve explicit groups, module groups and signal-connected root groups."""
    if intent.flow not in ("left-to-right", "top-to-bottom"):
        raise fail("invalid-intent", "unsupported reading direction", "flow", "select a supported flow")
    if len({u.key for u in units}) != len(units):
        raise fail("invalid-intent", "duplicate unit identities", "units", "retain unique unit keys")
    known = dict(component_sheets or {u.component: u.sheet for u in units})
    by_component: dict[str, list[Unit]] = {}
    for unit in sorted(units, key=lambda u: u.key):
        by_component.setdefault(unit.component, []).append(unit)
    blocks: dict[str, Block] = {}
    used: set[str] = set()
    for declaration in sorted(intent.blocks, key=lambda b: b.key):
        if not declaration.key or declaration.key in blocks or not declaration.members:
            raise fail(
                "invalid-intent", "empty or duplicate block declaration", declaration.key, "use unique blocks"
            )
        sheets: set[str] = set()
        found: list[Unit] = []
        for member in declaration.members:
            if member not in known or member in used:
                raise fail(
                    "invalid-intent",
                    f"unknown or duplicate member {member}",
                    declaration.key,
                    "fix membership",
                )
            used.add(member)
            sheets.add(known[member])
            found.extend(by_component.get(member, ()))
        if len(sheets) > 1:
            raise fail(
                "invalid-intent",
                "block spans electrical sheets",
                declaration.key,
                "declare one block per sheet",
            )
        if declaration.anchor is not None and declaration.anchor not in declaration.members:
            raise fail("invalid-intent", "anchor is not a member", declaration.key, "choose a member anchor")
        blocks[declaration.key] = Block(
            declaration.key,
            declaration.title,
            tuple(sorted(found, key=lambda u: u.key)),
            declaration.anchor,
            declaration.after,
        )
    for block in blocks.values():
        if block.after is None:
            continue
        before = blocks.get(block.after)
        if (
            before is None
            or not before.units
            or not block.units
            or before.units[0].sheet != block.units[0].sheet
        ):
            raise fail(
                "invalid-intent", "predecessor is absent or on another sheet", block.key, "fix block order"
            )
    remaining = [u for u in sorted(units, key=lambda u: u.key) if u.component not in used]
    modules: dict[tuple[str, str], list[Unit]] = {}
    root: dict[str, list[Unit]] = {}
    for unit in remaining:
        module = unit.component.rpartition("/")[0]
        if module:
            modules.setdefault((unit.sheet, module), []).append(unit)
        else:
            root.setdefault(unit.sheet, []).append(unit)

    def add_auto(title: str, members: list[Unit]) -> None:
        key = f"auto:{title}"
        while key in blocks:
            key = f"auto:{key}"
        blocks[key] = Block(key, title, tuple(members))

    for (sheet, module), members in sorted(modules.items()):
        add_auto(f"{sheet}/{module}", members)
    for sheet, members in sorted(root.items()):
        neighbours = {u.component: set[str]() for u in members}
        nets: dict[str, set[str]] = {}
        power: set[str] = set()
        for unit in members:
            for pin in unit.pins:
                if pin.net is not None:
                    nets.setdefault(pin.net, set()).add(unit.component)
                    if pin.power:
                        power.add(pin.net)
        for net, endpoints in sorted(nets.items()):
            if net in power or len(endpoints) > FANOUT_LIMIT:
                continue
            for member in endpoints:
                neighbours[member].update(endpoints - {member})
        unseen = set(neighbours)
        while unseen:
            first = min(unseen)
            stack = [first]
            connected: set[str] = set()
            while stack:
                current = stack.pop()
                if current in connected:
                    continue
                connected.add(current)
                stack.extend(sorted(neighbours[current] - connected, reverse=True))
            unseen -= connected
            add_auto(f"{sheet}/{first}", [u for u in members if u.component in connected])
    ordered: list[Block] = []
    pending = dict(blocks)
    while pending:
        available = sorted(k for k, b in pending.items() if b.after not in pending)
        if not available:
            raise fail("invalid-intent", "block ordering cycle", min(pending), "remove cyclic predecessors")
        key = available[0]
        ordered.append(pending.pop(key))
    return tuple(b for b in ordered if b.units)
