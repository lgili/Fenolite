# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role mode of the octilinear router: the critical routes of gate loops and Kelvin pairs (change c0244;
capability routing, "Role routes in a routing job" and the requirements after it; ``docs/routing.md``, "Role
mode").

``OctilinearRouter.route`` calls ``route_roles`` when ``job.roles`` is not empty, and routes nothing else.
The routes run in tiers (0: gate loops, 1: Kelvin pairs), each group as one unit routed whole or not at all,
with c0228's rounds inside a tier. Each route is tried with c0228's five shapes and the Z shapes of S-0837
(a first segment, a middle segment on a free line, a last segment), on each allowed layer, and accepted when
it passes c0228's acceptance and, in role mode:

- **isolation** (S-0892): an isolated route keeps the clearance in force from the copper of its own net, the
  end pads and the copper already joined to them excepted, and does not touch the outline of a zone of its
  net;
- **keep-away**: a route with aggressors keeps ``keep_away`` from their copper and zone outlines on its layer,
  and overlaps none of it on an adjacent copper layer, the condition of c0222's ``roles.near-switching``.

Among the accepted shapes the cheapest is kept: the least gate-loop area (S-0891) for a gate route, the
shortest centre line for a Kelvin pair. A gate return is routed side by side with its drive, else stacked
under it on the adjacent layer through one via at each end (S-0891), else carried by a ground plane under the
drive. The result is judged by the copper check and by ``extra["role_check"]``; a group with a new finding is
removed whole. Every item is locked; the command fences the routed branches with corridors.

Nothing here is taken from any router's code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from math import isqrt
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, format_length, parse_length
from fenolite.geometry import (
    BBox,
    Location,
    Thick,
    area2,
    point_in_ring,
    thick_bbox,
    thick_closer_than,
    thick_touch,
)
from fenolite.model.board import Track, Via
from fenolite.model.pairs import pair_base
from fenolite.model.rules import RuleSubject
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.octilinear import (
    EVIDENCE,
    MARGIN,
    ROUNDS,
    Pad,
    PairConn,
    Polyline,
    World,
    apart,
    bends_ok,
    fresh,
    length,
    offset,
    pair_lines,
    shapes,
    simplify,
    thick,
)
from fenolite.routing.protocol import (
    JobNet,
    JobPair,
    JobRoleEnd,
    JobRoleRoute,
    RoleOutcome,
    RoutingJob,
    RoutingResult,
)

OPTIONS = ("max-length", "rounds", "gate-vias", "kelvin-vias", "keep-away", "z-shapes")
"""The router options of the role mode."""
Z_PER_AXIS = 4
"""The middle lines of Z shapes taken per axis (design decision 12): at most 8 Z shapes per layer."""
RoleFinding = tuple[str, str, str, int | None]
"""A finding of ``extra["role_check"]``: its code, group, severity and measure (a loop ratio in per-mille, or
``None``)."""
RoleCheck = Callable[[object], Sequence[RoleFinding]]
_ROOM, _ISOLATION, _NEAR = 1, 2, 3
"""The tests that refuse a shape, in the order they run."""


@dataclass(frozen=True, slots=True)
class Options:
    """The options of one role job."""

    max_length: Nm | None = None
    rounds: int = ROUNDS
    gate_vias: int | None = None
    kelvin_vias: int | None = None
    keep_away: Nm | None = None
    z_shapes: bool = True


def role_options(options: Mapping[str, str], issues: list[Issue]) -> Options:
    """The role-mode options of ``options``; one ``route.option-ignored`` per unknown key or bad value."""
    found: dict[str, object] = {}
    for key, value in sorted(options.items()):
        ok = False
        if key in ("max-length", "keep-away"):
            try:
                parsed = parse_length(value, default_unit="mm")
            except ValueError:
                parsed = -1
            if parsed > 0 or (key == "keep-away" and parsed == 0):
                found[key] = parsed
                ok = True
        elif key in ("rounds", "gate-vias", "kelvin-vias") and value.isdigit():
            number = int(value)
            if key != "rounds" or number >= 1:
                found[key] = number
                ok = True
        elif key == "z-shapes" and value in ("on", "off"):
            found[key] = value == "on"
            ok = True
        if not ok:
            why = "an unknown option" if key not in OPTIONS else f"{value!r} is no valid value"
            issues.append(
                Issue(
                    "route.option-ignored",
                    "warning",
                    f"the router option {key} is ignored by the octilinear router in role mode: {why}",
                    key,
                    hint="role mode takes max-length=LENGTH, rounds=N, gate-vias=N, kelvin-vias=N, "
                    "keep-away=LENGTH and z-shapes=on|off",
                )
            )
    return Options(
        max_length=cast("int | None", found.get("max-length")),
        rounds=cast(int, found.get("rounds", ROUNDS)),
        gate_vias=cast("int | None", found.get("gate-vias")),
        kelvin_vias=cast("int | None", found.get("kelvin-vias")),
        keep_away=cast("int | None", found.get("keep-away")),
        z_shapes=cast(bool, found.get("z-shapes", True)),
    )


# --- the role world: own-net and aggressor copper -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Item:
    """A copper item of one net on one layer, for isolation and keep-away: its shape, what it is (``pad
    REF-N``, ``track``, ``via``, ``zone NAME``), whether it is a zone outline, and its box."""

    shape: Thick
    what: str
    zone: bool
    box: BBox


class RoleWorld:
    """The copper of every net per layer, as isolation and keep-away read it: pads, tracks, arcs and vias, and
    the outlines of zones (``_Item``), with which pads each item of a net touches."""

    def __init__(self, job: RoutingJob, world: World, pads: Sequence[object]) -> None:
        design = job.design
        board = design.board
        assert board is not None
        self.world = world
        self.layers = job.layers
        net_names = {net.id: net.name for net in design.circuit.nets}
        self.items: dict[tuple[str, str], list[_Item]] = {}
        self.pad_items: dict[tuple[str, str], list[tuple[str, _Item]]] = {}
        self.extents: dict[str, object] = {}
        for pad in pads:
            net = cast("str | None", getattr(pad, "net", None))
            label = f"{getattr(pad, 'ref', '')}-{getattr(pad, 'number', '')}"
            self.extents[label] = pad
            if not net:
                continue
            for entry in cast("tuple[object, ...]", getattr(pad, "copper", ())):
                layer = cast(str, getattr(entry, "layer", ""))
                shape = thick(
                    cast("tuple[Point, ...]", getattr(entry, "core", ())),
                    cast(int, getattr(entry, "width", 0)),
                    cast(bool, getattr(entry, "filled", False)),
                )
                if shape is not None:
                    self.pad_items.setdefault((net, layer), []).append(
                        (label, _Item(shape, f"pad {label}", False, thick_bbox(shape)))
                    )
        for track in (*board.tracks, *board.arcs):
            net = net_names.get(track.net_id or "")
            shape = thick((track.start, track.end), track.width)
            if net and shape is not None:
                self._add(net, track.layer, _Item(shape, f"track {track.id}", False, thick_bbox(shape)))
        for via in board.vias:
            net = net_names.get(via.net_id or "")
            disc = thick((via.position,), via.diameter)
            if net and disc is not None:
                for layer in world.span(via.layers):
                    self._add(net, layer, _Item(disc, f"via {via.id}", False, thick_bbox(disc)))
        for zone in board.zones:
            net = net_names.get(zone.net_id or "")
            if not net or len(zone.outline) < 3:
                continue
            shape = thick(zone.outline, 0, True)
            if shape is None:
                continue
            for layer in zone.layers:
                what = f"zone {zone.name or zone.id}"
                self._add(net, layer, _Item(shape, what, True, thick_bbox(shape)))
        self._own: dict[tuple[str, str, tuple[str, ...]], list[_Item]] = {}

    def _add(self, net: str, layer: str, item: _Item) -> None:
        self.items.setdefault((net, layer), []).append(item)

    def adjacent(self, layer: str) -> tuple[str, ...]:
        if layer not in self.layers:
            return ()
        index = self.layers.index(layer)
        return tuple(self.layers[i] for i in (index - 1, index + 1) if 0 <= i < len(self.layers))

    def own(self, net: str, layer: str, ends: Sequence[str]) -> list[_Item]:
        """The items of ``net`` on ``layer`` that an isolated route of it must keep clear of: every pad but
        the ``ends``, every zone outline, and every track, arc and via not joined to an end pad through
        tracks, arcs and vias alone (the part of the branch that already stands)."""
        key = (net, layer, tuple(ends))
        if key in self._own:
            return self._own[key]
        pads = self.pad_items.get((net, layer), [])
        start = [item for label, item in pads if label in ends]
        others = [item for label, item in pads if label not in ends]
        loose = [item for item in self.items.get((net, layer), []) if not item.zone]
        joined: set[int] = set()
        frontier = list(start)
        while frontier:
            current = frontier.pop()
            for index, item in enumerate(loose):
                if (
                    index not in joined
                    and _boxes_meet(current.box, item.box)
                    and thick_touch(current.shape, item.shape)
                ):
                    joined.add(index)
                    frontier.append(item)
        zones = [item for item in self.items.get((net, layer), []) if item.zone]
        found = [*others, *(item for i, item in enumerate(loose) if i not in joined), *zones]
        self._own[key] = found
        return found

    def aggressor(self, nets: Sequence[str], layer: str) -> list[_Item]:
        found: list[_Item] = []
        for net in nets:
            found += [item for _, item in self.pad_items.get((net, layer), [])]
            found += self.items.get((net, layer), [])
        return found


def _boxes_meet(a: BBox, b: BBox, grow: int = 0) -> bool:
    return not (a.x0 - grow > b.x1 or b.x0 - grow > a.x1 or a.y0 - grow > b.y1 or b.y0 - grow > a.y1)


# --- one route ----------------------------------------------------------------------------------------------


@dataclass
class _Tally:
    """Why the shapes of a route were refused: the first failing test of each shape, and what failed it."""

    tests: list[int] = field(default_factory=lambda: [])
    blockers: list[str] = field(default_factory=lambda: [])
    built: bool = False
    short: bool = False
    layers: bool = False

    def reason(self) -> str:
        if not self.layers:
            return "no-layer"
        if self.built and not self.short:
            return "too-long"
        if _NEAR in self.tests:
            return "near-switching"
        if _ISOLATION in self.tests:
            return "isolation"
        return "no-room"


@dataclass(frozen=True, slots=True)
class _Run:
    net: str
    layer: str
    width: Nm
    points: Polyline


@dataclass(frozen=True, slots=True)
class _Done:
    """The copper of one route: its runs and vias, and its form."""

    route: JobRoleRoute
    runs: tuple[_Run, ...]
    vias: tuple[Point, ...] = ()
    form: str = "single"


class _Router:
    def __init__(self, job: RoutingJob, world: World, roles: RoleWorld, options: Options) -> None:
        self.job = job
        self.world = world
        self.roles = roles
        self.options = options
        self.nets = {net.name: net for net in job.nets}
        self.placed: dict[str, Polyline] = {}
        self.layer_of: dict[str, str] = {}

    # the tests of a segment ---------------------------------------------------------------------------------

    def clear(self, net: str, layer: str, points: Polyline, width: Nm, pair: str | None) -> str | None:
        """``None`` when ``points`` passes c0228's acceptance on ``layer``, else what refused it."""
        return refusal(self.world, net, layer, points, width, pair)

    def isolated(self, route: JobRoleRoute, layer: str, points: Polyline, width: Nm) -> str | None:
        if not route.isolated:
            return None
        ends = (route.a.label, route.b.label)
        own = self.roles.own(route.net, layer, ends)
        mine = self.world.subject(route.net, layer)
        limit = self.world.clearance(mine, mine) + MARGIN
        placed = [shape for other, on, shape, _ in self.world.placed if other == route.net and on == layer]
        for p, q in zip(points, points[1:], strict=False):
            shape = thick((p, q), width)
            if shape is None:
                return "geometry"
            box = thick_bbox(shape)
            for item in own:
                gap = MARGIN if item.zone else limit
                if _boxes_meet(box, item.box, gap) and thick_closer_than(shape, item.shape, gap):
                    return item.what
            for other in placed:
                if thick_closer_than(shape, other, limit):
                    return f"routed copper of net {route.net}"
        return None

    def near(self, route: JobRoleRoute, layer: str, points: Polyline, width: Nm) -> str | None:
        if not route.aggressors:
            return None
        here = self.roles.aggressor(route.aggressors, layer)
        beside = [
            item
            for other in self.roles.adjacent(layer)
            for item in self.roles.aggressor(route.aggressors, other)
        ]
        placed_here = [s for n, on, s, _ in self.world.placed if n in route.aggressors and on == layer]
        placed_beside = [
            s
            for n, on, s, _ in self.world.placed
            if n in route.aggressors and on in self.roles.adjacent(layer)
        ]
        away = max(route.keep_away, 0)
        for p, q in zip(points, points[1:], strict=False):
            shape = thick((p, q), width)
            if shape is None:
                return "geometry"
            box = thick_bbox(shape)
            for item in here:
                if _boxes_meet(box, item.box, away) and thick_closer_than(shape, item.shape, away):
                    return item.what
            for item in beside:
                if _boxes_meet(box, item.box) and thick_touch(shape, item.shape):
                    return item.what
            if any(thick_closer_than(shape, other, away) for other in placed_here) or any(
                thick_touch(shape, other) for other in placed_beside
            ):
                return "routed switching copper"
        return None

    def judge(
        self,
        route: JobRoleRoute,
        layer: str,
        points: Polyline,
        width: Nm,
        tally: _Tally,
        pair: str | None = None,
    ) -> bool:
        """Whether ``points`` passes every test on ``layer``; a refusal is counted in ``tally``."""
        if not self.world.ends_ok(route.net, layer, points):
            tally.tests.append(_ROOM)
            return False
        for test, found in (
            (_ROOM, self.clear(route.net, layer, points, width, pair)),
            (_ISOLATION, self.isolated(route, layer, points, width)),
            (_NEAR, self.near(route, layer, points, width)),
        ):
            if found is not None:
                tally.tests.append(test)
                if found not in tally.blockers:
                    tally.blockers.append(found)
                return False
        return True

    # shapes -------------------------------------------------------------------------------------------------

    def lines(
        self, route: JobRoleRoute, a: Point, b: Point, width: Nm, partner: Polyline, stacked: bool
    ) -> tuple[list[int], list[int]]:
        """The middle lines of Z shapes between ``a`` and ``b``: per axis, from the partner's segments (at the
        pair pitch, or at offset 0 when ``stacked``), the aggressor copper, and the obstacles near the
        straight line, nearest to the middle of ``a`` and ``b`` first, at most ``Z_PER_AXIS`` each."""
        xs: list[int] = []
        ys: list[int] = []
        half = (width + 1) // 2
        pitch = half + (width + 1) // 2 + route.gap + MARGIN
        for p, q in zip(partner, partner[1:], strict=False):
            if p.x == q.x:
                xs += [p.x] if stacked else [p.x - pitch, p.x, p.x + pitch]
            elif p.y == q.y:
                ys += [p.y] if stacked else [p.y - pitch, p.y, p.y + pitch]
        span = BBox.of_points((a, b))
        reach = max(route.keep_away, self.world.reach // 2) + width
        boxes: list[tuple[BBox, int]] = []
        for layer in route.layers:
            for item in self.roles.aggressor(route.aggressors, layer):
                boxes.append((item.box, route.keep_away + half + MARGIN))
            for item in self.world.by_layer.get(layer, []):
                if item.net != route.net:
                    boxes.append(
                        (
                            item.box,
                            self.world.clearance(self.world.subject(route.net, layer), item.subject)
                            + half
                            + MARGIN,
                        )
                    )
            if route.isolated:
                for item in self.roles.own(route.net, layer, (route.a.label, route.b.label)):
                    boxes.append(
                        (
                            item.box,
                            self.world.clearance(
                                self.world.subject(route.net, layer), self.world.subject(route.net, layer)
                            )
                            + half
                            + MARGIN,
                        )
                    )
        for box, grow in boxes:
            if not _boxes_meet(box, span, reach):
                continue
            xs += [box.x0 - grow, box.x1 + grow]
            ys += [box.y0 - grow, box.y1 + grow]
        mx, my = (a.x + b.x) // 2, (a.y + b.y) // 2

        def nearest(values: list[int], mid: int) -> list[int]:
            unique = sorted(set(values), key=lambda v: (abs(v - mid), v))
            return unique[:Z_PER_AXIS]

        return nearest(xs, mx), nearest(ys, my)

    def candidates(
        self, route: JobRoleRoute, a: Point, b: Point, width: Nm, partner: Polyline, stacked: bool
    ) -> list[Polyline]:
        found: list[Polyline] = list(shapes(a, b))
        if self.options.z_shapes and a != b:
            xs, ys = self.lines(route, a, b, width, partner, stacked)
            for x in xs:
                found.append(simplify((a, Point(x, a.y), Point(x, b.y), b)))
            for y in ys:
                found.append(simplify((a, Point(a.x, y), Point(b.x, y), b)))
        unique: list[Polyline] = []
        for shape in found:
            if len(shape) >= 2 and bends_ok(shape) and shape not in unique:
                unique.append(shape)
        return unique

    # cost ---------------------------------------------------------------------------------------------------

    def loop(self, route: JobRoleRoute) -> list[Point]:
        """The loop points of ``route``, with a placed partner's polyline in place of its straight line."""
        points = list(route.loop)
        partner = self.placed.get(route.partner) if route.partner else None
        mate = next((r for r in self.job.roles if r.key == route.partner), None)
        if partner is None or mate is None:
            return points
        for i in range(len(points) - 1):
            if (points[i], points[i + 1]) == (mate.a.at, mate.b.at):
                return [*points[:i], *partner, *points[i + 2 :]]
            if (points[i], points[i + 1]) == (mate.b.at, mate.a.at):
                return [*points[:i], *reversed(partner), *points[i + 2 :]]
        return points

    def area(self, route: JobRoleRoute, points: Polyline) -> int:
        ring = [*points, *self.loop(route)]
        return abs(area2(ring)) if len(ring) >= 3 else 0

    def partner_line(self, route: JobRoleRoute) -> Polyline:
        placed = self.placed.get(route.partner) if route.partner else None
        if placed is not None:
            return placed
        return tuple(route.loop)

    # routing ------------------------------------------------------------------------------------------------

    def too_long(self, points: Polyline) -> bool:
        """Whether ``points`` is longer than ``max-length``; role mode has no default limit, since the
        placement fixes how long a critical route is."""
        limit = self.options.max_length
        return limit is not None and length(points) > limit

    def vias_of(self, route: JobRoleRoute) -> int:
        if route.kind == "gate-return" and self.options.gate_vias is not None:
            return self.options.gate_vias
        if route.kind == "kelvin" and self.options.kelvin_vias is not None:
            return self.options.kelvin_vias
        return route.vias

    def pad_layers(self, route: JobRoleRoute) -> list[str]:
        return [
            layer
            for layer in route.layers
            if layer in route.a.layers and layer in route.b.layers and layer not in self.world.planes
        ]

    def single(self, route: JobRoleRoute, tally: _Tally) -> _Done | None:
        """The cheapest accepted shape of ``route`` on a layer both its pads reach."""
        layers = self.pad_layers(route)
        if not layers:
            return None
        tally.layers = True
        best: tuple[tuple[int, int, int, int], _Done] | None = None
        partner = self.partner_line(route)
        for order, shape in enumerate(
            self.candidates(route, route.a.at, route.b.at, route.width, partner, False)
        ):
            tally.built = True
            if self.too_long(shape):
                continue
            tally.short = True
            for rank, layer in enumerate(layers):
                if not self.judge(route, layer, shape, route.width, tally):
                    continue
                cost = (self.area(route, shape) if route.kind != "kelvin" else 0, length(shape), rank, order)
                if best is None or cost < best[0]:
                    best = (cost, _Done(route, (_Run(route.net, layer, route.width, shape),)))
        return best[1] if best is not None else None

    def stacked(self, route: JobRoleRoute, tally: _Tally) -> _Done | None:
        """A gate return under its drive on the adjacent layer, through one via at each end."""
        if self.vias_of(route) < 2:
            return None
        pad = self.pad_layers(route)
        under = [layer for layer in route.layers if layer not in pad and layer not in self.world.planes]
        if not pad or not under:
            return None
        tally.layers = True
        net = self.nets.get(route.net)
        if net is None:
            return None
        top, layer = pad[0], under[0]
        partner = self.partner_line(route)
        heads = self.via_spots(route, route.a.label, route.a.at, route.b.at, net)
        tails = self.via_spots(route, route.b.label, route.b.at, route.a.at, net)
        best: tuple[tuple[int, int, int], _Done] | None = None
        for va in heads[:3]:
            for vb in tails[:3]:
                if va == vb:
                    continue
                head = self.entry(route, top, route.a.at, va, tally)
                tail = self.entry(route, top, vb, route.b.at, tally)
                if head is None or tail is None:
                    continue
                for order, shape in enumerate(self.candidates(route, va, vb, route.width, partner, True)):
                    tally.built = True
                    if self.too_long(shape):
                        continue
                    tally.short = True
                    if not self.judge(route, layer, shape, route.width, tally):
                        continue
                    whole = (*head, *shape, *tail)
                    cost = (self.area(route, simplify(whole)), length(whole), order)
                    if best is None or cost < best[0]:
                        runs = (
                            _Run(route.net, top, route.width, head),
                            _Run(route.net, layer, route.width, shape),
                            _Run(route.net, top, route.width, tail),
                        )
                        best = (
                            cost,
                            _Done(route, tuple(r for r in runs if len(r.points) >= 2), (va, vb), "stacked"),
                        )
        return best[1] if best is not None else None

    def entry(self, route: JobRoleRoute, layer: str, a: Point, b: Point, tally: _Tally) -> Polyline | None:
        if a == b:
            return (a,)
        for shape in shapes(a, b):
            if self.judge(route, layer, shape, route.width, tally):
                return shape
        return None

    def via_spots(
        self, route: JobRoleRoute, label: str, at: Point, toward: Point, net: JobNet
    ) -> list[Point]:
        """Where a via of ``net`` may stand beside the pad ``label``: in each of the eight octilinear
        directions, just outside the pad's copper, the spots that fit on every layer, nearest to ``toward``
        first."""
        pad = self.roles.extents.get(label)
        spots: list[Point] = []
        for dx, dy in ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)):
            reach = _pad_reach(pad, at, dx, dy) + net.via_diameter // 2 + 2 * MARGIN
            step = reach if dx == 0 or dy == 0 else isqrt(reach * reach // 2) + 1
            spot = Point(at.x + dx * step, at.y + dy * step)
            if self.via_fits(route, spot, net):
                spots.append(spot)
        spots.sort(key=lambda p: ((p.x - toward.x) ** 2 + (p.y - toward.y) ** 2, p.x, p.y))
        return spots

    def via_fits(self, route: JobRoleRoute, at: Point, net: JobNet) -> bool:
        probe = (at, Point(at.x + 1, at.y))
        tally = _Tally()
        return all(self.judge(route, layer, probe, net.via_diameter, tally) for layer in self.world.layers)

    def plane(self, route: JobRoleRoute) -> bool:
        """Whether a zone of the return's ground net covers the whole drive on a layer adjacent to the
        drive's (S-0891: a low-side return may take the plane); the drive is its placed polyline, else the
        drive's copper among the loop points."""
        if route.kind != "gate-return" or not route.plane:
            return False
        drive = self.placed.get(route.partner) if route.partner else None
        layer = self.layer_of.get(route.partner, "") if drive is not None else ""
        if drive is None:
            drive = tuple(route.loop)
            layer = next((x for x in route.layers if x in route.a.layers), "")
        if len(drive) < 2 or not layer:
            return False
        for other in self.roles.adjacent(layer):
            for item in self.roles.items.get((route.net, other), []):
                if item.zone and all(
                    point_in_ring(point, item.shape.core) is not Location.OUTSIDE for point in drive
                ):
                    return True
        return False

    def changed(self, route: JobRoleRoute, tally: _Tally) -> _Done | None:
        """A branch whose ends share no layer, on ``a``'s layer up to a bend of its shape and on ``b``'s layer
        after it, through one via at the bend; the shortest that passes (design decision 8)."""
        net = self.nets.get(route.net)
        first = next((x for x in route.layers if x in route.a.layers and x not in self.world.planes), None)
        last = next((x for x in route.layers if x in route.b.layers and x not in self.world.planes), None)
        if net is None or first is None or last is None or first == last:
            return None
        tally.layers = True
        best: tuple[tuple[int, int], _Done] | None = None
        for order, shape in enumerate(self.candidates(route, route.a.at, route.b.at, route.width, (), False)):
            tally.built = True
            if self.too_long(shape):
                continue
            tally.short = True
            for k in range(1, len(shape) - 1):
                head, tail = shape[: k + 1], shape[k:]
                if not (
                    self.judge(route, first, head, route.width, tally)
                    and self.judge(route, last, tail, route.width, tally)
                    and self.via_fits(route, shape[k], net)
                ):
                    continue
                cost = (length(shape), order)
                if best is None or cost < best[0]:
                    runs = (
                        _Run(route.net, first, route.width, head),
                        _Run(route.net, last, route.width, tail),
                    )
                    best = (cost, _Done(route, runs, (shape[k],), "single"))
        return best[1] if best is not None else None

    def pair(self, first: JobRoleRoute, second: JobRoleRoute, tally: _Tally) -> _Done | None:
        """The two branches of a Kelvin pair as c0228 routes a pair, from the entry points."""
        nets = (self.nets.get(first.net), self.nets.get(second.net))
        if nets[0] is None or nets[1] is None:
            return None
        common = [
            layer
            for layer in first.layers
            if all(layer in end.layers for end in (first.a, first.b, second.a, second.b))
            and layer in second.layers
            and layer not in self.world.planes
        ]
        if not common:
            return None
        tally.layers = True
        base = pair_base(first.net, second.net)
        held = self.world.clearance(
            self.world.subject(first.net, common[0], base), self.world.subject(second.net, common[0], base)
        )
        gap = max(first.gap, held)
        job_pair = JobPair(first.group, first.net, second.net, first.width, gap)
        pads = (
            (
                Pad(first.a.label, first.net, first.a.at, first.a.layers),
                Pad(second.a.label, second.net, second.a.at, second.a.layers),
            ),
            (
                Pad(first.b.label, first.net, first.b.at, first.b.layers),
                Pad(second.b.label, second.net, second.b.at, second.b.layers),
            ),
        )
        conn = PairConn(0, job_pair, nets[0], nets[1], pads)
        m1 = Point((first.a.at.x + second.a.at.x) // 2, (first.a.at.y + second.a.at.y) // 2)
        m2 = Point((first.b.at.x + second.b.at.x) // 2, (first.b.at.y + second.b.at.y) // 2)
        half = (first.width + gap + 1) // 2 + 1
        best: tuple[tuple[int, int, int], _Done] | None = None
        centres = self.candidates(first, m1, m2, 2 * half + first.width, (), False)
        for order, centre in enumerate(centres):
            for trim in (True, False):
                lines = pair_lines(conn, centre, half, trim)
                if lines is None:
                    continue
                one, two = lines
                tally.built = True
                if self.too_long(one) or self.too_long(two):
                    continue
                tally.short = True
                for rank, layer in enumerate(common):
                    if not (
                        self.judge(first, layer, one, first.width, tally, base)
                        and self.judge(second, layer, two, second.width, tally, base)
                    ):
                        continue
                    if not apart(self.world, job_pair, layer, one, two, base):
                        tally.tests.append(_ROOM)
                        continue
                    cost = (length(centre), rank, order)
                    if best is None or cost < best[0]:
                        best = (
                            cost,
                            _Done(
                                first,
                                (
                                    _Run(first.net, layer, first.width, one),
                                    _Run(second.net, layer, second.width, two),
                                ),
                                form="pair",
                            ),
                        )
        return best[1] if best is not None else None


def refusal(
    world: World, net: str, layer: str, points: Polyline, width: Nm, pair: str | None = None
) -> str | None:
    """``None`` when ``points`` passes c0228's clearance and edge tests on ``layer`` in ``world``, else what
    refused it (``pad of R9 of net FENCE``, ``track of net SW``, ``the board edge``); shared with the
    proposal mode (change c0280)."""
    mine = world.subject(net, layer, pair)
    items = world.by_layer.get(layer, [])
    tree = world.index.get(layer)
    for p, q in zip(points, points[1:], strict=False):
        shape = thick((p, q), width)
        if shape is None:
            return "geometry"
        box = thick_bbox(shape).inflate(world.reach)
        for i in tree.query(box) if tree is not None else ():
            item = items[i]
            if item.net == net:
                continue
            if thick_closer_than(shape, item.shape, world.clearance(mine, item.subject) + MARGIN):
                return _subject_text(item.subject)
        for other, on, placed, subject in world.placed:
            if other == net or on != layer:
                continue
            if thick_closer_than(shape, placed, world.clearance(mine, subject) + MARGIN):
                return f"routed copper of net {other}"
        for ring in world.edges:
            if thick_closer_than(shape, ring, max(world.edge, 1)):
                return "the board edge"
    return None


def z_shapes(
    job: RoutingJob, world: World, pads: Sequence[object], net: str, a: Point, b: Point, width: Nm
) -> list[Polyline]:
    """c0244's Z shapes between ``a`` and ``b`` for a plain connection of ``net``: their middle lines come
    from the bounding boxes of the other nets' copper near the straight line (design decision 12 of c0244),
    at most ``Z_PER_AXIS`` per axis; the five shapes of c0228 left out (change c0280, family ``z-shape``)."""
    end_a = JobRoleEnd("", "", net, a, job.layers)
    end_b = JobRoleEnd("", "", net, b, job.layers)
    route = JobRoleRoute("", "connection", 0, net, end_a, end_b, width, job.layers)
    router = _Router(job, world, RoleWorld(job, world, pads), Options())
    plain = set(shapes(a, b))
    return [shape for shape in router.candidates(route, a, b, width, (), False) if shape not in plain]


def _pad_reach(pad: object, at: Point, dx: int, dy: int) -> int:
    best = 0
    for entry in cast("tuple[object, ...]", getattr(pad, "copper", ())):
        width = cast(int, getattr(entry, "width", 0))
        for point in cast("tuple[Point, ...]", getattr(entry, "core", ())):
            along = (point.x - at.x) * dx + (point.y - at.y) * dy
            norm = 1 if dx == 0 or dy == 0 else 2
            reach = along // isqrt(norm) if norm == 1 else (along * 1_000_000) // 1_414_214
            best = max(best, reach + width // 2)
    return best


def _subject_text(subject: RuleSubject) -> str:
    what = subject.item_kind
    if subject.item_kind == "pad" and subject.ref:
        what = f"pad of {subject.ref}"
    net = f" of net {subject.net}" if subject.net else ""
    return f"{what}{net}"


# --- corridors ----------------------------------------------------------------------------------------------


def _simple(ring: Sequence[Point]) -> bool:
    """Whether no two edges of the closed ``ring`` that are not neighbours share a point."""
    from fenolite.geometry import SegmentRelation, classify_segments

    count = len(ring)
    edges = [(ring[i], ring[(i + 1) % count]) for i in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if classify_segments(*edges[i], *edges[j]) is not SegmentRelation.DISJOINT:
                return False
    return True


def _band(points: Polyline, grow: int) -> tuple[Point, ...]:
    left, right = offset(points, 1, grow), offset(points, -1, grow)
    return (*left, *reversed(right))


def corridor_rings(points: Polyline, grow: int) -> tuple[tuple[Point, ...], ...]:
    """The outline of the corridor of the octilinear polyline ``points``: its two offset lines at ``grow``
    (c0228's ``offset``), closed at its ends, as one ring; one ring per segment when that ring would cross
    itself (design decision 10). The ends are flat: a branch ends inside its pad, which joins its own pour."""
    line = simplify(points)
    if len(line) < 2:
        return ()
    ring = _band(line, grow)
    if _simple(ring):
        return (ring,)
    return tuple(_band((p, q), grow) for p, q in zip(line, line[1:], strict=False))


def via_ring(at: Point, grow: int) -> tuple[Point, ...]:
    """The square of half side ``grow`` around a via."""
    return (
        Point(at.x - grow, at.y - grow),
        Point(at.x + grow, at.y - grow),
        Point(at.x + grow, at.y + grow),
        Point(at.x - grow, at.y + grow),
    )


# --- the job ------------------------------------------------------------------------------------------------


@dataclass
class _State:
    """The job copper placed so far, to restore a round or a unit."""

    placed: list[tuple[str, str, Thick, RuleSubject]]
    ends: dict[tuple[str, str, Point], list[tuple[int, int]]]
    lines: dict[str, Polyline]
    layers: dict[str, str]

    @classmethod
    def of(cls, world: World, router: _Router) -> _State:
        return cls(
            list(world.placed),
            {key: list(value) for key, value in world.ends.items()},
            dict(router.placed),
            dict(router.layer_of),
        )

    def restore(self, world: World, router: _Router) -> None:
        world.placed = list(self.placed)
        world.ends = {key: list(value) for key, value in self.ends.items()}
        router.placed = dict(self.lines)
        router.layer_of = dict(self.layers)


@dataclass
class _Unit:
    group: str
    tier: int
    routes: list[JobRoleRoute]


@dataclass
class _Failure:
    reason: str
    blockers: tuple[str, ...]
    key: str


def _units(job: RoutingJob) -> list[_Unit]:
    by_group: dict[str, _Unit] = {}
    for route in job.roles:
        unit = by_group.setdefault(route.group, _Unit(route.group, route.tier, []))
        unit.routes.append(route)
    order = {"gate-out": 0, "gate-return": 1, "kelvin": 2}
    for unit in by_group.values():
        unit.routes.sort(key=lambda r: (order.get(r.kind, 3), r.key))
    return sorted(by_group.values(), key=lambda u: (u.tier, u.group))


def _route_unit(router: _Router, unit: _Unit) -> list[_Done] | _Failure:
    done: list[_Done] = []
    taken: set[str] = set()
    for route in unit.routes:
        if route.key in taken:
            continue
        tally = _Tally()
        results: list[_Done] = []
        mate = next((r for r in unit.routes if r.key == route.partner), None)
        if route.kind == "kelvin" and mate is not None and mate.kind == "kelvin":
            taken.add(mate.key)
            coupled = router.pair(route, mate, tally)
            if coupled is not None:
                router.placed[route.key] = coupled.runs[0].points
                router.placed[mate.key] = coupled.runs[1].points
                results = [coupled]
            elif not tally.layers and router.vias_of(route) >= 2:
                # no layer that all four ends reach: one via per branch (design decision 8)
                first = _place(router, router.changed(route, tally))
                second = _place(router, router.changed(mate, tally)) if first is not None else None
                results = [first, second] if first is not None and second is not None else []
                if first is not None and second is None:
                    return _Failure(tally.reason(), tuple(tally.blockers[:3]), mate.key)
            if not results:
                return _Failure(tally.reason(), tuple(tally.blockers[:3]), route.key)
            if coupled is not None:
                _place(router, coupled)
            done += results
            continue
        result: _Done | None = None
        if router.plane(route):
            result = _Done(route, (), form="plane-return")
        if result is None:
            result = router.single(route, tally)
            if result is not None and route.kind == "gate-return":
                result = _Done(result.route, result.runs, result.vias, "side-by-side")
        if result is None and route.kind == "gate-return":
            result = router.stacked(route, tally)
        if result is None:
            return _Failure(tally.reason(), tuple(tally.blockers[:3]), route.key)
        if result.runs:
            router.placed[route.key] = (
                result.runs[0].points if len(result.runs) == 1 else _joined(result.runs)
            )
            router.layer_of[route.key] = result.runs[0].layer
        _place(router, result)
        done.append(result)
    return done


def _place(router: _Router, result: _Done | None) -> _Done | None:
    """Put the copper of ``result`` into the world, so that the next routes keep clear of it."""
    if result is None:
        return None
    for run in result.runs:
        router.world.place(run.net, run.layer, run.points, run.width)
    net = router.nets.get(result.route.net)
    for point in result.vias:
        disc = thick((point,), net.via_diameter) if net is not None else None
        if disc is not None:
            for layer in router.world.layers:
                subject = router.world.subject(result.route.net, layer)
                router.world.placed.append((result.route.net, layer, disc, subject))
    return result


def _joined(runs: Sequence[_Run]) -> Polyline:
    points: list[Point] = []
    for run in runs:
        for point in run.points:
            if not points or points[-1] != point:
                points.append(point)
    return tuple(points)


def route_roles(job: RoutingJob, world: World, pads: Sequence[object], tool: str) -> RoutingResult:
    """Route ``job.roles`` in ``world`` (the octilinear world of the job) and judge the result."""
    issues: list[Issue] = []
    options = role_options(job.options, issues)
    if options.keep_away is not None:
        job = _with_keep_away(job, options.keep_away)
    roles = RoleWorld(job, world, pads)
    router = _Router(job, world, roles, options)
    units = _units(job)
    outcomes: dict[str, RoleOutcome] = {}
    kept: dict[str, list[_Done]] = {}
    failures: dict[str, _Failure] = {}
    for tier in sorted({item.tier for item in units}):
        start = _State.of(world, router)
        order = [item for item in units if item.tier == tier]
        best: tuple[dict[str, list[_Done]], dict[str, _Failure], _State] | None = None
        for _ in range(options.rounds):
            start.restore(world, router)
            placed: dict[str, list[_Done]] = {}
            failed: dict[str, _Failure] = {}
            for item in order:
                snapshot = _State.of(world, router)
                outcome = _route_unit(router, item)
                if isinstance(outcome, _Failure):
                    snapshot.restore(world, router)
                    failed[item.group] = outcome
                else:
                    placed[item.group] = outcome
            if best is None or len(placed) > len(best[0]):
                best = (placed, failed, _State.of(world, router))
            if not failed:
                break
            again = [*(u for u in order if u.group in failed), *(u for u in order if u.group not in failed)]
            if again == order:
                break
            order = again
        assert best is not None
        best[2].restore(world, router)
        kept.update(best[0])
        failures.update(best[1])
    tracks, vias, owner = _copper(job, kept)
    refused: dict[str, str] = {}
    checked = _copper_check(job, tracks, vias, owner)
    for group, detail in checked.items():
        failures[group] = _Failure("no-room", (detail,), "")
        kept.pop(group, None)
    if checked:
        tracks, vias, owner = _copper(job, kept)
    worse = _role_check(job, tracks, vias, owner)
    for group, detail in worse.items():
        refused[group] = detail
        kept.pop(group, None)
    if worse:
        tracks, vias, owner = _copper(job, kept)
    for route in job.roles:
        if route.group in refused:
            outcomes[route.key] = RoleOutcome(
                route.key, route.group, "refused", "role-check", detail=refused[route.group]
            )
            continue
        if route.group in failures:
            failure = failures[route.group]
            outcomes[route.key] = RoleOutcome(
                route.key,
                route.group,
                "unrouted",
                failure.reason,
                blockers=failure.blockers,
                detail=failure.key,
            )
            continue
        done = next((d for d in kept.get(route.group, []) if d.route.key == route.key), None)
        if done is None:  # the second branch of a pair
            pair = next(
                (d for d in kept.get(route.group, []) if d.route.key == route.partner and d.form == "pair"),
                None,
            )
            if pair is None:
                outcomes[route.key] = RoleOutcome(route.key, route.group, "unrouted", "no-room")
                continue
            run = next(r for r in pair.runs if r.net == route.net)
            outcomes[route.key] = RoleOutcome(
                route.key, route.group, "routed", form="pair", layer=run.layer, length=length(run.points),
                runs=((run.layer, run.width, run.points),),
            )  # fmt: skip
            continue
        if done.form == "plane-return":
            outcomes[route.key] = RoleOutcome(route.key, route.group, "plane-return", form="plane-return")
            continue
        runs = done.runs if done.form != "pair" else tuple(r for r in done.runs if r.net == route.net)
        outcomes[route.key] = RoleOutcome(
            route.key,
            route.group,
            "routed",
            form=done.form,
            layer=runs[0].layer if runs else "",
            length=sum(length(r.points) for r in runs),
            vias=len(done.vias),
            runs=tuple((r.layer, r.width, r.points) for r in runs),
            via_points=done.vias,
        )
    open_nets = {route.net for route in job.roles if outcomes[route.key].status in ("unrouted", "refused")}
    names = [net.name for net in job.nets]
    return RoutingResult(
        tracks=tuple(tracks),
        vias=tuple(vias),
        routed=tuple(name for name in names if name not in open_nets),
        unrouted=tuple(name for name in names if name in open_nets),
        issues=tuple(issues),
        tool=tool,
        tool_version="builtin",
        evidence=EVIDENCE,
        roles=tuple(outcomes[route.key] for route in job.roles),
    )


def _with_keep_away(job: RoutingJob, keep_away: Nm) -> RoutingJob:
    return replace(
        job, roles=tuple(replace(r, keep_away=keep_away if r.aggressors else 0) for r in job.roles)
    )


def _copper(
    job: RoutingJob, kept: Mapping[str, Sequence[_Done]]
) -> tuple[list[Track], list[Via], dict[str, str]]:
    """The locked tracks and vias of the kept groups with their ids, and the group of each id."""
    net_ids = {net.name: net.net_id for net in job.nets}
    nets = {net.name: net for net in job.nets}
    tracks: list[Track] = []
    vias: list[Via] = []
    owner: dict[str, str] = {}
    for group in sorted(kept):
        for done in kept[group]:
            for run in done.runs:
                for p, q in zip(run.points, run.points[1:], strict=False):
                    geometry = (p.x, p.y, q.x, q.y, run.width, run.layer)
                    track = Track(
                        id=derived_id("trk", "roles", content_hash(group, run.net, geometry)),
                        start=p,
                        end=q,
                        width=run.width,
                        layer=run.layer,
                        net_id=net_ids.get(run.net),
                        locked=True,
                    )
                    if track.id not in owner:
                        owner[track.id] = group
                        tracks.append(track)
            net = nets.get(done.route.net)
            for point in done.vias:
                if net is None:
                    continue
                layers = (job.layers[0], job.layers[-1])
                geometry = (point.x, point.y, net.via_diameter, net.via_drill, layers, "through")
                via = Via(
                    id=derived_id("via", "roles", content_hash(group, net.name, geometry)),
                    position=point,
                    diameter=net.via_diameter,
                    drill=net.via_drill,
                    layers=layers,
                    net_id=net.net_id,
                    locked=True,
                )
                if via.id not in owner:
                    owner[via.id] = group
                    vias.append(via)
    return tracks, vias, owner


def _copper_check(
    job: RoutingJob, tracks: Sequence[Track], vias: Sequence[Via], owner: Mapping[str, str]
) -> dict[str, str]:
    """The groups whose copper a new finding of the copper check names, with the finding."""
    check = job.extra.get("copper_check")
    if not callable(check) or not (tracks or vias):
        return {}
    judge = cast("Callable[[object], Sequence[tuple[str, str, tuple[str, ...], int]]]", check)
    try:
        after = apply(job.design, RoutingResult(tracks=tuple(tracks), vias=tuple(vias)))
    except RoutingError:
        return {}
    found: dict[str, str] = {}
    for code, layer, items, gap in fresh(judge(job.design), judge(after)):
        for item in items:
            group = owner.get(item)
            if group is not None and group not in found:
                apart_text = f" ({format_length(gap)} apart)" if gap else ""
                found[group] = f"the copper check finds {code} on {layer}{apart_text}"
    return found


def _role_check(
    job: RoutingJob, tracks: Sequence[Track], vias: Sequence[Via], owner: Mapping[str, str]
) -> dict[str, str]:
    """The groups whose role findings get worse with the job's copper (design decision 13), with the
    finding: a code the group did not have, or the same code with a larger measure. ``roles.loop-open``
    counts as no finding."""
    check = job.extra.get("role_check")
    groups = set(owner.values())
    if not callable(check) or not groups:
        return {}
    judge = cast(RoleCheck, check)
    try:
        after_design = apply(job.design, RoutingResult(tracks=tuple(tracks), vias=tuple(vias)))
    except RoutingError:
        return {}

    def worst(found: Sequence[RoleFinding]) -> dict[tuple[str, str], int | None]:
        held: dict[tuple[str, str], int | None] = {}
        for code, group, _severity, measure in found:
            if code == "roles.loop-open" or group not in groups:
                continue
            key = (group, code)
            old = held.get(key)
            held[key] = measure if old is None or (measure is not None and measure > old) else old
        return held

    before, after = worst(judge(job.design)), worst(judge(after_design))
    found: dict[str, str] = {}
    for (group, code), measure in sorted(after.items()):
        if group in found:
            continue
        if (group, code) not in before:
            found[group] = f"{code} appears" + (f" ({measure})" if measure is not None else "")
        else:
            old = before[(group, code)]
            if measure is not None and old is not None and measure > old:
                found[group] = f"{code} grows from {old} to {measure}"
    return found


__all__ = [
    "OPTIONS",
    "Options",
    "RoleCheck",
    "RoleFinding",
    "RoleWorld",
    "corridor_rings",
    "refusal",
    "role_options",
    "route_roles",
    "via_ring",
    "z_shapes",
]
