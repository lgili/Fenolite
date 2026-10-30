# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A built-in router of short connections in 0°, 45° and 90° segments (capability routing, "Octilinear
router plugin" and the requirements after it; change c0228; ``docs/routing.md``, "octilinear").

Each open connection of a net (an edge of a minimum spanning tree over its pads, pads joined by the net's
copper counting as one group) is tried with five shapes between the two pad centres, each on every allowed
copper layer before the next: straight, 45° then straight, straight then 45°, and the two L shapes, after
the pattern routing of S-0837 (routes of one or two bends tried in a fixed order). The first shape that
keeps the clearance in force from every other net's copper and hole, keeps the edge clearance and makes no
acute angle with the net's tracks at its ends is placed. Connections that fail for lack of room go first
in the next round, which starts again without the job's copper (rip-up and reroute, S-0838). A
differential pair is routed as two tracks offset from one centre shape. Nothing here is taken from any
router's code.

The command gives the job the clearance in force (``extra["clearance"]``) and the copper check
(``extra["copper_check"]``), which this package may not import; the check judges the result, and the
copper of a connection that brings a new finding is removed (``route.check-refused``).

A job with subjects (``RoutingJob.subjects``, change c0280) is answered by ``routing.propose`` with candidates
and nothing merged. A job with role routes (``RoutingJob.roles``, change c0244) is routed by
``routing.roleroute`` instead, on
this module's world, shapes and pair offsets: ``World``, ``Pad``, ``PairConn``, ``pair_lines``, ``thick``,
``length``, ``apart`` and ``unit`` are shared with it and stay internal to the routing package.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, format_length, parse_length
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import (
    BBox,
    GeometryError,
    SpatialIndex,
    Thick,
    round_point,
    thick_bbox,
    thick_closer_than,
    touch_groups,
)
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.model.pairs import pair_base
from fenolite.model.rules import RuleSubject, Selector
from fenolite.routing.layers import DEFAULT_CLASS
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import JobNet, JobPair, Router, RouterStatus, RoutingJob, RoutingResult

MAX_LENGTH: Nm = 20_000_000
"""The default of ``--router-option max-length``: no shape longer than this is tried."""
ROUNDS = 3
"""The default of ``--router-option rounds``."""
MARGIN: Nm = 2_000
"""Added to the clearance in force against other nets' copper: KiCad approximates some pad shapes."""
ARC_TOL: Nm = 1_000
"""The chord error of an arc's polygon; the arc is widened by twice this."""
OPTIONS = ("max-length", "rounds")
EVIDENCE = Evidence(hypotheses=("H-G-OCTI-CHECK", "H-K-OCTI-DRC"))
"""A route is ``UNVERIFIED`` until KiCad checks it; the rows name what the benches showed: the copper check
finds nothing new on the result (``H-G-OCTI-CHECK``), nor does KiCad's DRC (``H-K-OCTI-DRC``)."""
Finding = tuple[str, str, tuple[str, ...], int]
"""A finding of the copper check: its code, layer, sorted item ids and gap in nanometres."""
CopperCheck = Callable[[Design], Sequence[Finding]]
Clearance = Callable[[RuleSubject, RuleSubject], Nm]
Polyline = tuple[Point, ...]
_ALL = Selector("all")
Dir = tuple[int, int]


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _cross(u: Dir, v: Dir) -> int:
    return u[0] * v[1] - u[1] * v[0]


def _dot(u: Dir, v: Dir) -> int:
    return u[0] * v[0] + u[1] * v[1]


def _vec(a: Point, b: Point) -> Dir:
    return (b.x - a.x, b.y - a.y)


def unit(a: Point, b: Point) -> Dir:
    """The octilinear direction from ``a`` to ``b`` as signs per axis."""
    return (_sign(b.x - a.x), _sign(b.y - a.y))


def length(points: Polyline) -> int:
    return sum(isqrt((q.x - p.x) ** 2 + (q.y - p.y) ** 2) for p, q in zip(points, points[1:], strict=False))


def _octilinear(a: Point, b: Point) -> bool:
    dx, dy = abs(b.x - a.x), abs(b.y - a.y)
    return dx == 0 or dy == 0 or dx == dy


def shapes(a: Point, b: Point) -> tuple[Polyline, ...]:
    """The shapes between ``a`` and ``b`` in the order they are tried: straight (when ``a`` and ``b`` lie on
    one 0°, 45° or 90° line), 45° then straight, straight then 45°, the L through ``(b.x, a.y)`` and the L
    through ``(a.x, b.y)``; equal shapes once."""
    if a == b:
        return ()
    dx, dy = b.x - a.x, b.y - a.y
    sx, sy = _sign(dx), _sign(dy)
    d = min(abs(dx), abs(dy))
    found: list[Polyline] = []
    if _octilinear(a, b):
        found.append((a, b))
    else:
        found.append((a, Point(a.x + sx * d, a.y + sy * d), b))
        found.append((a, Point(b.x - sx * d, b.y - sy * d), b))
    if dx and dy:
        found.append((a, Point(b.x, a.y), b))
        found.append((a, Point(a.x, b.y), b))
    unique: list[Polyline] = []
    for shape in found:
        if shape not in unique:
            unique.append(shape)
    return tuple(unique)


def simplify(points: Iterable[Point]) -> Polyline:
    """``points`` without repeated points and without the middle of three points on one straight run."""
    out: list[Point] = []
    for point in points:
        if out and out[-1] == point:
            continue
        if len(out) >= 2 and unit(out[-2], out[-1]) == unit(out[-1], point):
            out[-1] = point
            continue
        out.append(point)
    return tuple(out)


def bends_ok(points: Polyline) -> bool:
    """True when every segment of ``points`` runs at a multiple of 45° and no joint is acute."""
    if any(not _octilinear(p, q) for p, q in zip(points, points[1:], strict=False)):
        return False
    for p, q, r in zip(points, points[1:], points[2:], strict=False):
        if _dot(unit(p, q), unit(q, r)) < 0:
            return False
    return True


def _off(direction: Dir, distance: int) -> Dir:
    """``direction`` scaled to at least ``distance`` (a diagonal's axes rounded up)."""
    if direction[0] == 0 or direction[1] == 0:
        return (direction[0] * distance, direction[1] * distance)
    k = isqrt(2 * distance * distance) // 2 + 1
    return (direction[0] * k, direction[1] * k)


def _add(p: Point, v: Dir, scale: int = 1) -> Point:
    return Point(p.x + scale * v[0], p.y + scale * v[1])


def _meet(a: Point, u: Dir, c: Point, v: Dir) -> tuple[Fraction, Point] | None:
    """Where the line ``a + t·u`` meets the line ``c + s·v``: ``t`` and the point rounded to nanometres."""
    den = _cross(u, v)
    if den == 0:
        return None
    t = Fraction(_cross(_vec(a, c), v), den)
    return t, round_point(a.x + t * u[0], a.y + t * u[1])


def offset(centre: Polyline, side: int, half: int) -> Polyline:
    """``centre`` moved by ``half`` to the side ``side`` (+1: its left normal), joints at the meet of the
    moved segments."""
    dirs = [unit(p, q) for p, q in zip(centre, centre[1:], strict=False)]
    moved = [_add(centre[i], _off((-d[1], d[0]), half), side) for i, d in enumerate(dirs)]
    points = [moved[0]]
    for i in range(1, len(dirs)):
        found = _meet(moved[i - 1], dirs[i - 1], moved[i], dirs[i])
        points.append(found[1] if found is not None else moved[i])
    points.append(_add(centre[-1], _off((-dirs[-1][1], dirs[-1][0]), half), side))
    return tuple(points)


@dataclass(frozen=True, slots=True)
class Pad:
    label: str
    net: str
    at: Point
    layers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Obstacle:
    shape: Thick
    net: str | None
    subject: RuleSubject
    box: BBox


@dataclass(frozen=True, slots=True)
class _Single:
    key: int
    net: JobNet
    a: Pad
    b: Pad


@dataclass(frozen=True, slots=True)
class PairConn:
    key: int
    pair: JobPair
    positive: JobNet
    negative: JobNet
    ends: tuple[tuple[Pad, Pad], tuple[Pad, Pad]]
    """The two ends, each ``(positive pad, negative pad)``."""


_Conn = _Single | PairConn


@dataclass(frozen=True, slots=True)
class _Placed:
    """The copper of one routed connection: per net name, its layer, width and polyline."""

    key: int
    runs: tuple[tuple[JobNet, str, Nm, Polyline], ...]


@dataclass
class _Round:
    placed: list[_Placed] = field(default_factory=lambda: [])
    room: list[_Conn] = field(default_factory=lambda: [])
    long: list[_Conn] = field(default_factory=lambda: [])


def thick(points: Sequence[Point], width: int, filled: bool = False) -> Thick | None:
    try:
        return Thick(tuple(points), width, filled)
    except (GeometryError, ValueError):
        return None


class World:
    """The obstacles of a job: other nets' copper and holes per layer, the edge rings, and the job copper
    placed in the round so far."""

    def __init__(self, job: RoutingJob, pads: Sequence[object], outline: Sequence[Sequence[Point]]) -> None:
        design = job.design
        board = design.board
        assert board is not None
        self.layers = job.layers
        self.planes = frozenset(job.plane_layers)
        net_ids = {net.id: net for net in design.circuit.nets}
        classes = {item.id: item for item in design.circuit.netclasses}
        default = next(
            (item for item in design.circuit.netclasses if item.name.casefold() == "default"), None
        )
        self.class_of: dict[str, str | None] = {
            net.name: (classes[net.netclass_id].name if net.netclass_id in classes else DEFAULT_CLASS)
            for net in design.circuit.nets
        }
        self.class_clearance: dict[str, Nm] = {
            net.name: (
                getattr(classes.get(net.netclass_id or ""), "clearance", None)
                or getattr(default, "clearance", None)
                or 0
            )
            for net in design.circuit.nets
        }
        given = job.extra.get("clearance")
        self._given: Clearance | None = cast(Clearance, given) if callable(given) else None
        self._memo: dict[tuple[RuleSubject, RuleSubject], Nm] = {}
        self.job_clearance = {net.name: net.clearance for net in job.nets}
        self.edge = _edge_clearance(design)
        self.edges = tuple(
            shape
            for ring in outline
            if len(ring) >= 2
            and (shape := thick((*ring, ring[0]) if ring[0] != ring[-1] else tuple(ring), 0)) is not None
        )
        found: list[tuple[str, _Obstacle]] = []
        self.pads: dict[str, list[Pad]] = {}
        self.pad_shapes: dict[str, list[list[tuple[str, Thick]]]] = {}
        for pad in pads:
            net = cast(str | None, getattr(pad, "net", None))
            ref = cast(str, getattr(pad, "ref", ""))
            number = cast(str, getattr(pad, "number", ""))
            copper = cast("tuple[object, ...]", getattr(pad, "copper", ()))
            entries: list[tuple[str, Thick]] = []
            for entry in copper:
                layer = cast(str, getattr(entry, "layer", ""))
                shape = thick(
                    cast("tuple[Point, ...]", getattr(entry, "core", ())),
                    cast(int, getattr(entry, "width", 0)),
                    cast(bool, getattr(entry, "filled", False)),
                )
                if shape is None:
                    continue
                entries.append((layer, shape))
                found.append(
                    (
                        layer,
                        self._obstacle(
                            shape, net, RuleSubject("pad", net, self.class_of.get(net or ""), ref, layer)
                        ),
                    )
                )
            hole = cast("tuple[Point, ...]", getattr(pad, "hole", ()))
            drill = cast("int | None", getattr(pad, "drill", None))
            if hole and drill:
                shape = thick(hole, drill)
                if shape is not None:
                    for layer in self.layers:
                        found.append(
                            (
                                layer,
                                self._obstacle(
                                    shape,
                                    net,
                                    RuleSubject("pad", net, self.class_of.get(net or ""), ref, layer),
                                ),
                            )
                        )
            if net and entries:
                position = cast(Point, getattr(pad, "position", None))
                layers = tuple(layer for layer in self.layers if any(name == layer for name, _ in entries))
                self.pads.setdefault(net, []).append(Pad(f"{ref}-{number}", net, position, layers))
                self.pad_shapes.setdefault(net, []).append(entries)
        self.ends: dict[tuple[str, str, Point], list[Dir]] = {}
        self.net_copper: dict[str, list[list[tuple[str, Thick]]]] = {}
        for track in board.tracks:
            net = net_ids[track.net_id].name if track.net_id in net_ids else None
            shape = thick((track.start, track.end), track.width)
            if shape is None:
                continue
            found.append(
                (
                    track.layer,
                    self._obstacle(
                        shape, net, RuleSubject("track", net, self.class_of.get(net or ""), layer=track.layer)
                    ),
                )
            )
            if net:
                self.net_copper.setdefault(net, []).append([(track.layer, shape)])
                if track.start != track.end:
                    self.ends.setdefault((net, track.layer, track.start), []).append(
                        _vec(track.start, track.end)
                    )
                    self.ends.setdefault((net, track.layer, track.end), []).append(
                        _vec(track.end, track.start)
                    )
        for arc in board.arcs:
            net = net_ids[arc.net_id].name if arc.net_id in net_ids else None
            try:
                points = GeoArc(arc.start, arc.mid, arc.end).polygonize(ARC_TOL)
            except (GeometryError, ValueError):
                points = (arc.start, arc.mid, arc.end)
            shape = thick(points, arc.width + 2 * ARC_TOL)
            if shape is None:
                continue
            found.append(
                (
                    arc.layer,
                    self._obstacle(
                        shape, net, RuleSubject("track", net, self.class_of.get(net or ""), layer=arc.layer)
                    ),
                )
            )
            if net:
                self.net_copper.setdefault(net, []).append([(arc.layer, shape)])
        for via in board.vias:
            net = net_ids[via.net_id].name if via.net_id in net_ids else None
            span = self.span(via.layers)
            disc = thick((via.position,), via.diameter)
            if disc is None:
                continue
            for layer in span:
                found.append(
                    (
                        layer,
                        self._obstacle(
                            disc, net, RuleSubject("via", net, self.class_of.get(net or ""), layer=layer)
                        ),
                    )
                )
            if net:
                self.net_copper.setdefault(net, []).append([(layer, disc) for layer in span])
        self.by_layer: dict[str, list[_Obstacle]] = {layer: [] for layer in self.layers}
        for layer, obstacle in found:
            self.by_layer.setdefault(layer, []).append(obstacle)
        self.reach = max([*self.class_clearance.values(), *self.job_clearance.values(), 0]) * 2 + 1_000_000
        self.index = {
            layer: SpatialIndex[int].build((item.box, i) for i, item in enumerate(items))
            for layer, items in self.by_layer.items()
        }
        self.placed: list[tuple[str, str, Thick, RuleSubject]] = []

    def _obstacle(self, shape: Thick, net: str | None, subject: RuleSubject) -> _Obstacle:
        return _Obstacle(shape, net, subject, thick_bbox(shape))

    def span(self, layers: Sequence[str]) -> tuple[str, ...]:
        """The job layers from the first to the last of ``layers`` in stack order."""
        found = [self.layers.index(layer) for layer in layers if layer in self.layers]
        if not found:
            return ()
        return self.layers[min(found) : max(found) + 1]

    def clearance(self, a: RuleSubject, b: RuleSubject) -> Nm:
        """The clearance in force between ``a`` and ``b``: the command's, else the larger class value."""
        key = (a, b)
        if key not in self._memo:
            if self._given is not None:
                value = self._given(a, b)
            else:
                value = max(
                    self.job_clearance.get(a.net or "", 0),
                    self.job_clearance.get(b.net or "", 0),
                    self.class_clearance.get(a.net or "", 0),
                    self.class_clearance.get(b.net or "", 0),
                )
            self._memo[key] = value
        return self._memo[key]

    def subject(self, net: str, layer: str, pair: str | None = None) -> RuleSubject:
        return RuleSubject("track", net, self.class_of.get(net), layer=layer, diff_pair=pair)

    def fits(self, net: str, layer: str, points: Polyline, width: Nm, pair: str | None = None) -> bool:
        """True when every segment of ``points`` keeps the clearance in force plus ``MARGIN`` from every
        other net's item on ``layer`` and from the job copper, and the edge clearance from the outline."""
        mine = self.subject(net, layer, pair)
        items = self.by_layer.get(layer, [])
        tree = self.index.get(layer)
        for p, q in zip(points, points[1:], strict=False):
            shape = thick((p, q), width)
            if shape is None:
                return False
            box = thick_bbox(shape).inflate(self.reach)
            for i in tree.query(box) if tree is not None else ():
                item = items[i]
                if item.net == net:
                    continue
                if thick_closer_than(shape, item.shape, self.clearance(mine, item.subject) + MARGIN):
                    return False
            for other, on, placed, subject in self.placed:
                if other == net or on != layer:
                    continue
                if thick_closer_than(shape, placed, self.clearance(mine, subject) + MARGIN):
                    return False
            for ring in self.edges:
                if thick_closer_than(shape, ring, max(self.edge, 1)):
                    return False
        return True

    def ends_ok(self, net: str, layer: str, points: Polyline) -> bool:
        """True when no end of ``points`` makes an acute angle with a track of ``net`` that ends there."""
        for end, toward in ((points[0], points[1]), (points[-1], points[-2])):
            out = _vec(end, toward)
            if any(_dot(out, other) > 0 for other in self.ends.get((net, layer, end), ())):
                return False
        return True

    def place(self, net: str, layer: str, points: Polyline, width: Nm, pair: str | None = None) -> None:
        subject = self.subject(net, layer, pair)
        for p, q in zip(points, points[1:], strict=False):
            shape = thick((p, q), width)
            if shape is not None:
                self.placed.append((net, layer, shape, subject))
        self.ends.setdefault((net, layer, points[0]), []).append(_vec(points[0], points[1]))
        self.ends.setdefault((net, layer, points[-1]), []).append(_vec(points[-1], points[-2]))

    def reset(self, ends: dict[tuple[str, str, Point], list[Dir]]) -> None:
        self.placed = []
        self.ends = {key: list(value) for key, value in ends.items()}


def _edge_clearance(design: Design) -> Nm:
    """The largest ``min`` of the board-wide ``edge_clearance`` rules of ``design``, or 0."""
    rules = design.rules.rules if design.rules is not None else ()
    return max(
        (
            rule.min
            for rule in rules
            if rule.kind == "edge_clearance"
            and rule.severity != "ignore"
            and rule.min is not None
            and rule.selector_a == _ALL
            and rule.selector_b is None
        ),
        default=0,
    )


def _layers(net: JobNet, world: World, *pads: Pad) -> tuple[str, ...]:
    return tuple(
        layer
        for layer in world.layers
        if layer not in world.planes
        and (net.layers is None or layer in net.layers)
        and all(layer in pad.layers for pad in pads)
    )


def _connections(net: JobNet, world: World) -> list[tuple[Pad, Pad]]:
    """The edges of a minimum spanning tree over the pads of ``net`` between the groups its copper makes,
    shortest first."""
    pads = world.pads.get(net.name, [])
    if len(pads) < 2:
        return []
    items: list[list[tuple[str, Thick]]] = [*world.pad_shapes[net.name], *world.net_copper.get(net.name, [])]
    groups = touch_groups(items)[: len(pads)]
    parent = {group: group for group in groups}

    def find(group: int) -> int:
        while parent[group] != group:
            group = parent[group]
        return group

    edges = sorted(
        (
            (pads[i].at.x - pads[j].at.x) ** 2 + (pads[i].at.y - pads[j].at.y) ** 2,
            *sorted((pads[i].label, pads[j].label)),
            i,
            j,
        )
        for i in range(len(pads))
        for j in range(i + 1, len(pads))
    )
    chosen: list[tuple[Pad, Pad]] = []
    for _, _, _, i, j in edges:
        a, b = find(groups[i]), find(groups[j])
        if a == b:
            continue
        parent[max(a, b)] = min(a, b)
        first, second = sorted((pads[i], pads[j]), key=lambda pad: pad.label)
        chosen.append((first, second))
    return chosen


class OctilinearRouter:
    """Routes short connections with five 0°/45°/90° shapes per connection in clearance, in rounds; pairs
    as two offset tracks. No via, no process."""

    name = "octilinear"
    description = (
        "Routes short connections, such as gate loops and sense pairs, in 0, 45 and 90 degree segments that "
        "keep the clearance; no via; each result is judged by the copper check."
    )
    sends_data_offsite = False
    features = frozenset({"pairs", "short", "roles", "propose"})

    def available(self) -> RouterStatus:
        """This built-in router is always available and uses no external tool."""
        return RouterStatus(True, version="builtin")

    def route(self, job: RoutingJob) -> RoutingResult:
        """Route the job's nets and pairs, or its role routes only when it has any (``routing.roleroute``);
        the result is ``UNVERIFIED`` until KiCad checks it."""
        issues: list[Issue] = []
        plain = not job.roles and not job.subjects
        max_length, rounds = _options(job.options, issues) if plain else (MAX_LENGTH, ROUNDS)
        pads = job.extra.get("board_pads")
        outline = job.extra.get("outline")
        if not isinstance(pads, tuple) or job.design.board is None:
            names = tuple(net.name for net in job.nets)
            issues.append(
                Issue(
                    "route.tool-failed",
                    "error",
                    "the octilinear router needs the board-frame pads (RoutingJob.extra['board_pads'])",
                    names[0] if names else "",
                )
            )
            return self._result((), (), names, issues)
        rings = cast("tuple[tuple[Point, ...], ...]", outline) if isinstance(outline, tuple) else ()
        world = World(job, cast("tuple[object, ...]", pads), rings)
        if job.subjects:  # proposal mode (change c0280): candidates only, nothing merged
            from fenolite.routing.propose import propose

            return propose(job, world, cast("tuple[object, ...]", pads), self.name)
        if job.roles:  # role mode (change c0244): the role routes and nothing else
            from fenolite.routing.roleroute import route_roles

            return route_roles(job, world, cast("tuple[object, ...]", pads), self.name)
        conns, routed_free = self._plan(job, world, issues)
        base_ends = {key: list(value) for key, value in world.ends.items()}
        order: list[_Conn] = list(conns)
        best: _Round | None = None
        for _ in range(rounds):
            world.reset(base_ends)
            done = _Round()
            for conn in order:
                outcome = _route_one(conn, world, max_length)
                if isinstance(outcome, _Placed):
                    done.placed.append(outcome)
                elif outcome == "long":
                    done.long.append(conn)
                else:
                    done.room.append(conn)
            if best is None or len(done.placed) > len(best.placed):
                best = done
            if not done.room:
                break
            again = [*done.room, *(conn for conn in order if conn not in done.room)]
            if again == order:
                break
            order = again
        assert best is not None or not conns
        final = best or _Round()
        tracks, owner = _tracks(final.placed)
        refused = _judge(job, tracks, owner, issues)
        if refused:
            final.placed = [item for item in final.placed if item.key not in refused]
            tracks, owner = _tracks(final.placed)
        for conn in sorted([*final.room, *final.long], key=lambda item: item.key):
            issues.append(_failed(conn, conn in final.long, max_length))
        done_keys = {item.key for item in final.placed}
        open_nets: set[str] = set()
        for conn in conns:
            if conn.key not in done_keys:
                if isinstance(conn, _Single):
                    open_nets.add(conn.net.name)
                else:
                    open_nets.update((conn.positive.name, conn.negative.name))
        names = [net.name for net in job.nets]
        routed = tuple(name for name in names if name not in open_nets and name not in routed_free)
        unrouted = tuple(name for name in names if name in open_nets or name in routed_free)
        return self._result(tracks, routed, unrouted, issues)

    def _plan(self, job: RoutingJob, world: World, issues: list[Issue]) -> tuple[list[_Conn], set[str]]:
        """The connections of the job, pairs first by their positive net, and the nets left open before
        routing (pairs that cannot be routed)."""
        conns: list[_Conn] = []
        left: set[str] = set()
        by_name = {net.name: net for net in job.nets}
        in_pair: set[str] = set()
        for pair in job.pairs:
            positive, negative = by_name.get(pair.positive), by_name.get(pair.negative)
            if positive is None or negative is None:
                continue
            in_pair.update((pair.positive, pair.negative))
            p_pads, n_pads = world.pads.get(pair.positive, []), world.pads.get(pair.negative, [])
            if len(p_pads) != 2 or len(n_pads) != 2:
                left.update((pair.positive, pair.negative))
                issues.append(
                    _pair_issue(pair, f"its nets have {len(p_pads)} and {len(n_pads)} pads, not two each")
                )
                continue
            ends = _pair_ends(p_pads, n_pads)
            conns.append(PairConn(len(conns), pair, positive, negative, ends))
        for net in job.nets:
            if net.name in in_pair:
                continue
            if len(world.pads.get(net.name, [])) < 2:
                left.add(net.name)
                continue
            for a, b in _connections(net, world):
                conns.append(_Single(len(conns), net, a, b))
        return conns, left

    def _result(
        self, tracks: Sequence[Track], routed: Sequence[str], unrouted: Sequence[str], issues: list[Issue]
    ) -> RoutingResult:
        return RoutingResult(
            tracks=tuple(tracks),
            routed=tuple(routed),
            unrouted=tuple(unrouted),
            issues=tuple(issues),
            tool=self.name,
            tool_version="builtin",
            evidence=EVIDENCE,
        )


def _options(options: Mapping[str, str], issues: list[Issue]) -> tuple[Nm, int]:
    max_length, rounds = MAX_LENGTH, ROUNDS
    for key, value in sorted(options.items()):
        if key == "max-length":
            try:
                parsed = parse_length(value, default_unit="mm")
            except ValueError:
                parsed = 0
            if parsed > 0:
                max_length = parsed
                continue
        elif key == "rounds" and value.isdigit() and int(value) >= 1:
            rounds = int(value)
            continue
        why = "an unknown option" if key not in OPTIONS else f"{value!r} is no valid value"
        issues.append(
            Issue(
                "route.option-ignored",
                "warning",
                f"the router option {key} is ignored by the octilinear router: {why}",
                key,
                hint="the octilinear router takes max-length=LENGTH and rounds=N (a positive integer)",
            )
        )
    return max_length, rounds


def _pair_ends(p_pads: list[Pad], n_pads: list[Pad]) -> tuple[tuple[Pad, Pad], tuple[Pad, Pad]]:
    """The matching of the positive and negative pads with the smaller sum of distances, the end whose
    positive pad label sorts first first."""

    def dist(a: Pad, b: Pad) -> int:
        return isqrt((a.at.x - b.at.x) ** 2 + (a.at.y - b.at.y) ** 2)

    straight = dist(p_pads[0], n_pads[0]) + dist(p_pads[1], n_pads[1])
    crossed = dist(p_pads[0], n_pads[1]) + dist(p_pads[1], n_pads[0])
    if crossed < straight:
        n_pads = [n_pads[1], n_pads[0]]
    ends = sorted(((p_pads[0], n_pads[0]), (p_pads[1], n_pads[1])), key=lambda end: end[0].label)
    return ends[0], ends[1]


def _route_one(conn: _Conn, world: World, max_length: Nm) -> _Placed | str:
    """The copper of ``conn`` placed in ``world``, or ``"long"`` when every shape is longer than
    ``max_length``, or ``"room"`` when no shape fits."""
    if isinstance(conn, _Single):
        return _route_single(conn, world, max_length)
    return _route_pair(conn, world, max_length)


def _route_single(conn: _Single, world: World, max_length: Nm) -> _Placed | str:
    net = conn.net
    layers = _layers(net, world, conn.a, conn.b)
    short = [shape for shape in shapes(conn.a.at, conn.b.at) if length(shape) <= max_length]
    if not short:
        return "long"
    for shape in short:
        for layer in layers:
            if world.ends_ok(net.name, layer, shape) and world.fits(net.name, layer, shape, net.width):
                world.place(net.name, layer, shape, net.width)
                return _Placed(conn.key, ((net, layer, net.width, shape),))
    return "room"


def _entry(pad: Point, at: Point, direction: Dir, *, into: bool) -> Polyline | None:
    """The first shape from ``pad`` to ``at`` (``into``) or from ``at`` to ``pad`` whose joint with a coupled
    segment of ``direction`` at ``at`` is not acute; ``(pad,)`` when they are one point."""
    if pad == at:
        return (pad,)
    for shape in shapes(pad, at) if into else shapes(at, pad):
        joint = unit(shape[-2], shape[-1]) if into else unit(shape[0], shape[1])
        if _dot(joint, direction) >= 0:
            return shape
    return None


def _start(pad: Point, side: int, line: Point, direction: Dir) -> Point | None:
    """Where an entry from ``pad``, on the side ``side`` of the centre line, going along ``direction`` and
    toward the centre line at 45° to it, meets the offset line ``line + t·direction``; ``None`` when it meets
    it behind ``line`` (the pads lie no wider apart than the pitch)."""
    normal = (-direction[1], direction[0])
    way = (direction[0] - side * normal[0], direction[1] - side * normal[1])
    found = _meet(pad, way, line, direction)
    if found is None:
        return None
    t, point = found
    return point if t > 0 else None


def pair_lines(conn: PairConn, centre: Polyline, half: int, trim: bool) -> tuple[Polyline, Polyline] | None:
    """The positive and negative polylines of a pair along ``centre``, or ``None``."""
    (p1, n1), (p2, n2) = conn.ends
    first, last = unit(centre[0], centre[1]), unit(centre[-2], centre[-1])
    s1 = _sign(_cross(first, _vec(centre[0], p1.at)))
    s2 = _sign(_cross(last, _vec(centre[-1], p2.at)))
    if s1 == 0 or s1 != s2:
        return None
    lines: list[Polyline] = []
    for side, a, b in ((s1, p1, p2), (-s1, n1, n2)):
        moved = offset(centre, side, half)
        start, end = moved[0], moved[-1]
        if trim:
            start = _start(a.at, side, moved[0], first) or moved[0]
            end = _start(b.at, -side, moved[-1], (-last[0], -last[1])) or moved[-1]
        inner = list(moved[1:-1])
        if not inner and (start == end or unit(start, end) != first):
            return None
        if inner and (_dot(_vec(start, inner[0]), first) <= 0 or _dot(_vec(inner[-1], end), last) <= 0):
            return None
        head = _entry(a.at, start, first, into=True)
        tail = _entry(b.at, end, last, into=False)
        if head is None or tail is None:
            return None
        line = simplify((*head, *inner, *tail))
        if len(line) < 2 or not bends_ok(line):
            return None
        lines.append(line)
    return lines[0], lines[1]


def _route_pair(conn: PairConn, world: World, max_length: Nm) -> _Placed | str:
    pair = conn.pair
    (p1, n1), (p2, n2) = conn.ends
    layers = _layers(conn.positive, world, p1, n1, p2, n2)
    m1 = Point((p1.at.x + n1.at.x) // 2, (p1.at.y + n1.at.y) // 2)
    m2 = Point((p2.at.x + n2.at.x) // 2, (p2.at.y + n2.at.y) // 2)
    half = (pair.width + pair.gap + 1) // 2 + 1
    base = pair_base(pair.positive, pair.negative)
    built = short = False
    for centre in shapes(m1, m2):
        for trim in (True, False):
            lines = pair_lines(conn, centre, half, trim)
            if lines is None:
                continue
            built = True
            positive, negative = lines
            if length(positive) > max_length or length(negative) > max_length:
                continue
            short = True
            for layer in layers:
                if not (
                    world.ends_ok(pair.positive, layer, positive)
                    and world.ends_ok(pair.negative, layer, negative)
                    and world.fits(pair.positive, layer, positive, pair.width, base)
                    and world.fits(pair.negative, layer, negative, pair.width, base)
                    and apart(world, pair, layer, positive, negative, base)
                ):
                    continue
                world.place(pair.positive, layer, positive, pair.width, base)
                world.place(pair.negative, layer, negative, pair.width, base)
                return _Placed(
                    conn.key,
                    (
                        (conn.positive, layer, pair.width, positive),
                        (conn.negative, layer, pair.width, negative),
                    ),
                )
    return "long" if built and not short else "room"


def apart(world: World, pair: JobPair, layer: str, a: Polyline, b: Polyline, base: str | None) -> bool:
    """True when the two tracks of a pair keep the clearance in force between its nets, with no margin."""
    limit = world.clearance(
        world.subject(pair.positive, layer, base), world.subject(pair.negative, layer, base)
    )
    pieces_a = [thick((p, q), pair.width) for p, q in zip(a, a[1:], strict=False)]
    pieces_b = [thick((p, q), pair.width) for p, q in zip(b, b[1:], strict=False)]
    for one in pieces_a:
        for other in pieces_b:
            if one is None or other is None or thick_closer_than(one, other, limit):
                return False
    return True


def _tracks(placed: Sequence[_Placed]) -> tuple[list[Track], dict[str, int]]:
    """The tracks of ``placed`` with their ids, and the connection key of each id."""
    tracks: list[Track] = []
    owner: dict[str, int] = {}
    for item in placed:
        for net, layer, width, points in item.runs:
            for p, q in zip(points, points[1:], strict=False):
                geometry = (p.x, p.y, q.x, q.y, width, layer)
                track = Track(
                    id=derived_id("trk", "routing", content_hash(net.name, geometry)),
                    start=p,
                    end=q,
                    width=width,
                    layer=layer,
                    net_id=net.net_id,
                )
                if track.id in owner:
                    continue
                owner[track.id] = item.key
                tracks.append(track)
    return tracks, owner


def fresh(before: Iterable[Finding], after: Iterable[Finding]) -> list[Finding]:
    """The findings of ``after`` that ``before`` lacks: a new pair of items, or a smaller gap of a known
    pair."""
    known: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for code, layer, items, gap in before:
        key = (code, layer, items)
        known[key] = min(gap, known.get(key, gap))
    return sorted(
        found
        for found in after
        if (key := (found[0], found[1], found[2])) not in known or found[3] < known[key]
    )


def _judge(
    job: RoutingJob, tracks: Sequence[Track], owner: Mapping[str, int], issues: list[Issue]
) -> set[int]:
    """The connections whose copper a new finding of the copper check names, each with one
    ``route.check-refused``; empty without a check or without copper."""
    check = job.extra.get("copper_check")
    if not callable(check) or not tracks:
        return set()
    judge = cast(CopperCheck, check)
    try:
        after_design = apply(job.design, RoutingResult(tracks=tuple(tracks)))
    except RoutingError:
        return set()
    names = {track.id: track for track in tracks}
    net_names = {net.net_id: net.name for net in job.nets}
    refused: dict[int, Finding] = {}
    for found in fresh(judge(job.design), judge(after_design)):
        for item in found[2]:
            if item in owner and owner[item] not in refused:
                refused[owner[item]] = found
    for key, found in sorted(refused.items()):
        track = next(names[item] for item in found[2] if item in names and owner[item] == key)
        net = net_names.get(track.net_id or "", "")
        gap = f" ({format_length(found[3])} apart)" if found[3] else ""
        issues.append(
            Issue(
                "route.check-refused",
                "warning",
                f"the copper of a connection of net {net} was removed: the copper check finds {found[0]} on "
                f"{found[1]}{gap}",
                net,
                hint="give the connection room with fenolite place --move, or route it with another router",
            )
        )
    return set(refused)


def _failed(conn: _Conn, long: bool, max_length: Nm) -> Issue:
    if isinstance(conn, PairConn):
        why = (
            f"every shape is longer than max-length {format_length(max_length)}"
            if long
            else "no shape keeps the clearance"
        )
        return _pair_issue(conn.pair, why)
    where = f"{conn.a.label} to {conn.b.label}"
    if long:
        message = (
            f"the connection {where} of net {conn.net.name} stays open: every shape is longer than "
            f"max-length {format_length(max_length)}"
        )
        hint = "route it with another router, or raise --router-option max-length"
    else:
        message = f"the connection {where} of net {conn.net.name} stays open: no shape keeps the clearance"
        hint = "give it room with fenolite place --move, or route it with another router"
    return Issue("route.unrouted", "warning", message, conn.net.name, hint=hint)


def _pair_issue(pair: JobPair, why: str) -> Issue:
    return Issue(
        "route.pair-not-routed",
        "warning",
        f"the pair {pair.name} is not routed by the octilinear router: {why}",
        pair.name,
        hint="route the pair with another router that has the feature pairs, or give it room",
    )


_ROUTER: Router = OctilinearRouter()

__all__ = [
    "EVIDENCE",
    "MARGIN",
    "MAX_LENGTH",
    "ROUNDS",
    "Clearance",
    "CopperCheck",
    "Finding",
    "OctilinearRouter",
    "bends_ok",
    "fresh",
    "offset",
    "shapes",
    "simplify",
]
