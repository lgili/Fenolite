# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The critical routes of the role groups (change c0244; capability net-roles, "Critical route plan" and
"Critical copper for later phases"; ``docs/roles.md``, "Critical routes").

``plan_critical`` turns the confirmed and declared gate loops and Kelvin pairs of a board into the routes of
their open connections, in this package's own plain types; the command ``fenolite route --roles critical``
translates them into ``routing.protocol.JobRoleRoute`` and hands them to a router with the feature ``roles``.

- **Gate loops** (tier 0): the drive segments (driver output to gate, through the gate resistor's pads) and
  one return from the source or Kelvin-source pad to the driver's return pad (S-0853), the return paired
  with the longest drive segment, at the width of its drive (it carries the gate current back, S-0891).
- **Kelvin pairs** (tier 1): two partnered branches from an entry point on the inner half of each sense pad
  to the receiver (S-0850, S-0852), at the pair width of a model pair, else the ``Default`` class width (a
  sense branch carries no current).
- A branch of a ``power``, ``switch_node`` or ``ground`` net is isolated: it may touch its own net's copper
  only at its ends (S-0892). Kelvin branches keep the profile's ``switching_distance_nm`` from every switch
  node, gate routes from the nodes of other switches, as c0222's judge judges them.
- Hot loops are phase 1's power copper (the maintainer's decision of 2026-10-29) and are never planned; one
  named by ``groups`` is ``skipped`` with reason ``phase-1``. Inferred groups are ``skipped`` with reason
  ``unconfirmed``.

``critical_copper`` reads, from a board, the copper and the corridors ``role.corridor.<group>.<net>`` that
role mode wrote for each group, for the later phases to keep and to fill around (c0243's contract).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Location, Thick, point_in_ring, thick_touch
from fenolite.model.board import Keepout
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design
from fenolite.model.pairs import pair_base
from fenolite.model.rules import GateLoop, KelvinPair, RoleSet
from fenolite.roles import profile
from fenolite.roles.codes import STATED
from fenolite.roles.kelvin import pad_name

MARGIN = 2_000
"""The margin of an entry point inside its pad: c0228's margin of the octilinear router (2 µm)."""
GATE_VIAS = 2
"""The vias a gate return may place by default: one at each end of its stacked form (S-0891)."""
ISOLATED_KINDS = frozenset({"power", "switch_node", "ground"})
"""The role kinds whose branches are isolated from the rest of their net's copper (S-0892)."""
TIER_GATE = 0
TIER_KELVIN = 1
CORRIDOR_PREFIX = "role.corridor."
"""The name prefix of the corridors of both phases (c0243 and c0244, decided on 2026-10-29)."""
_UNSAFE = re.compile(r"[^A-Za-z0-9_+-]")


def safe_net(net: str) -> str:
    """``net`` with every character outside ``A-Z a-z 0-9 _ + -`` made ``_``: the net part of a corridor
    name."""
    return _UNSAFE.sub("_", net)


def corridor_name(group: str, net: str) -> str:
    """The name of the corridor of ``net``'s branch of ``group``: ``role.corridor.<group>.<net>``."""
    return f"{CORRIDOR_PREFIX}{group}.{safe_net(net)}"


@dataclass(frozen=True, slots=True)
class RouteEnd:
    """One end of a critical route: the pad, its net and copper layers, and ``at``, where the track ends."""

    ref: str
    number: str
    net: str
    at: Point
    layers: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.ref}-{self.number}"


@dataclass(frozen=True, slots=True)
class CriticalRoute:
    """One open connection of a group, with the fields of ``routing.protocol.JobRoleRoute``."""

    group: str
    kind: str
    tier: int
    net: str
    a: RouteEnd
    b: RouteEnd
    width: int
    layers: tuple[str, ...]
    vias: int = 0
    isolated: bool = False
    aggressors: tuple[str, ...] = ()
    keep_away: int = 0
    partner: str = ""
    gap: int = 0
    loop: tuple[Point, ...] = ()
    key: str = ""
    plane: bool = False


@dataclass(frozen=True, slots=True)
class GroupPlan:
    """One group of the plan: its name, kind (``gate_loop``, ``kelvin_pair``, ``hot_loop``) and tier, its
    status before routing (``planned``, ``complete``, ``kept``, ``skipped``, ``unrouted``), the reason of a
    skipped or unrouted group, its pads, the keys of its routes, the nets of its connections, and the
    role findings it had."""

    name: str
    kind: str
    tier: int
    status: str
    reason: str = ""
    pads: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()
    nets: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CriticalPlan:
    """The groups of the plan, sorted by tier and name, and the routes of the planned ones."""

    groups: tuple[GroupPlan, ...] = ()
    routes: tuple[CriticalRoute, ...] = ()

    def group(self, name: str) -> GroupPlan | None:
        return next((found for found in self.groups if found.name == name), None)


# --- pads and copper -------------------------------------------------------------------------------------


def _copper_layers(record: BoardPad) -> tuple[str, ...]:
    return tuple(dict.fromkeys(entry.layer for entry in record.copper))


def _common_layers(a: BoardPad, b: BoardPad, stack: Sequence[str]) -> tuple[str, ...]:
    """The layers of ``stack`` that both pads reach, the first pad's side first; without one, the first pad's
    layers, then the second's."""
    mine, other = set(_copper_layers(a)), set(_copper_layers(b))
    common = [layer for layer in stack if layer in mine and layer in other]
    side = "B.Cu" if a.side == "bottom" else "F.Cu"
    if not common:  # a route between them changes layer at a via, when one is allowed
        return (*(layer for layer in stack if layer in mine), *(layer for layer in stack if layer in other))
    return tuple(sorted(common, key=lambda layer: (layer != side, stack.index(layer))))


def _adjacent(layer: str, stack: Sequence[str]) -> str | None:
    """The copper layer next to ``layer`` toward the inside of the stack."""
    if layer not in stack or len(stack) < 2:
        return None
    index = stack.index(layer)
    nxt = index + 1 if index < len(stack) - 1 else index - 1
    return stack[nxt]


def half_extent(record: BoardPad, toward: Point, layer: str | None = None) -> int:
    """The extent of ``record``'s copper from its centre along the unit vector toward ``toward``, in
    nanometres (rounded down)."""
    c = record.position
    dx, dy = toward.x - c.x, toward.y - c.y
    norm = isqrt(dx * dx + dy * dy)
    if norm == 0:
        return 0
    best = 0
    for entry in record.copper:
        if layer is not None and entry.layer != layer:
            continue
        for point in entry.core:
            reach = ((point.x - c.x) * dx + (point.y - c.y) * dy) // norm + entry.width // 2
            best = max(best, reach)
    return best


def entry_point(record: BoardPad, toward: Point, width: int, layer: str | None = None) -> Point:
    """The end of a sense branch on ``record``'s inner half: ``c + u·(L/2 − w/2 − MARGIN)`` along the unit
    vector ``u`` toward ``toward``, rounded toward the centre ``c``; the centre when that offset is not
    positive (design decision 5)."""
    c = record.position
    reach = half_extent(record, toward, layer) - (width + 1) // 2 - MARGIN
    dx, dy = toward.x - c.x, toward.y - c.y
    norm = isqrt(dx * dx + dy * dy)
    if reach <= 0 or norm == 0:
        return c

    def toward_c(value: int) -> int:
        return value // norm if value >= 0 else -((-value) // norm)

    return Point(c.x + toward_c(dx * reach), c.y + toward_c(dy * reach))


def _inside_pad(point: Point, record: BoardPad) -> bool:
    probe = Thick((point,), 1)
    for entry in record.copper:
        try:
            shape = Thick(entry.core, entry.width, entry.filled)
        except ValueError:
            continue
        if thick_touch(probe, shape):
            return True
    return False


def copper_path(design: Design, net: str, a: BoardPad, b: BoardPad) -> tuple[Point, ...]:
    """The points of the tracks and arcs of ``net`` that join ``a`` to ``b`` in walk order, ``a``'s and
    ``b``'s centres first and last; ``(a, b)`` when no track path joins them (a zone, or nothing)."""
    board = design.board
    straight = (a.position, b.position)
    if board is None:
        return straight
    net_id = next((found.id for found in design.circuit.nets if found.name == net), None)
    segments = [(t.start, t.end) for t in board.tracks if t.net_id == net_id and t.start != t.end]
    segments += [(arc.start, arc.end) for arc in board.arcs if arc.net_id == net_id and arc.start != arc.end]
    if not segments:
        return straight
    near: dict[Point, list[Point]] = {}
    for p, q in segments:
        near.setdefault(p, []).append(q)
        near.setdefault(q, []).append(p)
    starts = sorted((point for point in near if _inside_pad(point, a)), key=lambda p: (p.x, p.y))
    goals = {point for point in near if _inside_pad(point, b)}
    seen: dict[Point, Point | None] = {point: None for point in starts}
    queue = list(starts)
    found: Point | None = None
    while queue:
        point = queue.pop(0)
        if point in goals:
            found = point
            break
        for other in sorted(near[point], key=lambda p: (p.x, p.y)):
            if other not in seen:
                seen[other] = point
                queue.append(other)
    if found is None:
        return straight
    path: list[Point] = []
    step: Point | None = found
    while step is not None:
        path.append(step)
        step = seen[step]
    path.reverse()
    points = [a.position, *path, b.position]
    return tuple(point for i, point in enumerate(points) if i == 0 or point != points[i - 1])


# --- the plan -----------------------------------------------------------------------------------------------


def _classes(design: Design) -> tuple[dict[str, NetClass | None], NetClass | None]:
    classes = {item.id: item for item in design.circuit.netclasses}
    default = next((item for item in design.circuit.netclasses if item.name.casefold() == "default"), None)
    return {net.name: classes.get(net.netclass_id or "") for net in design.circuit.nets}, default


def _value(name: str, key: str, of: Mapping[str, NetClass | None], default: NetClass | None) -> int | None:
    found = getattr(of.get(name), key, None)
    return found if found is not None else getattr(default, key, None)


def _model_pair(a: str, b: str) -> bool:
    return pair_base(a, b) is not None or pair_base(b, a) is not None


@dataclass
class _Context:
    design: Design
    roles: RoleSet
    records: dict[str, BoardPad]
    stack: tuple[str, ...]
    clearance: Callable[[str, str], int]
    default_width: int
    keep_away: int | None
    islands: dict[str, list[set[str]]]
    of: dict[str, NetClass | None]
    default: NetClass | None

    def kind(self, net: str | None) -> str | None:
        role = self.roles.role_of(net) if net is not None else None
        return role.kind if role is not None else None

    def joined(self, net: str, a: str, b: str) -> bool:
        return any(a in island and b in island for island in self.islands.get(net, ()))

    def nodes(self) -> list[str]:
        return sorted(role.net for role in self.roles.nets if role.kind == "switch_node")

    def away(self, net: str) -> int:
        if self.keep_away is not None:
            return self.keep_away
        return profile.resolve("switching_distance_nm", self.roles.limits, net=net, kind="kelvin").value or 0

    def end(self, record: BoardPad, at: Point | None = None) -> RouteEnd:
        return RouteEnd(
            record.ref, record.number, record.net or "", at or record.position, _copper_layers(record)
        )


def _ring(chain: Sequence[tuple[Point, ...]], k: int) -> tuple[Point, ...]:
    """The loop points of connection ``k`` of the cyclic ``chain`` of paths: from the end of path ``k``
    around to its start, both ends excluded."""
    count = len(chain)
    points: list[Point] = []
    for step in range(1, count):
        for point in chain[(k + step) % count]:
            if not points or points[-1] != point:
                points.append(point)
    first, last = chain[k][-1], chain[k][0]
    while points and points[0] == first:
        points.pop(0)
    while points and points[-1] == last:
        points.pop()
    return tuple(points)


def _gate(ctx: _Context, loop: GateLoop) -> tuple[GroupPlan, list[CriticalRoute]]:
    pads = loop.pads
    if any(name not in ctx.records for name in pads):
        return GroupPlan(loop.name, "gate_loop", TIER_GATE, "unrouted", "pads", pads), []
    order = [loop.drive, *loop.resistor, loop.gate, loop.source, loop.ret]
    # the connections of the loop in order: (a, b, kind); the jumps inside parts close the chain
    links: list[tuple[str, str, str]] = []
    outs = (
        [(loop.drive, loop.resistor[0]), (loop.resistor[1], loop.gate)]
        if loop.resistor
        else [(loop.drive, loop.gate)]
    )
    links += [(a, b, "gate-out") for a, b in outs]
    links.append((loop.source, loop.ret, "gate-return"))
    chain: list[tuple[Point, ...]] = []
    cycle = [*order, order[0]]
    for a, b in zip(cycle, cycle[1:], strict=False):
        ra, rb = ctx.records[a], ctx.records[b]
        net = ra.net if ra.net == rb.net else None
        if net and ctx.joined(net, a, b):
            chain.append(copper_path(ctx.design, net, ra, rb))
        else:
            chain.append((ra.position, rb.position))
    index = {(a, b): i for i, (a, b) in enumerate(zip(cycle, cycle[1:], strict=False))}
    open_links = [(a, b, kind) for a, b, kind in links if not _link_joined(ctx, a, b)]
    nets = tuple(sorted({ctx.records[a].net or "" for a, _, _ in links}))
    if not open_links:
        return GroupPlan(loop.name, "gate_loop", TIER_GATE, "joined", "", pads, (), nets), []
    switch = loop.gate.rpartition("-")[0]
    own_nodes = {
        record.net
        for record in ctx.records.values()
        if record.ref == switch and ctx.kind(record.net) == "switch_node"
    }
    longest = max(outs, key=lambda link: _dist(ctx.records[link[0]].position, ctx.records[link[1]].position))
    out_width = (
        _value(ctx.records[longest[0]].net or "", "track_width", ctx.of, ctx.default) or ctx.default_width
    )
    ret_key = _key(loop.name, "gate-return", loop.source, loop.ret)
    routes: list[CriticalRoute] = []
    for a, b, kind in open_links:
        ra, rb = ctx.records[a], ctx.records[b]
        net = ra.net or ""
        layers = _common_layers(ra, rb, ctx.stack)
        if kind == "gate-return":
            width = out_width
            partner = _key(loop.name, "gate-out", *longest) if (*longest, "gate-out") in open_links else ""
            side = layers[0] if layers else None
            extra = _adjacent(side, ctx.stack) if side is not None else None
            if extra is not None and extra not in layers:
                layers = (*layers, extra)
            vias = GATE_VIAS
            gap = ctx.clearance(ctx.records[longest[0]].net or "", net)
        else:
            width = _value(net, "track_width", ctx.of, ctx.default) or ctx.default_width
            partner = (
                ret_key if (loop.source, loop.ret, "gate-return") in open_links and (a, b) == longest else ""
            )
            vias = 0
            gap = ctx.clearance(net, ctx.records[loop.source].net or "")
        aggressors = tuple(node for node in ctx.nodes() if node not in own_nodes and node != net)
        routes.append(
            CriticalRoute(
                loop.name,
                kind,
                TIER_GATE,
                net,
                ctx.end(ra),
                ctx.end(rb),
                width,
                layers,
                vias,
                ctx.kind(net) in ISOLATED_KINDS,
                aggressors,
                ctx.away(net) if aggressors else 0,
                partner,
                gap if partner else 0,
                _ring(chain, index[(a, b)]),
                _key(loop.name, kind, a, b),
                kind == "gate-return" and ctx.kind(net) == "ground",
            )
        )
    plan = GroupPlan(
        loop.name, "gate_loop", TIER_GATE, "planned", "", pads, tuple(r.key for r in routes), nets
    )
    return plan, routes


def _link_joined(ctx: _Context, a: str, b: str) -> bool:
    ra, rb = ctx.records[a], ctx.records[b]
    return bool(ra.net) and ra.net == rb.net and ctx.joined(ra.net or "", a, b)


def _dist(a: Point, b: Point) -> int:
    return isqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _key(group: str, kind: str, a: str, b: str) -> str:
    return f"{group}:{kind}:{a}:{b}"


def _receiver(ctx: _Context, receiver: str, net: str) -> BoardPad | None:
    """The pad a branch of ``net`` ends at: the receiver's pad on ``net``, else the pad on ``net`` of a
    two-pad part whose other pad lies on the receiver's net (a series resistor)."""
    record = ctx.records.get(receiver)
    if record is None:
        return None
    if record.net == net:
        return record
    parts: dict[str, list[BoardPad]] = {}
    for found in ctx.records.values():
        parts.setdefault(found.ref, []).append(found)
    for ref in sorted(parts):
        held = parts[ref]
        if len(held) == 2 and {held[0].net, held[1].net} == {net, record.net}:
            return next(found for found in held if found.net == net)
    return None


def _kelvin(ctx: _Context, pair: KelvinPair) -> tuple[GroupPlan, list[CriticalRoute]]:
    pads = (*pair.element, *pair.receiver, *pair.force)
    elements = [ctx.records.get(name) for name in pair.element]
    if any(record is None or record.net is None for record in elements):
        return GroupPlan(pair.name, "kelvin_pair", TIER_KELVIN, "unrouted", "pads", pads), []
    e0, e1 = elements[0], elements[1]
    assert e0 is not None and e1 is not None
    n0, n1 = e0.net or "", e1.net or ""
    receivers = [_receiver(ctx, pair.receiver[0], n0), _receiver(ctx, pair.receiver[1], n1)]
    if any(record is None for record in receivers):
        return GroupPlan(pair.name, "kelvin_pair", TIER_KELVIN, "unrouted", "pads", pads), []
    r0, r1 = receivers[0], receivers[1]
    assert r0 is not None and r1 is not None
    nets = tuple(sorted({n0, n1}))
    sides = ((e0, r0, e1, r1), (e1, r1, e0, r0))
    joined = [ctx.joined(e.net or "", pad_name(e), pad_name(r)) for e, r, _, _ in sides]
    if all(joined):
        return GroupPlan(pair.name, "kelvin_pair", TIER_KELVIN, "joined", "", pads, (), nets), []
    if _model_pair(n0, n1):
        width = _value(n0, "diff_pair_width", ctx.of, ctx.default) or ctx.default_width
        gap = _value(n0, "diff_pair_gap", ctx.of, ctx.default) or ctx.clearance(n0, n1)
    else:
        width = getattr(ctx.default, "track_width", None) or ctx.default_width
        gap = ctx.clearance(n0, n1)
    keys = [_key(pair.name, "kelvin", pad_name(e), pad_name(r)) for e, r, _, _ in sides]
    routes: list[CriticalRoute] = []
    for i, (element, receiver, other, other_receiver) in enumerate(sides):
        net = element.net or ""
        layers = _common_layers(element, receiver, ctx.stack)
        at = entry_point(element, other.position, width, layers[0] if layers else None)
        aggressors = tuple(node for node in ctx.nodes() if node != net)
        routes.append(
            CriticalRoute(
                pair.name,
                "kelvin",
                TIER_KELVIN,
                net,
                ctx.end(element, at),
                ctx.end(receiver),
                width,
                layers,
                0,
                ctx.kind(net) in ISOLATED_KINDS,
                aggressors,
                ctx.away(net) if aggressors else 0,
                keys[1 - i],
                gap,
                (other_receiver.position, other.position),
                keys[i],
            )
        )
    plan = GroupPlan(pair.name, "kelvin_pair", TIER_KELVIN, "planned", "", pads, tuple(keys), nets)
    return plan, routes


def plan_critical(
    design: Design,
    roles: RoleSet,
    pads: Sequence[BoardPad],
    *,
    layers: Sequence[str],
    clearance: Callable[[str, str], int],
    default_width: int,
    groups: Sequence[str] = (),
    findings: Mapping[str, Sequence[str]] | None = None,
    keep_away: int | None = None,
) -> CriticalPlan:
    """The critical routes of ``roles`` on the board ``design``: one entry per gate loop and Kelvin pair (and
    per hot loop named by ``groups``), and the routes of the open connections of the confirmed and declared
    ones. ``layers`` are the routing layers in stack order; ``clearance`` gives the clearance in force
    between two nets; ``default_width`` is the track width when no class gives one; ``groups`` limits the
    plan to the named groups; ``findings`` holds each group's role findings, which make a joined group
    ``kept`` instead of ``complete``; ``keep_away`` overrides the profile's ``switching_distance_nm``."""
    records = {pad_name(record): record for record in pads}
    wanted = set(groups)
    held = {pad for group in (*roles.gates, *roles.kelvins) for pad in group.pads}
    names = {found.net for pad in held if (found := records.get(pad)) is not None and found.net}
    report = connectivity(design, pads=pads, nets=names)
    islands = {row.name: [set(island) for island in row.pads] for row in report.nets}
    of, default = _classes(design)
    ctx = _Context(
        design, roles, records, tuple(layers), clearance, default_width, keep_away, islands, of, default
    )
    plans: list[GroupPlan] = []
    routes: list[CriticalRoute] = []
    for loop in roles.loops:
        if loop.name in wanted:
            plans.append(GroupPlan(loop.name, "hot_loop", TIER_GATE, "skipped", "phase-1", loop.pads))
    chosen: list[tuple[str, GateLoop | KelvinPair]] = [
        *(("gate", g) for g in roles.gates),
        *(("kelvin", k) for k in roles.kelvins),
    ]
    for kind, group in chosen:
        if wanted and group.name not in wanted:
            continue
        what = "gate_loop" if kind == "gate" else "kelvin_pair"
        tier = TIER_GATE if kind == "gate" else TIER_KELVIN
        if group.origin not in STATED:
            plans.append(GroupPlan(group.name, what, tier, "skipped", "unconfirmed", group.pads))
            continue
        plan, made = _gate(ctx, group) if isinstance(group, GateLoop) else _kelvin(ctx, group)
        if plan.status == "joined":
            held = tuple(sorted(set(findings.get(plan.name, ()) if findings else ())))
            status = "kept" if held else "complete"
            plan = GroupPlan(plan.name, plan.kind, plan.tier, status, "", plan.pads, (), plan.nets, held)
        plans.append(plan)
        routes += made
    plans.sort(key=lambda found: (found.tier, found.kind != "hot_loop", found.name))
    routes.sort(key=lambda found: (found.tier, found.group, found.key))
    return CriticalPlan(tuple(plans), tuple(routes))


# --- the copper of the groups, for later phases -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroupCopper:
    """The role copper of one group on a board: its corridors and the locked tracks, arcs and vias of its
    nets that lie inside them, by id."""

    group: str
    kind: str
    corridors: tuple[str, ...] = ()
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CriticalCopper:
    """The role copper of every gate loop and Kelvin pair of a board, by group name."""

    groups: tuple[GroupCopper, ...] = ()

    def group(self, name: str) -> GroupCopper | None:
        return next((found for found in self.groups if found.group == name), None)


def _within(point: Point, ring: Sequence[Point]) -> bool:
    return point_in_ring(point, ring) is not Location.OUTSIDE


def critical_copper(design: Design, roles: RoleSet) -> CriticalCopper:
    """The copper and the corridors that role mode wrote for each gate loop and Kelvin pair of ``roles``, read
    from ``design``'s board: the corridors named ``role.corridor.<group>.<net>``, and the locked items of each
    corridor's net on its layers whose every point lies inside it. It reads the board only, so it works on a
    board read back from KiCad or Altium."""
    board = design.board
    if board is None:
        return CriticalCopper()
    net_names = {net.id: net.name for net in design.circuit.nets}
    by_safe: dict[str, set[str]] = {}
    for name in net_names.values():
        by_safe.setdefault(safe_net(name), set()).add(name)
    found: list[GroupCopper] = []
    groups: list[tuple[str, str]] = [
        *((g.name, "gate_loop") for g in roles.gates),
        *((k.name, "kelvin_pair") for k in roles.kelvins),
    ]
    for group, kind in sorted(groups):
        prefix = f"{CORRIDOR_PREFIX}{group}."
        areas: list[Keepout] = [area for area in board.keepouts if area.name.startswith(prefix)]
        items: set[str] = set()
        for area in areas:
            nets = by_safe.get(area.name[len(prefix) :], set())
            ring = area.outline
            if len(ring) < 3:
                continue
            for track in (*board.tracks, *board.arcs):
                if not track.locked or net_names.get(track.net_id or "") not in nets:
                    continue
                if track.layer in area.layers and _within(track.start, ring) and _within(track.end, ring):
                    items.add(track.id)
            for via in board.vias:
                if via.locked and net_names.get(via.net_id or "") in nets and _within(via.position, ring):
                    items.add(via.id)
        found.append(GroupCopper(group, kind, tuple(sorted(a.id for a in areas)), tuple(sorted(items))))
    return CriticalCopper(tuple(found))


__all__ = [
    "CORRIDOR_PREFIX",
    "GATE_VIAS",
    "ISOLATED_KINDS",
    "MARGIN",
    "TIER_GATE",
    "TIER_KELVIN",
    "CriticalCopper",
    "CriticalPlan",
    "CriticalRoute",
    "GroupCopper",
    "GroupPlan",
    "RouteEnd",
    "copper_path",
    "corridor_name",
    "critical_copper",
    "entry_point",
    "half_extent",
    "plan_critical",
    "safe_net",
]
