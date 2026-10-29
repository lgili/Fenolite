# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated copper of a KiCad build: the records of ``band``, ``keepout_ring``, ``barrier``,
``body_keepout``, ``fanout_zone`` and ``stitch_pieces`` turned into zones, rule areas, tracks and vias
(capability design-dsl, "Generated copper calls"; ``docs/copper.md``, "Generated copper"; change c0224).

``resolve_generated`` runs on the placed design after the script copper, so the generators see every pad
and every script track. What it adds is ordinary: a locked zone with the id of the ``zone()`` of its name,
a rule area with the id of the ``rule_area()`` of its name (marked by ``boarditems.mark_items``), and
tracks and vias with copper uuids. A rebuild therefore replaces them and nothing else. Every length is an
integer of nanometres and every test exact (``geometry.thick``); the shapes are convex where a union would
be needed, because the core has no polygon union (c0224's design, decision 4).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Collection, Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType
from typing import ClassVar, Protocol, cast

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad import boarditems
from fenolite.backends.kicad.copper import copper_uuid, edge_clearance_in_force, stitch_vias
from fenolite.backends.kicad.fanout import FanoutSizes, plan_fanout
from fenolite.backends.kicad.frame import board_pads, placed_extents
from fenolite.backends.kicad.outline import BoardOutline, board_outline
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.geometry import (
    DEFAULT_TOL,
    BBox,
    GeometryError,
    Location,
    Polygon,
    SpatialIndex,
    Thick,
    Transform,
    convex_hull,
    dist2_point_segment,
    point_in_ring,
    polygons_intersect,
    rotate_point,
    round_point,
    thick_bbox,
    thick_closer_than,
)
from fenolite.geometry import Arc as GeoArc
from fenolite.model.board import Keepout, Track, Via, Zone, ZoneSettings
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject

GENERATE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.generate.altium": "error",
        "kicad.generate.unknown": "error",
        "kicad.generate.off-board": "error",
        "kicad.generate.no-hole": "error",
        "kicad.generate.no-plan": "error",
        "kicad.generate.no-zone": "error",
        "kicad.generate.size-missing": "error",
        "kicad.generate.pieces": "error",
        "kicad.generate.name-taken": "error",
        "kicad.generate.crossing": "error",
        "kicad.generate.unplaced": "warning",
        "kicad.generate.band-narrow": "warning",
        "kicad.generate.encloses": "warning",
        "kicad.generate.stitch-short": "warning",
    }
)
"""The closed table of the codes of generated copper."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-GEN-DRC",))
"""What a build with generated copper claims until the oracle row is measured on both majors."""
CALLS: tuple[str, ...] = ("keepout_ring", "body_keepout", "barrier", "band", "fanout_zone", "stitch_pieces")
"""The order of resolution: keep-outs, bands, fan-outs, stitches (``fenolite.dsl.generate.CALLS``)."""
DSL = "dsl"
ENVELOPE_SIDES = 16
"""The sides of the disc polygons that make a convex envelope (barriers and body keep-outs)."""
SHORT_RUN = 5
"""A spine segment shorter than this many widths widens by at most one level."""


# --- the records as the build reads them ----------------------------------------------------------


class GeneratedLike(Protocol):
    """What every record has: its call, its name and its key ``<call>.<name>``."""

    call: ClassVar[str]

    @property
    def name(self) -> str: ...
    @property
    def key(self) -> str: ...


class BandLike(GeneratedLike, Protocol):
    @property
    def net(self) -> str: ...
    @property
    def spine(self) -> tuple[Point, ...]: ...
    @property
    def width(self) -> Nm: ...
    @property
    def max_width(self) -> Nm: ...
    @property
    def step(self) -> Nm: ...
    @property
    def layers(self) -> tuple[str, ...]: ...
    @property
    def clearance(self) -> Nm | None: ...
    @property
    def priority(self) -> int: ...


class AreaLike(GeneratedLike, Protocol):
    """A keep-out record: ``keepout_ring``, ``barrier`` or ``body_keepout``."""

    @property
    def setback(self) -> Nm: ...
    @property
    def layers(self) -> tuple[str, ...]: ...
    @property
    def forbid(self) -> tuple[str, ...]: ...


class RingLike(AreaLike, Protocol):
    @property
    def component(self) -> str: ...
    @property
    def sides(self) -> int: ...


class BodyLike(AreaLike, Protocol):
    @property
    def component(self) -> str: ...


class BarrierLike(AreaLike, Protocol):
    @property
    def netclass(self) -> str: ...
    @property
    def pieces(self) -> bool: ...


class FanoutLike(GeneratedLike, Protocol):
    @property
    def net(self) -> str: ...
    @property
    def side(self) -> str: ...
    @property
    def refs(self) -> tuple[str, ...]: ...
    @property
    def width(self) -> Nm | None: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...
    @property
    def clearance(self) -> Nm | None: ...


class StitchPiecesLike(GeneratedLike, Protocol):
    @property
    def net(self) -> str: ...
    @property
    def pitch(self) -> Nm: ...
    @property
    def layers(self) -> tuple[str, ...]: ...
    @property
    def min_vias(self) -> int: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...
    @property
    def clearance(self) -> Nm | None: ...
    @property
    def margin(self) -> Nm: ...


def issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, GENERATE_ISSUE_CODES[code], message, where=where, hint=hint)


class _Refused(Exception):
    """A record that creates nothing: the issue says why."""

    def __init__(self, code: str, message: str, key: str, hint: str = "") -> None:
        self.issue = issue(code, message, key, hint)
        super().__init__(message)


def _mm(value: int) -> str:
    """``value`` nanometres as millimetres, without trailing zeros."""
    sign = "-" if value < 0 else ""
    whole, part = divmod(abs(value), 1_000_000)
    text = f"{part:06d}".rstrip("0")
    return f"{sign}{whole}.{text}" if text else f"{sign}{whole}"


# --- shapes ---------------------------------------------------------------------------------------


def disc(center: Point, radius: int, sides: int) -> tuple[Point, ...]:
    """A polygon of ``sides`` vertices around ``center`` that holds the disc of ``radius``: its vertices lie
    at ``radius / cos(π / sides)`` or a few nanometres more, turned by ``rotate_point``, and every edge is
    proved to keep ``radius`` from the centre with integers. ``radius`` 0 gives the centre alone."""
    if radius <= 0:
        return (center,)
    reach = math.ceil(radius / math.cos(math.pi / sides)) + 1
    turn = 360_000_000 // sides
    while True:
        ring = tuple(
            Point(center.x + p.x, center.y + p.y)
            for p in (rotate_point(Point(reach, 0), k * turn) for k in range(sides))
        )
        edges = zip(ring, (*ring[1:], ring[0]), strict=True)
        if all(dist2_point_segment(center, a, b) >= radius * radius for a, b in edges):
            return ring
        reach += 1 + reach // 1_000_000


def _points(shape: Thick, grow: int, sides: int) -> list[Point]:
    """Points whose convex hull holds ``shape`` grown by ``grow``: a disc polygon of ``width / 2 + grow``
    around each point of its core (a filled core's region lies in the hull of its vertices)."""
    radius = -(-shape.width // 2) + grow
    return [point for core in shape.core for point in disc(core, radius, sides)]


def _hull(points: Sequence[Point]) -> tuple[Point, ...]:
    hull = convex_hull(points)
    if len(hull) < 3:
        raise GeometryError("a convex envelope needs three points that are not on one line", points=hull)
    return tuple(hull)


def _simplified(ring: Sequence[Point]) -> tuple[Point, ...]:
    """``ring`` without repeated points and without points on a straight line between their neighbours."""
    points: list[Point] = []
    for point in ring:
        if not points or points[-1] != point:
            points.append(point)
    while len(points) > 1 and points[0] == points[-1]:
        points.pop()
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i in range(len(points)):
            a, b, c = points[i - 1], points[i], points[(i + 1) % len(points)]
            if (b.x - a.x) * (c.y - b.y) == (b.y - a.y) * (c.x - b.x):
                del points[i]
                changed = True
                break
    return tuple(points)


def _clip(ring: Sequence[Point], cut: int, left: bool) -> list[Point]:
    """The part of the convex ``ring`` with ``x <= cut`` (``left``) or ``x >= cut``, in the ring's order.
    Where an edge crosses the line, the crossing is the exact point rounded: the same for both halves."""
    out: list[Point] = []

    def inside(point: Point) -> bool:
        return point.x <= cut if left else point.x >= cut

    for i, p in enumerate(ring):
        q = ring[(i + 1) % len(ring)]
        if inside(p):
            out.append(p)
        if (p.x - cut) * (q.x - cut) < 0:
            y = p.y + Fraction((q.y - p.y) * (cut - p.x), q.x - p.x)
            out.append(round_point(cut, y))
    return out


def _chain(part: Sequence[Point], cut: int) -> list[Point]:
    """The points of a clipped convex ring from one end of its edge on the line ``x = cut`` round to the
    other, so that the edge on the line is left out."""
    points = list(_simplified(part))
    size = len(points)
    for k in range(size):
        if points[k].x == cut and points[(k + 1) % size].x == cut:
            return [points[(k + 1 + i) % size] for i in range(size)]
    raise GeometryError("a half of an envelope has no edge on its cut line", points=tuple(points))


def halves(outer: Sequence[Point], inner: Sequence[Point]) -> tuple[tuple[Point, ...], tuple[Point, ...]]:
    """The band between the convex rings ``outer`` and ``inner`` (inside it) as two simple polygons, cut by
    the vertical line through the middle of ``inner``: a rule area of the model has no hole."""
    cut = (min(p.x for p in inner) + max(p.x for p in inner)) // 2
    found: list[tuple[Point, ...]] = []
    for left in (True, False):
        out_chain = _chain(_clip(outer, cut, left), cut)
        in_chain = _chain(_clip(inner, cut, left), cut)
        found.append(_simplified((*out_chain, *reversed(in_chain))))
    return found[0], found[1]


# --- the design as the generators see it --------------------------------------------------------------


@dataclasses.dataclass(slots=True)
class _Board:
    """The placed design, the pads in the board frame, and what the records add, in order."""

    design: Design
    pads: tuple[BoardPad, ...]
    unplaced: frozenset[str]
    nets: dict[str, Net]
    classes: dict[str, NetClass]
    zones: list[Zone] = dataclasses.field(default_factory=lambda: list[Zone]())
    keepouts: list[Keepout] = dataclasses.field(default_factory=lambda: list[Keepout]())
    tracks: list[Track] = dataclasses.field(default_factory=lambda: list[Track]())
    vias: list[Via] = dataclasses.field(default_factory=lambda: list[Via]())

    @property
    def copper(self) -> tuple[str, ...]:
        board = self.design.board
        layers = board.layers if board is not None else ()
        return tuple(la.name for la in sorted(layers, key=lambda la: la.ordinal) if la.kind == "copper")

    def net(self, name: str, key: str) -> Net:
        found = self.nets.get(name)
        if found is None:
            raise _Refused("kicad.generate.unknown", f"{key}: {name!r} is not a net of the design", key)
        return found

    def netclass(self, net: Net) -> NetClass | None:
        return self.classes.get(net.netclass_id) if net.netclass_id is not None else None

    def class_clearance(self, name: str | None) -> int:
        found = next((cls for cls in self.classes.values() if cls.name == name), None)
        return found.clearance or 0 if found is not None else 0

    def placed(self, pad: BoardPad) -> bool:
        return pad.path not in self.unplaced and pad.ref not in self.unplaced

    def part_pads(self, component: str, key: str) -> list[BoardPad]:
        found = [pad for pad in self.pads if pad.path == component] or [
            pad for pad in self.pads if pad.ref == component
        ]
        if not found:
            raise _Refused(
                "kicad.generate.unknown", f"{key}: no footprint of {component!r} on the board", key
            )
        if not all(self.placed(pad) for pad in found):
            raise _Refused(
                "kicad.generate.unplaced",
                f"{key}: {component} is not placed yet (it sits in the staging row), so nothing is generated",
                key,
            )
        return found

    def current(self) -> Design:
        """The design with what the records added so far; rule areas marked as script items."""
        board = self.design.board
        assert board is not None
        return boarditems.mark_items(
            dataclasses.replace(
                self.design,
                board=dataclasses.replace(
                    board,
                    zones=(*board.zones, *self.zones),
                    keepouts=(*board.keepouts, *self.keepouts),
                    tracks=(*board.tracks, *self.tracks),
                    vias=(*board.vias, *self.vias),
                ),
            )
        )

    def take(self, kind: str, name: str, key: str) -> None:
        """Refuse a generated name that a zone or a rule area of the design already holds."""
        board = self.design.board
        assert board is not None
        held = (*board.zones, *self.zones) if kind == "zone" else (*board.keepouts, *self.keepouts)
        if any(item.name.casefold() == name.casefold() for item in held):
            raise _Refused(
                "kicad.generate.name-taken",
                f"{key}: the {kind} name {name!r} is already held by the design",
                key,
                "pass another name= to the call",
            )

    def area(self, intent: AreaLike, name: str, ring: Sequence[Point]) -> Keepout:
        self.take("rule area", name, intent.key)
        return Keepout(
            id=derived_id("kpo", DSL, f"area:{name}"),
            outline=tuple(ring),
            layers=intent.layers,
            name=name,
            no_tracks="tracks" in intent.forbid,
            no_vias="vias" in intent.forbid,
            no_pads="pads" in intent.forbid,
            no_copper_pour="pours" in intent.forbid,
            no_footprints="footprints" in intent.forbid,
        )


def _pad_shapes(pad: BoardPad, layers: Collection[str] | None) -> list[tuple[str | None, Thick]]:
    """The copper of ``pad`` on ``layers`` (every layer when ``None``) and its hole (layer ``None``)."""
    found: list[tuple[str | None, Thick]] = []
    for entry in pad.copper:
        if layers is not None and entry.layer not in layers:
            continue
        try:
            found.append((entry.layer, Thick(entry.core, entry.width, entry.filled)))
        except (GeometryError, ValueError):
            continue
    if pad.hole and pad.drill:
        found.append((None, Thick(tuple(pad.hole), pad.drill)))
    return found


def _item_shapes(design: Design, nets: Collection[str] | None, *, exclude: str | None = None) -> list[Thick]:
    """The tracks, arcs and vias of ``nets`` (of every net but ``exclude`` when ``nets`` is ``None``)."""
    board = design.board
    assert board is not None
    names = {net.id: net.name for net in design.circuit.nets}

    def chosen(net_id: str | None) -> bool:
        name = names.get(net_id or "")
        return (name in nets) if nets is not None else name != exclude or name is None

    found: list[Thick] = []
    for track in board.tracks:
        if chosen(track.net_id):
            found.append(Thick((track.start, track.end), track.width))
    for arc in board.arcs:
        if chosen(arc.net_id):
            try:
                core = tuple(GeoArc(arc.start, arc.mid, arc.end).polygonize(DEFAULT_TOL))
            except (GeometryError, ValueError):
                core = (arc.start, arc.mid, arc.end)
            found.append(Thick(core, arc.width + 2 * DEFAULT_TOL + 2))
    for via in board.vias:
        if chosen(via.net_id):
            found.append(Thick((via.position,), via.diameter))
    return found


# --- the band ---------------------------------------------------------------------------------------


def _clearance(ctx: _Board, net: Net, given: int | None, key: str) -> int:
    if given is not None:
        return given
    cls = ctx.netclass(net)
    if cls is None or cls.clearance is None:
        raise _Refused(
            "kicad.generate.size-missing",
            f"{key}: no clearance is given and the class of {net.name} sets none",
            key,
            "pass clearance= or give the net a class with a clearance",
        )
    return cls.clearance


def _on_board(point: Point, rings: Sequence[Sequence[Point]]) -> bool:
    if not rings:
        return True
    if point_in_ring(point, rings[0]) is Location.OUTSIDE:
        return False
    return not any(point_in_ring(point, hole) is Location.INSIDE for hole in rings[1:])


def _levels(
    allowed: Sequence[int], lengths: Sequence[int], step: int, caps: Sequence[int], ties: Sequence[range]
) -> list[int]:
    """The level of each cell boundary: the lower level of its cells, at most its cap, with one level of
    change across a full cell (a 45° edge), none across an end cell or a shorter one, and one level for
    the boundaries of each tie."""
    count = len(allowed)
    levels = [min(caps[0], allowed[0])]
    levels += [min(caps[b], allowed[b - 1], allowed[b]) for b in range(1, count)]
    levels.append(min(caps[count], allowed[-1]))
    changed = True
    while changed:
        changed = False
        for cell in range(count):
            a, b = levels[cell], levels[cell + 1]
            flat = lengths[cell] != step or cell == 0 or cell == count - 1
            limit_a, limit_b = (b, a) if flat else (b + 1, a + 1)
            if a > limit_a:
                levels[cell], changed = limit_a, True
            if b > limit_b:
                levels[cell + 1], changed = limit_b, True
        for tie in ties:
            low = min(levels[b] for b in tie)
            for b in tie:
                if levels[b] != low:
                    levels[b], changed = low, True
    return levels


@dataclasses.dataclass(slots=True)
class _Run:
    """One segment of a band's spine: its start, unit direction and length, its cell boundaries, and per
    side (``+1`` the left of the direction, ``-1`` the right) the levels allowed per cell, the caps and the
    ties per boundary, and the solved levels."""

    a: Point
    u: tuple[int, int]
    length: int
    ticks: list[int]
    allowed: dict[int, list[int]] = dataclasses.field(default_factory=lambda: dict[int, list[int]]())
    caps: dict[int, list[int]] = dataclasses.field(default_factory=lambda: dict[int, list[int]]())
    ties: dict[int, list[range]] = dataclasses.field(default_factory=lambda: dict[int, list[range]]())
    levels: dict[int, list[int]] = dataclasses.field(default_factory=lambda: dict[int, list[int]]())

    @property
    def n(self) -> tuple[int, int]:
        return -self.u[1], self.u[0]

    @property
    def lengths(self) -> list[int]:
        return [t1 - t0 for t0, t1 in zip(self.ticks, self.ticks[1:], strict=False)]

    def at(self, t: int, o: int) -> Point:
        (ux, uy), (nx, ny) = self.u, self.n
        return Point(self.a.x + ux * t + nx * o, self.a.y + uy * t + ny * o)


def _inner(first: _Run, second: _Run, side: int) -> bool:
    """Whether ``side`` of the path is the inside of the turn from ``first`` to ``second``."""
    return second.u == (side * first.n[0], side * first.n[1])


def _band(ctx: _Board, intent: BandLike, outline: BoardOutline) -> tuple[list[Zone], list[Issue]]:
    key = intent.key
    net = ctx.net(intent.net, key)
    clearance = _clearance(ctx, net, intent.clearance, key)
    for point in intent.spine:
        if not _on_board(point, outline.rings):
            raise _Refused(
                "kicad.generate.off-board",
                f"{key}: the spine point ({_mm(point.x)}, {_mm(point.y)}) mm of the board frame lies off "
                "the board",
                key,
                "move the spine inside the board outline",
            )
    layers = set(intent.layers)
    obstacles: list[Thick] = []
    for pad in ctx.pads:
        if pad.net != net.name and ctx.placed(pad):
            obstacles += [
                shape for layer, shape in _pad_shapes(pad, layers) if layer in layers or layer is None
            ]
    obstacles += _item_shapes(ctx.design, None, exclude=net.name)
    index = SpatialIndex[Thick].build((thick_bbox(shape).inflate(clearance), shape) for shape in obstacles)

    def clear(ring: Sequence[Point]) -> bool:
        shape = Thick(tuple(ring), 0, filled=True)
        box = thick_bbox(shape)
        return not any(thick_closer_than(shape, other, clearance) for other in index.query(box))

    half, step = intent.width // 2, intent.step
    top = max(half, intent.max_width // 2)
    count = (top - half) // step

    def offset(level: int) -> int:
        return half + level * step

    runs: list[_Run] = []
    for a, b in zip(intent.spine, intent.spine[1:], strict=False):
        length = abs(b.x - a.x) + abs(b.y - a.y)
        ticks = [*range(0, length, step), length]
        if len(ticks) > 2 and ticks[-1] - ticks[-2] < step // 2:
            del ticks[-2]  # a last cell under half a step joins the one before it, which is then flat
        runs.append(_Run(a, ((b.x - a.x) // length, (b.y - a.y) // length), length, ticks))
    narrow = 0
    for run in runs:
        cap = 1 if run.length < SHORT_RUN * intent.width else count
        for side in (1, -1):
            allowed: list[int] = []
            for t0, t1 in zip(run.ticks, run.ticks[1:], strict=False):
                best = -1
                for level in range(count + 1):
                    o = side * offset(level)
                    if not clear((run.at(t0, 0), run.at(t1, 0), run.at(t1, o), run.at(t0, o))):
                        break
                    best = level
                if best < 0:
                    narrow += 1
                allowed.append(max(best, 0))
            run.allowed[side] = allowed
            run.caps[side] = [cap] * len(run.ticks)
            run.ties[side] = []
    # on the inside of a turn, each run is flat over the reach of the other: the corner is then one point
    for first, second in zip(runs, runs[1:], strict=False):
        for side in (1, -1):
            if _inner(first, second, side):
                near = [b for b, t in enumerate(first.ticks) if t >= first.length - top]
                first.ties[side].append(range(max(0, near[0] - 1), len(first.ticks)))
                near = [b for b, t in enumerate(second.ticks) if t <= top]
                second.ties[side].append(range(0, min(len(second.ticks), near[-1] + 2)))
    changed = True
    while changed:
        changed = False
        for run in runs:
            for side in (1, -1):
                run.levels[side] = _levels(
                    run.allowed[side], run.lengths, step, run.caps[side], run.ties[side]
                )
        # on the outside of a turn, the corner square between the two runs must keep the clearance too
        for first, second in zip(runs, runs[1:], strict=False):
            for side in (1, -1):
                if _inner(first, second, side):
                    continue
                end, start = first.levels[side][-1], second.levels[side][0]
                o_end, o_start = side * offset(end), offset(start)
                corner = (
                    first.at(first.length, 0), first.at(first.length + o_start, 0),
                    first.at(first.length + o_start, o_end), first.at(first.length, o_end),
                )  # fmt: skip
                if clear(corner):
                    continue
                if end == 0 and start == 0:
                    narrow += 1
                    continue
                if end >= start:
                    first.caps[side][-1] = end - 1
                else:
                    second.caps[side][0] = start - 1
                changed = True
    ring = _simplified([*_walk(runs, 1, half, offset), *reversed(_walk(runs, -1, half, offset))])
    try:
        simple = Polygon(ring).is_simple()
    except (GeometryError, ValueError):
        simple = False
    if not simple:
        raise _Refused(
            "kicad.generate.crossing",
            f"{key}: the outline of the band crosses itself",
            key,
            "space the runs of the spine at least max_width apart",
        )
    found: list[Issue] = []
    if narrow:
        found.append(
            issue(
                "kicad.generate.band-narrow",
                f"{key}: {narrow} cell(s) of the band cannot keep {_mm(clearance)} mm from other copper even "
                "at the base width; the fill carves the copper there",
                key,
                "move the spine away from the copper of other nets or narrow the band",
            )
        )
    ctx.take("zone", key, key)
    zone = Zone(
        id=derived_id("zon", DSL, f"zone:{key}"),
        outline=ring,
        name=key,
        layers=intent.layers,
        net_id=net.id,
        priority=intent.priority,
        settings=ZoneSettings(clearance=clearance),
        locked=True,
    )
    return [zone], found


def _walk(runs: Sequence[_Run], side: int, half: int, offset: Callable[[int], int]) -> list[Point]:
    """The edge of a band on ``side`` of its spine, from the start to the end: each run's profile, a
    single point on the inside of a turn, a bevelled corner on the outside, and bevelled ends."""
    bevel = half // 2
    points: list[Point] = []
    last = len(runs) - 1
    for number, run in enumerate(runs):
        profile = [(t, offset(level)) for t, level in zip(run.ticks, run.levels[side], strict=True)]
        cut_start, cut_end = -1, run.length
        if number == 0:
            o = profile[0][1]
            cap = min(bevel, run.lengths[0])
            points += [run.at(0, side * (o - cap)), run.at(cap, side * o)]
            cut_start = cap
        elif _inner(runs[number - 1], run, side):
            cut_start = offset(runs[number - 1].levels[side][-1])
        following = runs[number + 1] if number < last else None
        if following is not None and _inner(run, following, side):
            cut_end = run.length - offset(following.levels[side][0])
        elif following is None:
            cut_end = run.length - min(bevel, run.lengths[-1])
        points += [run.at(t, side * o) for t, o in profile if cut_start < t < cut_end]
        o_end = profile[-1][1]
        if following is None:
            cap = min(bevel, run.lengths[-1])
            points += [run.at(run.length - cap, side * o_end), run.at(run.length, side * (o_end - cap))]
        elif _inner(run, following, side):
            points.append(run.at(cut_end, side * o_end))
        else:
            o_next = offset(following.levels[side][0])
            cap = min(bevel, o_end, o_next)
            points += [
                run.at(run.length, side * o_end),
                run.at(run.length + o_next - cap, side * o_end),
                run.at(run.length + o_next, side * (o_end - cap)),
            ]
    return points


# --- keep-outs ----------------------------------------------------------------------------------------


def _ring(ctx: _Board, intent: RingLike) -> list[Keepout]:
    key, component, sides = intent.key, intent.component, intent.sides
    holes = [pad for pad in ctx.part_pads(component, key) if pad.hole and pad.drill]
    if not holes:
        raise _Refused("kicad.generate.no-hole", f"{key}: {component} has no hole", key)
    found: list[Keepout] = []
    for number, pad in enumerate(holes):
        assert pad.drill is not None
        radius = -(-pad.drill // 2) + intent.setback
        points = [point for centre in pad.hole for point in disc(centre, radius, sides)]
        ring = points if len(pad.hole) == 1 else list(_hull(points))
        name = key if len(holes) == 1 else f"{key}.{number}"
        found.append(ctx.area(intent, name, ring))
    return found


def _body(ctx: _Board, intent: BodyLike) -> list[Keepout]:
    key, component = intent.key, intent.component
    owned = {pad.footprint_id for pad in ctx.part_pads(component, key)}
    board = ctx.design.board
    assert board is not None
    rings: list[tuple[Point, ...]] = []
    for footprint in board.footprints:
        if footprint.id not in owned:
            continue
        frame = Transform.placement(footprint.position, footprint.rotation)
        rings += [
            tuple(frame.apply(p) for p in body.outline) for body in footprint.bodies if len(body.outline) >= 3
        ]
    if not rings:
        extents = placed_extents(ctx.design)
        rings = [tuple(ring) for extent in extents if extent.footprint_id in owned for ring in extent.own]
    rings = [ring for ring in rings if len(ring) >= 3]
    if not rings:
        raise _Refused(
            "kicad.generate.no-plan",
            f"{key}: {component} has no body outline and no courtyard, so its plan view is unknown",
            key,
            "give the footprint a courtyard",
        )
    points = [
        grown for ring in rings for point in ring for grown in disc(point, intent.setback, ENVELOPE_SIDES)
    ]
    return [ctx.area(intent, key, _hull(points))]


def _barrier(ctx: _Board, intent: BarrierLike) -> tuple[list[Keepout], list[Issue]]:
    key, netclass, pieces = intent.key, intent.netclass, intent.pieces
    cls = next((item for item in ctx.classes.values() if item.name == netclass), None)
    if cls is None:
        raise _Refused("kicad.generate.unknown", f"{key}: {netclass!r} is not a net class of the design", key)
    members = {net.name for net in ctx.nets.values() if net.netclass_id == cls.id}
    shapes: list[Thick] = []
    for pad in ctx.pads:
        if pad.net in members and ctx.placed(pad):
            shapes += [shape for layer, shape in _pad_shapes(pad, None) if layer is not None]
    shapes += _item_shapes(ctx.design, members)
    if not shapes:
        raise _Refused(
            "kicad.generate.unknown", f"{key}: the class {netclass} holds no copper on the board", key
        )
    inner_points = [_points(shape, 0, ENVELOPE_SIDES) for shape in shapes]
    groups: list[tuple[list[Point], list[Point]]] = [
        (points, _grown(points, intent.setback)) for points in inner_points
    ]
    groups = _merged(groups)
    if len(groups) > 1 and not pieces:
        raise _Refused(
            "kicad.generate.pieces",
            f"{key}: the copper of the class {netclass} lies in {len(groups)} pieces, so one barrier would "
            "close over the ground between them",
            key,
            "pass pieces=True for one barrier per piece, or a larger setback",
        )
    found: list[Keepout] = []
    warnings: list[Issue] = []
    for number, (inner, outer) in enumerate(groups):
        hull_in, hull_out = _hull(inner), _hull(outer)
        left, right = halves(hull_out, hull_in)
        found.append(ctx.area(intent, f"{key}.{number}.a", left))
        found.append(ctx.area(intent, f"{key}.{number}.b", right))
        enclosed = sorted(
            {
                f"{pad.ref}-{pad.number}"
                for pad in ctx.pads
                if pad.net not in members
                and ctx.placed(pad)
                and point_in_ring(pad.position, hull_out) is not Location.OUTSIDE
            }
        )
        if enclosed:
            warnings.append(
                issue(
                    "kicad.generate.encloses",
                    f"{key}: piece {number} of the barrier closes around the pads {', '.join(enclosed)} of "
                    "other nets; their tracks cannot leave without crossing it",
                    key,
                    "use pieces=True, a smaller setback, or move those parts",
                )
            )
    return found, warnings


def _grown(points: Sequence[Point], setback: int) -> list[Point]:
    return [grown for point in points for grown in disc(point, setback, ENVELOPE_SIDES)]


def _root(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _merged(groups: list[tuple[list[Point], list[Point]]]) -> list[tuple[list[Point], list[Point]]]:
    """``groups`` (inner points, outer points) joined while two outer envelopes meet."""
    current = list(groups)
    changed = True
    while changed:
        changed = False
        polygons = [Polygon(_hull(outer)) for _, outer in current]
        boxes = [polygon.bbox() for polygon in polygons]
        index = SpatialIndex[int].build((box, number) for number, box in enumerate(boxes))
        parent = list(range(len(current)))
        for i, j in index.pairs():
            if _root(parent, i) != _root(parent, j) and polygons_intersect(polygons[i], polygons[j]):
                parent[_root(parent, i)] = _root(parent, j)
                changed = True
        if changed:
            joined: dict[int, tuple[list[Point], list[Point]]] = {}
            for number, (inner, outer) in enumerate(current):
                root = _root(parent, number)
                held = joined.setdefault(root, ([], []))
                held[0].extend(inner)
                held[1].extend(outer)
            current = [
                (list(_hull(inner)), list(_hull(outer)))
                for inner, outer in (joined[k] for k in sorted(joined))
            ]
    return [(list(_hull(inner)), list(_hull(outer))) for inner, outer in current]


# --- fan-out and stitches -------------------------------------------------------------------------------


def _sizes(
    ctx: _Board, net: Net, given: tuple[int | None, int | None, int | None], key: str
) -> tuple[int, int, int]:
    cls = ctx.netclass(net)
    width = given[0] if given[0] is not None else (cls.track_width if cls is not None else None)
    diameter = given[1] if given[1] is not None else (cls.via_diameter if cls is not None else None)
    drill = given[2] if given[2] is not None else (cls.via_drill if cls is not None else None)
    missing = [
        name for name, value in (("width", width), ("diameter", diameter), ("drill", drill)) if value is None
    ]
    if missing:
        raise _Refused(
            "kicad.generate.size-missing",
            f"{key}: no {', '.join(missing)} is given and the class of {net.name} sets none",
            key,
            "pass the sizes to the call or give the net a class with them",
        )
    assert width is not None and diameter is not None and drill is not None
    if drill >= diameter:
        raise _Refused(
            "kicad.generate.size-missing", f"{key}: the drill must be smaller than the diameter", key
        )
    return width, diameter, drill


def _fanout(
    ctx: _Board, intent: FanoutLike, outline: BoardOutline, edge: int
) -> tuple[list[Track], list[Via], list[Issue]]:
    key = intent.key
    net = ctx.net(intent.net, key)
    face = "F.Cu" if intent.side == "top" else "B.Cu"
    design = ctx.current()
    board = design.board
    assert board is not None
    planes = sorted(
        {layer for zone in board.zones if zone.net_id == net.id for layer in zone.layers if layer != face}
    )
    if not planes:
        raise _Refused(
            "kicad.generate.no-zone",
            f"{key}: {net.name} has no zone on a copper layer other than {face}",
            key,
            "declare a zone of the net on the other side, or a plane",
        )
    width, diameter, drill = _sizes(ctx, net, (intent.width, intent.diameter, intent.drill), key)
    given = _clearance(ctx, net, intent.clearance, key)
    for ref in intent.refs:
        ctx.part_pads(ref, key)

    def in_force(a: RuleSubject, b: RuleSubject) -> Nm:
        return max(given, ctx.class_clearance(a.netclass), ctx.class_clearance(b.netclass))

    plan = plan_fanout(
        design,
        board_pads(design),
        nets={net.name: FanoutSizes(width, diameter, drill, given)},
        plane_layers=tuple(planes),
        outline=outline.rings,
        edge_clearance=edge,
        clearance=in_force,
    )
    chosen = {
        pad.position: f"{pad.ref}-{pad.number}"
        for pad in ctx.pads
        if pad.net == net.name
        and not pad.hole
        and ctx.placed(pad)
        and any(entry.layer == face for entry in pad.copper)
        and (not intent.refs or pad.path in intent.refs or pad.ref in intent.refs)
    }
    tracks: list[Track] = []
    vias: list[Via] = []
    for track in plan.tracks:
        label = chosen.get(track.start)
        if label is None or track.layer != face:
            continue
        via = next(via for via in plan.vias if via.position == track.end)
        tracks.append(
            dataclasses.replace(
                track,
                id=derived_id("trk", DSL, f"copper:{key}:{label}"),
                native_ids={"kicad": copper_uuid(key, f"{label}/track")},
            )
        )
        vias.append(
            dataclasses.replace(
                via,
                id=derived_id("via", DSL, f"copper:{key}:{label}"),
                native_ids={"kicad": copper_uuid(key, f"{label}/via")},
            )
        )
    labels = set(chosen.values())
    found = [item for item in plan.issues if item.where in labels]
    return tracks, vias, found


def _inside(point: Point, ring: Sequence[Point], reach: int) -> bool:
    """Whether ``point`` lies inside ``ring`` at least ``reach / 2`` from each of its edges."""
    if point_in_ring(point, ring) is not Location.INSIDE:
        return False
    edges = zip(ring, (*ring[1:], ring[0]), strict=True)
    return all(4 * dist2_point_segment(point, a, b) >= reach * reach for a, b in edges)


def _stitch(
    ctx: _Board,
    intent: StitchPiecesLike,
    outline: BoardOutline,
    edge_floor: int,
    keepouts: Sequence[Keepout],
) -> tuple[list[Via], list[Issue]]:
    key = intent.key
    net = ctx.net(intent.net, key)
    design = ctx.current()
    board = design.board
    assert board is not None
    _, diameter, drill = _sizes(ctx, net, (0, intent.diameter, intent.drill), key)
    clearance = _clearance(ctx, net, intent.clearance, key)
    pieces = [
        (zone.name or zone.id, layer, tuple(zone.outline))
        for zone in board.zones
        if zone.net_id == net.id and len(zone.outline) >= 3
        for layer in zone.layers
        if layer in intent.layers
    ]
    overlaps: list[tuple[str, tuple[Point, ...], tuple[Point, ...]]] = []
    for i, (name_a, layer_a, ring_a) in enumerate(pieces):
        for name_b, layer_b, ring_b in pieces[i + 1 :]:
            if layer_a == layer_b:
                continue
            try:
                meet = polygons_intersect(Polygon(ring_a), Polygon(ring_b))
            except (GeometryError, ValueError):
                meet = False
            if meet:
                overlaps.append((f"{name_a}@{layer_a}+{name_b}@{layer_b}", ring_a, ring_b))
    if not overlaps:
        raise _Refused(
            "kicad.generate.no-zone",
            f"{key}: no two zones of {net.name} on different layers of {', '.join(intent.layers)} overlap",
            key,
            "declare the pours of the net first, on two layers",
        )
    reach = diameter + 2 * intent.margin
    pitch = intent.pitch
    foreign = [
        tuple(zone.outline)
        for zone in board.zones
        if zone.net_id != net.id and len(zone.outline) >= 3 and set(zone.layers) & set(intent.layers)
    ]
    gap = 2 * clearance + diameter

    def free(point: Point) -> bool:
        """Outside every zone of another net on the layers, by the clearance and half a diameter: a via
        there would join only one of its pieces."""
        for ring in foreign:
            if point_in_ring(point, ring) is not Location.OUTSIDE:
                return False
            edges = zip(ring, (*ring[1:], ring[0]), strict=True)
            if any(4 * dist2_point_segment(point, a, b) < gap * gap for a, b in edges):
                return False
        return True

    candidates: dict[Point, str] = {}
    for _, ring_a, ring_b in overlaps:
        box = BBox.of_points(ring_a)
        other = BBox.of_points(ring_b)
        x0, y0 = max(box.x0, other.x0), max(box.y0, other.y0)
        x1, y1 = min(box.x1, other.x1), min(box.y1, other.y1)
        for j in range(-(-y0 // pitch), y1 // pitch + 1):
            for i in range(-(-x0 // pitch), x1 // pitch + 1):
                point = Point(i * pitch, j * pitch)
                if (
                    point not in candidates
                    and _inside(point, ring_a, reach)
                    and _inside(point, ring_b, reach)
                    and free(point)
                ):
                    candidates[point] = f"via[{i},{j}]"
    ordered = sorted(candidates.items(), key=lambda item: (item[0].y, item[0].x))
    kept, _ = stitch_vias(
        design,
        key,
        net.name,
        [(locator, point) for point, locator in ordered],
        sizes=(diameter, drill),
        clearance=clearance,
        unplaced=ctx.unplaced,
        keepouts=keepouts,
        outline=outline,
        edge_floor=edge_floor,
    )
    found: list[Issue] = []
    for label, ring_a, ring_b in overlaps:
        count = sum(
            1 for via in kept if _inside(via.position, ring_a, reach) and _inside(via.position, ring_b, reach)
        )
        if count < intent.min_vias:
            found.append(
                issue(
                    "kicad.generate.stitch-short",
                    f"{key}: the overlap {label} holds {count} via(s), fewer than {intent.min_vias}",
                    key,
                    "reduce the pitch, the margin or the via size, or enlarge the overlap",
                )
            )
    return list(kept), found


# --- resolution -----------------------------------------------------------------------------------------


def resolve_generated(
    design: Design,
    intents: Sequence[GeneratedLike],
    *,
    unplaced: Collection[str] = (),
    issues: list[Issue] | None = None,
    keepouts: Sequence[Keepout] = (),
    outline: BoardOutline | None = None,
    edge_floor: Nm = 0,
) -> Design:
    """``design`` with what ``intents`` generate, resolved in the order of ``CALLS`` and then by key: zones
    and rule areas after those of the design, tracks and vias after its copper. A record with an error
    creates nothing and adds its issue; ``unplaced`` names the components the build staged. Fan-out and
    stitch vias avoid the rule areas of the design and the ``keepouts`` given besides (a rebuild passes
    those of the existing board), and keep the edge clearance in force (``edge_floor`` is the project's
    ``min_copper_edge_clearance``). Nothing is read or written."""
    found: list[Issue] = []
    if not intents:
        return design
    if design.board is None:
        if issues is not None:
            issues.append(
                issue("kicad.generate.unknown", "the design has no board to generate copper on", "")
            )
        return design
    ctx = _Board(
        design=design,
        pads=board_pads(design),
        unplaced=frozenset(unplaced),
        nets={net.name: net for net in design.circuit.nets},
        classes={cls.id: cls for cls in design.circuit.netclasses},
    )
    ring = outline if outline is not None else board_outline(design)
    edge = edge_clearance_in_force(design, edge_floor)
    order = {call: index for index, call in enumerate(CALLS)}
    for intent in sorted(intents, key=lambda item: (order.get(item.call, len(order)), item.key)):
        try:
            if intent.call == "keepout_ring":
                ctx.keepouts += _ring(ctx, cast(RingLike, intent))
            elif intent.call == "body_keepout":
                ctx.keepouts += _body(ctx, cast(BodyLike, intent))
            elif intent.call == "barrier":
                areas, warned = _barrier(ctx, cast(BarrierLike, intent))
                ctx.keepouts += areas
                found += warned
            elif intent.call == "band":
                zones, warned = _band(ctx, cast(BandLike, intent), ring)
                ctx.zones += zones
                found += warned
            elif intent.call == "fanout_zone":
                tracks, vias, warned = _fanout(ctx, cast(FanoutLike, intent), ring, edge)
                ctx.tracks += tracks
                ctx.vias += vias
                found += warned
            elif intent.call == "stitch_pieces":
                vias, warned = _stitch(ctx, cast(StitchPiecesLike, intent), ring, edge_floor, keepouts)
                ctx.vias += vias
                found += warned
            else:
                raise _Refused(
                    "kicad.generate.unknown", f"{intent.key}: {intent.call!r} is no generator", intent.key
                )
        except _Refused as refused:
            found.append(refused.issue)
        except GeometryError as error:
            found.append(issue("kicad.generate.unknown", f"{intent.key}: {error}", intent.key))
    if issues is not None:
        issues.extend(found)
    return ctx.current()


__all__ = [
    "CALLS",
    "EVIDENCE",
    "GENERATE_ISSUE_CODES",
    "AreaLike",
    "BandLike",
    "BarrierLike",
    "BodyLike",
    "FanoutLike",
    "GeneratedLike",
    "RingLike",
    "StitchPiecesLike",
    "disc",
    "halves",
    "issue",
    "resolve_generated",
]
