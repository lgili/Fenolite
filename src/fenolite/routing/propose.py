# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proposal mode of the octilinear router: candidates for the subjects of a job (change c0280; capability
routing, "Candidates in a routing result" and the requirements after it; ``docs/routing.md``, "Proposals").

``OctilinearRouter.route`` calls ``propose`` when ``job.subjects`` is not empty and merges nothing. Each
subject gets candidates from these families, in this order, on the world of c0228 (other nets' copper and
holes, the board edge; zone fills are not obstacles, since a fill is poured again after routing):

1. ``shape``: c0228's five shapes on each allowed layer both ends reach;
2. ``z-shape``: c0244's Z shapes, whose middle lines come from the bounding boxes of the copper near the
   straight line;
3. ``via-l``: a shape of one bend whose bend is a through via of the net's class, the first leg on a layer of
   ``a``, the second on another layer of ``b``;
4. ``fanout`` (``fanout`` subjects): a neck and a via, searched as the plane fan-out of c0107 searches (the
   eight directions in the order of their angle to the outward direction, steps of a quarter via diameter,
   nine distances from the first that keeps the neck), the first passing position of each direction, the via
   inside the zone outline by half its diameter and inside the zone's copper (``extra["zone_copper"]``);
5. ``role`` (``group`` subjects): c0244's role mode on the group's routes with its defaults, then once per
   relaxation ``kelvin-vias=2``, ``gate-vias=2`` and ``keep-away=clearance``. Isolation is never relaxed.

A candidate passes c0228's acceptance (the clearance in force plus 2 µm, the edge, no acute joint with its
net's tracks) and is kept when it differs from every kept one by its layer set, its via count, or a centre
line farther than the clearance in force; the first ``candidates`` (default 4, at most 8) are kept. A subject
without one gets a reason (``no-room``, ``no-layer``, ``too-long``, ``near-switching``, ``isolation``,
``pads``) and the three first blockers in ``RoutingResult.refusals``. No score is given: the order is the
generation order. Nothing here is taken from any router's code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from math import isqrt
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, parse_length
from fenolite.geometry import Location, dist2_point_segment, point_in_ring, rotate_point
from fenolite.model.board import Track, Via
from fenolite.routing.octilinear import (
    EVIDENCE,
    MAX_LENGTH,
    Polyline,
    World,
    length,
    shapes,
    thick,
)
from fenolite.routing.protocol import Candidate, JobNet, JobRoleRoute, JobSubject, RoutingJob, RoutingResult
from fenolite.routing.roleroute import refusal, route_roles, z_shapes

CANDIDATES = 4
"""The default of ``--candidates``: candidates kept per subject."""
MAX_CANDIDATES = 8
FAMILIES = ("shape", "z-shape", "via-l", "fanout", "role")
"""The families of the octilinear router, in generation order."""
RELAXATIONS = ("kelvin-vias=2", "gate-vias=2", "keep-away=clearance")
"""The relaxations of the ``role`` family, one at a time, after its defaults; isolation is never relaxed."""
REASONS = ("no-room", "no-layer", "too-long", "near-switching", "isolation", "pads")
"""The reasons the router gives a subject without a candidate (the command adds ``all-rejected`` and
``budget``)."""
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (1, -1),
)
"""The eight directions of the fan-out search, ``k · 45°`` from +X (the plane fan-out's, c0107)."""
STEPS = 9
GRID = 1_000
"""Fan-out via centres lie on whole micrometres, as the plane fan-out's."""
REACH_LIMIT = 400
OPTIONS = ("candidates", "max-length")
ROLE_OPTIONS = ("rounds", "gate-vias", "kelvin-vias", "keep-away", "z-shapes")
"""The router options of the proposal mode, and those passed on to the ``role`` family."""
ZoneCopper = Callable[[str, str, Point, int], bool]
"""``extra["zone_copper"]``: whether the disc of a radius around a point lies in the zone copper of a net on a
layer (the saved fill, else the simulated pour); the command builds it from ``roles.proposals.ZoneCopper``."""


# --- items and ids ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Shape:
    """A candidate before its id: its runs (layer, polyline), its via points, family and relaxations, and
    for a ``role`` candidate its ready copper."""

    source: str
    runs: tuple[tuple[str, Polyline], ...] = ()
    vias: tuple[Point, ...] = ()
    relaxed: tuple[str, ...] = ()
    tracks: tuple[Track, ...] = ()
    role_vias: tuple[Via, ...] = ()


def _geometry(subject: JobSubject, shape: _Shape, through: tuple[str, str]) -> list[object]:
    if shape.source == "role":
        found: list[object] = [
            ["track", t.layer, t.width, [t.start.x, t.start.y], [t.end.x, t.end.y]] for t in shape.tracks
        ]
        found += [
            ["via", [v.position.x, v.position.y], v.diameter, v.drill, list(v.layers)]
            for v in shape.role_vias
        ]
        return sorted(found, key=repr)
    found = [["track", layer, subject.width, [[p.x, p.y] for p in points]] for layer, points in shape.runs]
    found += [["via", [p.x, p.y], subject.via_diameter, subject.via_drill, list(through)] for p in shape.vias]
    return found


def candidate_id(subject: str, source: str, relaxed: Sequence[str], geometry: Sequence[object]) -> str:
    """``c-`` and the first 16 hex digits of the SHA-256 of the canonical JSON of the subject key, the source,
    the relaxations and the items' geometry: never of the rest of the board."""
    return "c-" + content_hash(subject, source, list(relaxed), list(geometry))[:16]


def _candidate(job: RoutingJob, subject: JobSubject, net_id: str | None, shape: _Shape) -> Candidate:
    through = (job.layers[0], job.layers[-1])
    ident = candidate_id(subject.key, shape.source, shape.relaxed, _geometry(subject, shape, through))
    if shape.source == "role":
        tracks = tuple(
            replace(
                t,
                id=derived_id(
                    "trk",
                    "proposal",
                    content_hash(ident, t.layer, t.width, [t.start.x, t.start.y], [t.end.x, t.end.y]),
                ),
                locked=False,
            )
            for t in shape.tracks
        )
        vias = tuple(
            replace(
                v,
                id=derived_id("via", "proposal", content_hash(ident, v.position.x, v.position.y)),
                locked=False,
            )
            for v in shape.role_vias
        )
    else:
        made: list[Track] = []
        for layer, points in shape.runs:
            for p, q in zip(points, points[1:], strict=False):
                geometry = (p.x, p.y, q.x, q.y, subject.width, layer)
                made.append(
                    Track(
                        id=derived_id("trk", "proposal", content_hash(ident, geometry)),
                        start=p,
                        end=q,
                        width=subject.width,
                        layer=layer,
                        net_id=net_id,
                    )
                )
        tracks = tuple(made)
        vias = tuple(
            Via(
                id=derived_id("via", "proposal", content_hash(ident, p.x, p.y)),
                position=p,
                diameter=subject.via_diameter,
                drill=subject.via_drill,
                layers=through,
                net_id=net_id,
            )
            for p in shape.vias
        )
    used = {t.layer for t in tracks} | {layer for v in vias for layer in (v.layers[0], v.layers[-1])}
    if vias:
        used |= set(job.layers)
    layers = tuple(layer for layer in job.layers if layer in used)
    total = sum(isqrt((t.end.x - t.start.x) ** 2 + (t.end.y - t.start.y) ** 2) for t in tracks)
    return Candidate(ident, subject.key, shape.source, shape.relaxed, tracks, (), vias, total, layers)


# --- distinct candidates ------------------------------------------------------------------------------------


def _lines(candidate: Candidate) -> list[tuple[Point, Point]]:
    return [(t.start, t.end) for t in candidate.tracks] or [(v.position, v.position) for v in candidate.vias]


def _far(one: list[tuple[Point, Point]], other: list[tuple[Point, Point]], limit: int) -> bool:
    """Whether a point of ``one`` (an end or the middle of a segment) lies farther than ``limit`` from every
    segment of ``other``."""
    for p, q in one:
        for point in (p, q, Point((p.x + q.x) // 2, (p.y + q.y) // 2)):
            if all(dist2_point_segment(point, a, b) > limit * limit for a, b in other):
                return True
    return False


def distinct(candidate: Candidate, kept: Sequence[Candidate], clearance: int) -> bool:
    """Whether ``candidate`` differs from every kept one: another layer set, another via count, or a centre
    line apart by more than ``clearance`` somewhere (decision 4)."""
    mine = _lines(candidate)
    for other in kept:
        if set(other.layers) != set(candidate.layers) or len(other.vias) != len(candidate.vias):
            continue
        theirs = _lines(other)
        if not mine or not theirs:
            return False
        if not (_far(mine, theirs, clearance) or _far(theirs, mine, clearance)):
            return False
    return True


# --- the search ---------------------------------------------------------------------------------------------


@dataclass
class _Tally:
    """Why the shapes of a subject were refused: whether a shape was built, one was short enough, a layer or a
    via was possible, and the first blockers."""

    built: bool = False
    short: bool = False
    layered: bool = False
    blockers: list[str] = field(default_factory=lambda: [])

    def block(self, found: str | None) -> None:
        if found and found not in self.blockers:
            self.blockers.append(found)

    def reason(self) -> str:
        if not self.layered:
            return "no-layer"
        if self.built and not self.short:
            return "too-long"
        return "no-room"


class _Search:
    def __init__(
        self, job: RoutingJob, world: World, pads: Sequence[object], max_length: Nm, keep: int
    ) -> None:
        self.job = job
        self.world = world
        self.pads = pads
        self.max_length = max_length
        self.keep = keep
        self.records = {f"{getattr(p, 'ref', '')}-{getattr(p, 'number', '')}": p for p in pads}
        given = job.extra.get("zone_copper")
        self.zone_copper: ZoneCopper | None = cast(ZoneCopper, given) if callable(given) else None
        self.net_ids = {net.name: net.id for net in job.design.circuit.nets}

    # acceptance ---------------------------------------------------------------------------------------------

    def fits(self, net: str, layer: str, points: Polyline, width: Nm, tally: _Tally) -> bool:
        if len(points) < 2:
            return True
        if not self.world.ends_ok(net, layer, points):
            tally.block("an acute joint with a track of its net")
            return False
        found = refusal(self.world, net, layer, points, width)
        tally.block(found)
        return found is None

    def via_fits(self, net: str, at: Point, diameter: Nm, tally: _Tally) -> bool:
        probe = (at, Point(at.x + 1, at.y))
        for layer in self.world.layers:
            found = refusal(self.world, net, layer, probe, diameter)
            if found is not None:
                tally.block(found)
                return False
        return True

    def layers(self, subject: JobSubject, *ends: tuple[str, ...]) -> list[str]:
        return [
            layer
            for layer in subject.layers
            if layer in self.world.layers
            and layer not in self.world.planes
            and all(layer in end for end in ends)
        ]

    # families -----------------------------------------------------------------------------------------------

    def plain(self, subject: JobSubject, tally: _Tally) -> list[_Shape]:
        """The ``shape``, ``z-shape`` and ``via-l`` shapes of a subject, in that order."""
        a, b = subject.a, subject.b
        found: list[_Shape] = []
        common = self.layers(subject, a.layers, b.layers)
        firsts = self.layers(subject, a.layers)
        lasts = self.layers(subject, b.layers)
        via = subject.via_diameter > 0 and any(x != y for x in firsts for y in lasts)
        tally.layered = bool(common) or via
        plain = list(shapes(a.at, b.at))
        zees = (
            z_shapes(self.job, self.world, self.pads, subject.net, a.at, b.at, subject.width)
            if a.at != b.at
            else []
        )
        for source, group in (("shape", plain), ("z-shape", zees)):
            for points in group:
                tally.built = True
                if length(points) > self.max_length:
                    continue
                tally.short = True
                for layer in common:
                    if self.fits(subject.net, layer, points, subject.width, tally):
                        found.append(_Shape(source, ((layer, points),)))
        if not via:
            return found
        for points in (*plain, *zees):
            if len(points) != 3 or length(points) > self.max_length:
                continue
            tally.built = tally.short = True
            head, tail, bend = points[:2], points[1:], points[1]
            for first in firsts:
                for last in lasts:
                    if first == last:
                        continue
                    if (
                        self.fits(subject.net, first, head, subject.width, tally)
                        and self.fits(subject.net, last, tail, subject.width, tally)
                        and self.via_fits(subject.net, bend, subject.via_diameter, tally)
                    ):
                        found.append(_Shape("via-l", ((first, head), (last, tail)), (bend,)))
        return found

    def fanout(self, subject: JobSubject, tally: _Tally) -> list[_Shape]:
        """The neck and via of the plane fan-out's search, the first passing position of each direction."""
        if subject.via_diameter <= 0:
            return []
        pad = self.records.get(subject.a.name)
        zone_layer = subject.b.layers[0] if subject.b.layers else ""
        layer = next((x for x in subject.a.layers if x in self.world.layers), None)
        if pad is None or layer is None or not zone_layer:
            return []
        tally.layered = tally.built = tally.short = True
        own = _pad_shapes(pad, layer)
        step = -(-subject.via_diameter // (4 * GRID)) * GRID
        neck = self.world.clearance(
            self.world.subject(subject.net, layer), self.world.subject(subject.net, layer)
        )
        outlines = self._outlines(subject.net, zone_layer)
        found: list[_Shape] = []
        origin = subject.a.at
        for k in _direction_order(_outward(self.job, pad, origin)):
            direction = DIRECTIONS[k]
            start = _first_distance(own, origin, direction, step, subject.via_diameter, neck)
            for count in range(start, start + STEPS):
                centre = _centre(origin, direction, count * step)
                neck_line = (origin, centre)
                if not (
                    self.fits(subject.net, layer, neck_line, subject.width, tally)
                    and self.via_fits(subject.net, centre, subject.via_diameter, tally)
                ):
                    continue
                if not _on_zone(outlines, centre, subject.via_diameter):
                    tally.block(f"outside the zone {subject.b.name}")
                    continue
                if self.zone_copper is not None and not self.zone_copper(
                    subject.net, zone_layer, centre, (subject.via_diameter + 1) // 2
                ):
                    tally.block(f"outside the copper of {subject.b.name}")
                    continue
                found.append(_Shape("fanout", ((layer, neck_line),), (centre,)))
                break
        return found

    def _outlines(self, net: str, layer: str) -> list[tuple[Point, ...]]:
        board = self.job.design.board
        net_id = self.net_ids.get(net)
        return [
            zone.outline
            for zone in (board.zones if board is not None else ())
            if zone.net_id == net_id and layer in zone.layers and len(zone.outline) >= 3
        ]

    def role(self, subject: JobSubject, tally: _Tally) -> tuple[list[_Shape], str]:
        """The ``role`` candidates of a group subject and the reason of its default run."""
        routes = tuple(route for route in self.job.roles if route.group == subject.group)
        if not routes:
            return [], "pads"
        tally.layered = tally.built = tally.short = True
        base = {key: value for key, value in self.job.options.items() if key in ROLE_OPTIONS}
        found: list[_Shape] = []
        reason = ""
        variants: list[tuple[str, ...]] = [(), *((r,) for r in RELAXATIONS)]
        for relaxed in variants:
            options = dict(base)
            job_routes: tuple[JobRoleRoute, ...] = routes
            for item in relaxed:
                key, _, value = item.partition("=")
                if key == "keep-away":
                    # the keep-away lowered to the clearance in force, which the clearance test keeps from
                    # every other net's copper: the aggressors drop out, isolation stays
                    job_routes = tuple(replace(r, aggressors=(), keep_away=0) for r in job_routes)
                    options.pop("keep-away", None)
                else:
                    options[key] = value
            sub = replace(self.job, roles=job_routes, subjects=(), options=options)
            held = (list(self.world.placed), {k: list(v) for k, v in self.world.ends.items()})
            result = route_roles(sub, self.world, self.pads, "octilinear")
            self.world.placed, self.world.ends = held[0], held[1]
            bad = [o for o in result.roles if o.status in ("unrouted", "refused")]
            if not relaxed and bad:
                first = bad[0]
                reason = first.reason if first.reason in REASONS else "no-room"
                for blocker in first.blockers:
                    tally.block(blocker)
            if bad or not (result.tracks or result.vias):
                continue
            found.append(_Shape("role", relaxed=relaxed, tracks=result.tracks, role_vias=result.vias))
        return found, reason or "no-room"


def _pad_shapes(pad: object, layer: str) -> list[object]:
    found: list[object] = []
    for entry in cast("tuple[object, ...]", getattr(pad, "copper", ())):
        if getattr(entry, "layer", "") != layer:
            continue
        shape = thick(
            cast("tuple[Point, ...]", getattr(entry, "core", ())),
            cast(int, getattr(entry, "width", 0)),
            cast(bool, getattr(entry, "filled", False)),
        )
        if shape is not None:
            found.append(shape)
    return found


def _outward(job: RoutingJob, pad: object, at: Point) -> tuple[int, int]:
    """From the footprint's position to the pad's, or the pad's +X turned by its rotation (the plane fan-out's
    outward direction)."""
    board = job.design.board
    footprint = getattr(pad, "footprint_id", None)
    origin = next((fp.position for fp in (board.footprints if board else ()) if fp.id == footprint), at)
    dx, dy = at.x - origin.x, at.y - origin.y
    if (dx, dy) != (0, 0):
        return dx, dy
    turned = rotate_point(Point(1_000_000, 0), cast(int, getattr(pad, "rotation", 0)))
    return turned.x, turned.y


def _direction_order(outward: tuple[int, int]) -> tuple[int, ...]:
    """The indices of ``DIRECTIONS`` by their angle to ``outward``, equal angles by index, compared exactly by
    the sign and the square of the cosine's numerator over ``|d|²``."""
    ox, oy = outward

    def key(k: int) -> tuple[Fraction, int]:
        dx, dy = DIRECTIONS[k]
        dot = ox * dx + oy * dy
        value = Fraction(dot * dot, dx * dx + dy * dy)
        return (-value if dot > 0 else value, k)

    return tuple(sorted(range(len(DIRECTIONS)), key=key))


def _centre(origin: Point, direction: tuple[int, int], distance: int) -> Point:
    """The point ``distance`` from ``origin`` along ``direction``, on whole micrometres, half to even."""
    dx, dy = direction
    along = distance if 0 in (dx, dy) else isqrt(distance * distance // 2)

    def snap(value: int) -> int:
        q, r = divmod(value, GRID)
        if 2 * r > GRID or (2 * r == GRID and q % 2 == 1):
            q += 1
        return q * GRID

    return Point(snap(origin.x + dx * along), snap(origin.y + dy * along))


def _first_distance(
    own: Sequence[object], origin: Point, direction: tuple[int, int], step: int, diameter: int, neck: int
) -> int:
    """The steps to the first distance at which the via keeps ``neck`` from its own pad's copper."""
    from fenolite.geometry import Thick, thick_closer_than, thick_touch

    for count in range(1, REACH_LIMIT + 1):
        via = Thick((_centre(origin, direction, count * step),), diameter)
        if not any(
            thick_touch(via, cast(Thick, shape))
            if neck == 0
            else thick_closer_than(via, cast(Thick, shape), neck)
            for shape in own
        ):
            return count
    return REACH_LIMIT


def _on_zone(outlines: Sequence[tuple[Point, ...]], centre: Point, diameter: int) -> bool:
    """Whether ``centre`` lies inside a zone outline by at least half the via's diameter."""
    for ring in outlines:
        if point_in_ring(centre, ring) is not Location.INSIDE:
            continue
        edges = zip(ring, (*ring[1:], ring[0]), strict=True)
        if all(4 * dist2_point_segment(centre, a, b) >= diameter * diameter for a, b in edges):
            return True
    return False


# --- the job ------------------------------------------------------------------------------------------------


def propose_options(options: Mapping[str, str], issues: list[Issue]) -> tuple[int, Nm]:
    """``candidates`` and ``max-length`` of a proposal job; one ``route.option-ignored`` per unknown key or
    bad value (the role-mode options go to the ``role`` family)."""
    keep, max_length = CANDIDATES, MAX_LENGTH
    for key, value in sorted(options.items()):
        if key in ROLE_OPTIONS:
            continue
        if key == "candidates" and value.isdigit() and 1 <= int(value) <= MAX_CANDIDATES:
            keep = int(value)
            continue
        if key == "max-length":
            try:
                parsed = parse_length(value, default_unit="mm")
            except ValueError:
                parsed = 0
            if parsed > 0:
                max_length = parsed
                continue
        why = "an unknown option" if key not in OPTIONS else f"{value!r} is no valid value"
        issues.append(
            Issue(
                "route.option-ignored",
                "warning",
                f"the router option {key} is ignored by the octilinear router in proposal mode: {why}",
                key,
                hint="proposal mode takes candidates=1..8 and max-length=LENGTH, and the role-mode options",
            )
        )
    return keep, max_length


def propose(job: RoutingJob, world: World, pads: Sequence[object], tool: str) -> RoutingResult:
    """Candidates for ``job.subjects`` (see the module); the result holds no track, arc or via."""
    issues: list[Issue] = []
    keep, max_length = propose_options(job.options, issues)
    search = _Search(job, world, pads, max_length, keep)
    nets: dict[str, JobNet] = {net.name: net for net in job.nets}
    candidates: list[Candidate] = []
    refusals: list[tuple[str, str, tuple[str, ...]]] = []
    base = (list(world.placed), {k: list(v) for k, v in world.ends.items()})
    for subject in job.subjects:
        world.placed, world.ends = list(base[0]), {k: list(v) for k, v in base[1].items()}
        tally = _Tally()
        shaped: list[_Shape] = []
        reason = ""
        if subject.kind == "group":
            shaped, reason = search.role(subject, tally)
        else:
            shaped = search.plain(subject, tally)
            if subject.kind == "fanout":
                shaped += search.fanout(subject, tally)
        net = nets.get(subject.net)
        net_id = net.net_id if net is not None else search.net_ids.get(subject.net)
        clearance = world.clearance(world.subject(subject.net, ""), world.subject(subject.net, ""))
        kept: list[Candidate] = []
        for shape in shaped:
            if len(kept) >= keep:
                break
            made = _candidate(job, subject, net_id, shape)
            if distinct(made, kept, clearance):
                kept.append(made)
        candidates += kept
        if not kept:
            refusals.append((subject.key, reason or tally.reason(), tuple(tally.blockers[:3])))
    return RoutingResult(
        issues=tuple(issues),
        tool=tool,
        tool_version="builtin",
        evidence=EVIDENCE,
        candidates=tuple(candidates),
        refusals=tuple(refusals),
    )


__all__ = [
    "CANDIDATES",
    "FAMILIES",
    "MAX_CANDIDATES",
    "REASONS",
    "RELAXATIONS",
    "ZoneCopper",
    "candidate_id",
    "distinct",
    "propose",
    "propose_options",
]
