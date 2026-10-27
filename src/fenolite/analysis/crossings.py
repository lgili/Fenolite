# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Barrier crossings: the free ways across a cut segment on each copper layer, and the connections that must
cross it (capability board-analyses, "Barrier crossings"; user guide ``docs/analyses.md``, "Barrier
crossings").

A cut is a segment drawn across a barrier: a row of pads, a gap between two areas, a slot. On each copper
layer the obstacles along the cut are the copper of every item grown by the clearance in force against a new
track, the board edge and the cut-outs grown by the edge clearance, holes without copper grown by the
clearance, and the rule areas that forbid tracks on that layer. The free intervals left are the ways. A way of
length ``L`` fits ``⌊(L + c) / (w + c)⌋`` tracks of width ``w`` at the clearance ``c``: ``n`` tracks take
``n·w + (n − 1)·c``.

The demand is read from the board: the open connections whose straight line crosses the cut (the tree of
``analysis.connectivity``), and the tracks and arcs whose copper already crosses it, per net.

Positions along a cut are integer nanometres from its first end. The intersections are computed with
``Decimal`` at 50 digits and rounded outward, so an obstacle is never shorter than its exact interval and a
way is never longer.
"""

from __future__ import annotations

import fnmatch
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from math import isqrt

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.codes import issue
from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, copper_layers, loose_copper, net_copper
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import Location, SegmentRelation, Thick, classify_segments, point_in_ring, thick_touch
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CROSSINGS",))
"""Geometry on the board's own copper, proved on authored benches with ways counted by hand."""
DIGITS = 50

_Span = tuple[Decimal, Decimal]


@dataclass(frozen=True, slots=True)
class Cut:
    """A cut segment from ``a`` to ``b``; ``name`` is how the user gave it."""

    name: str
    a: Point
    b: Point


@dataclass(frozen=True, slots=True)
class Obstacle:
    """Where an obstacle lies along the cut, ``start`` to ``end`` in nm from its first end: ``kind`` (pad,
    track, arc, via, fill, edge, cutout, hole or area) and ``where``."""

    start: int
    end: int
    kind: str
    where: str


@dataclass(frozen=True, slots=True)
class Way:
    """A free interval of the cut, ``start`` to ``end`` in nm from its first end (``a`` and ``b`` on the
    board, rounded to the nanometre), its ``length`` and the number of ``tracks`` it fits."""

    start: int
    end: int
    length: int
    tracks: int
    a: Point
    b: Point


@dataclass(frozen=True, slots=True)
class LayerWays:
    layer: str
    ways: tuple[Way, ...]
    tracks: int
    obstacles: tuple[Obstacle, ...] = ()


@dataclass(frozen=True, slots=True)
class Demand:
    """A net that must cross the cut: ``open`` connections whose straight line crosses it, ``routed`` tracks
    and arcs whose copper crosses it."""

    net: str
    open: int
    routed: int


@dataclass(frozen=True, slots=True)
class CrossingRow:
    """One cut: its length, the width and the clearance of a new track, the ways per copper layer, the
    tracks they fit on all layers (``supply``), and the demand."""

    cut: str
    a: Point
    b: Point
    length: int
    width: int | None
    clearance: int | None
    layers: tuple[LayerWays, ...]
    supply: int
    demand: tuple[Demand, ...]
    open: int
    routed: int


@dataclass(frozen=True, slots=True)
class CrossingReport:
    rows: tuple[CrossingRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE
    summary: Mapping[str, int] = field(default_factory=lambda: {})


class CutLine:
    """A segment as ``P0 + t·d``; spans are in ``t``, and ``along`` turns them into nanometres. Callers
    set the ``Decimal`` context (``DIGITS``) around its use."""

    def __init__(self, cut: Cut) -> None:
        self.p0 = cut.a
        self.dx, self.dy = cut.b.x - cut.a.x, cut.b.y - cut.a.y
        self.l2 = self.dx * self.dx + self.dy * self.dy
        self.length = isqrt(self.l2)
        self.root = Decimal(self.l2).sqrt()
        x0, x1 = sorted((cut.a.x, cut.b.x))
        y0, y1 = sorted((cut.a.y, cut.b.y))
        self.box = (x0, y0, x1, y1)

    def near(self, shape: Thick, grow: int) -> bool:
        xs = [p.x for p in shape.core]
        ys = [p.y for p in shape.core]
        reach = shape.width // 2 + grow + 1
        x0, y0, x1, y1 = self.box
        return (
            min(xs) - reach <= x1
            and x0 <= max(xs) + reach
            and min(ys) - reach <= y1
            and y0 <= max(ys) + reach
        )

    def disc(self, c: Point, r: Decimal) -> _Span | None:
        ex, ey = self.p0.x - c.x, self.p0.y - c.y
        a = Decimal(self.l2)
        b = Decimal(2 * (self.dx * ex + self.dy * ey))
        cc = Decimal(ex * ex + ey * ey) - r * r
        disc = b * b - 4 * a * cc
        if disc < 0:
            return None
        root = disc.sqrt()
        return ((-b - root) / (2 * a), (-b + root) / (2 * a))

    def _clip(self, alpha: Decimal, beta: Decimal, lo: Decimal, hi: Decimal) -> _Span | None:
        if beta == 0:
            return (Decimal("-Infinity"), Decimal("Infinity")) if lo <= alpha <= hi else None
        t1, t2 = (lo - alpha) / beta, (hi - alpha) / beta
        return (min(t1, t2), max(t1, t2))

    def capsule(self, a: Point, b: Point, r: Decimal) -> _Span | None:
        """The line inside the points within ``r`` of the segment ``a–b``: a convex set, so the hull of
        its parts (the two end discs and the band between them)."""
        parts = [self.disc(a, r), self.disc(b, r)]
        ux, uy = b.x - a.x, b.y - a.y
        if ux or uy:
            ex, ey = self.p0.x - a.x, self.p0.y - a.y
            norm = Decimal(ux * ux + uy * uy).sqrt()
            side = self._clip(
                Decimal(ux * ey - uy * ex), Decimal(ux * self.dy - uy * self.dx), -r * norm, r * norm
            )
            run = self._clip(
                Decimal(ux * ex + uy * ey),
                Decimal(ux * self.dx + uy * self.dy),
                Decimal(0),
                Decimal(ux * ux + uy * uy),
            )
            if side is not None and run is not None:
                lo, hi = max(side[0], run[0]), min(side[1], run[1])
                if lo <= hi:
                    parts.append((lo, hi))
        found = [part for part in parts if part is not None]
        if not found:
            return None
        return (min(part[0] for part in found), max(part[1] for part in found))

    def inside(self, ring: Sequence[Point]) -> list[_Span]:
        """The spans of ``t`` in ``[0, 1]`` where the line lies inside the ring (non-zero rule)."""
        cuts = {Decimal(0), Decimal(1)}
        n = len(ring)
        for i in range(n):
            e, f = ring[i], ring[(i + 1) % n]
            vx, vy = f.x - e.x, f.y - e.y
            denom = self.dx * vy - self.dy * vx
            if denom == 0:
                continue
            wx, wy = e.x - self.p0.x, e.y - self.p0.y
            t = Decimal(wx * vy - wy * vx) / Decimal(denom)
            v = Decimal(wx * self.dy - wy * self.dx) / Decimal(denom)
            if 0 <= v <= 1 and 0 < t < 1:
                cuts.add(t)
        marks = sorted(cuts)
        spans: list[_Span] = []
        for lo, hi in zip(marks, marks[1:], strict=False):
            mid = (lo + hi) / 2
            at = Point(
                int((self.p0.x + mid * self.dx).to_integral_value()),
                int((self.p0.y + mid * self.dy).to_integral_value()),
            )
            if point_in_ring(at, tuple(ring)) != Location.OUTSIDE:
                if spans and spans[-1][1] == lo:
                    spans[-1] = (spans[-1][0], hi)
                else:
                    spans.append((lo, hi))
        return spans

    def grown(self, shape: Thick, grow: int) -> list[_Span]:
        """The spans of the line inside ``shape`` grown by ``grow``."""
        r = Decimal(shape.width) / 2 + grow
        core = shape.core
        spans: list[_Span] = []
        if shape.filled:
            spans += self.inside(core)
            if r > 0:
                pieces = [(core[i], core[(i + 1) % len(core)]) for i in range(len(core))]
                spans += [s for a, b in pieces if (s := self.capsule(a, b, r)) is not None]
        elif len(core) == 1:
            if (s := self.disc(core[0], r)) is not None:
                spans.append(s)
        else:
            spans += [
                s for a, b in zip(core, core[1:], strict=False) if (s := self.capsule(a, b, r)) is not None
            ]
        return spans

    def along(self, span: _Span) -> tuple[int, int] | None:
        """``span`` in nanometres along the cut, rounded outward and clipped to the cut."""
        lo, hi = max(span[0], Decimal(0)), min(span[1], Decimal(1))
        if lo > hi:
            return None
        start = int((lo * self.root).to_integral_value(ROUND_FLOOR))
        end = int((hi * self.root).to_integral_value(ROUND_CEILING))
        return (max(start, 0), min(end, self.length))

    def point(self, s: int) -> Point:
        if self.length == 0:
            return self.p0
        t = Decimal(s) / self.root
        return Point(
            int((self.p0.x + t * self.dx).to_integral_value()),
            int((self.p0.y + t * self.dy).to_integral_value()),
        )


def fits(length: int, width: int, clearance: int) -> int:
    """The tracks of ``width`` that a way of ``length`` holds at ``clearance``: ``⌊(L + c) / (w + c)⌋``."""
    return max(0, (length + clearance) // (width + clearance))


def _merge(found: Iterable[Obstacle]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted((o.start, o.end) for o in found):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _ways(line: CutLine, blocked: Sequence[Obstacle], width: int, clearance: int) -> tuple[Way, ...]:
    out: list[Way] = []
    at = 0
    for start, end in [*_merge(blocked), (line.length, line.length)]:
        if start > at:
            length = start - at
            out.append(
                Way(at, start, length, fits(length, width, clearance), line.point(at), line.point(start))
            )
        at = max(at, end)
    return tuple(out)


def _layer_matches(names: Sequence[str], layer: str) -> bool:
    for name in names:
        pattern = name.replace("F&B", "[FB]").replace("&", "*")
        if name == layer or fnmatch.fnmatchcase(layer, pattern):
            return True
    return False


def _clearances(design: Design) -> tuple[dict[str, int], int | None, int | None, int | None]:
    """The clearance of each net's class by net name, and the width, the clearance and the edge clearance
    of a new track: the narrowest class width, its class's clearance, and the board-wide edge rule."""
    circuit = design.circuit
    classes = {cls.id: cls for cls in circuit.netclasses}
    by_net = {
        net.name: cls.clearance
        for net in circuit.nets
        if (cls := classes.get(net.netclass_id or "")) is not None and cls.clearance is not None
    }
    widths = sorted((cls.track_width, cls.name) for cls in circuit.netclasses if cls.track_width)
    narrow = next((cls for cls in circuit.netclasses if widths and cls.name == widths[0][1]), None)
    default = next((cls for cls in circuit.netclasses if cls.name == "Default"), None)
    width = widths[0][0] if widths else None
    clearance = narrow.clearance if narrow is not None and narrow.clearance is not None else None
    if clearance is None and default is not None:
        clearance = default.clearance
    edge: int | None = None
    if design.rules is not None:
        found = [
            rule.min
            for rule in design.rules.rules
            if rule.kind == "edge_clearance" and rule.min is not None and rule.selector_a.op == "all"
        ]
        edge = max(found) if found else None
    return dict(by_net), width, clearance, edge


def _obstacles(
    design: Design,
    line: CutLine,
    layers: Sequence[str],
    shapes: Iterable[tuple[CopperShape, str | None]],
    pads: Sequence[BoardPad],
    boundary: BoardBoundary | None,
    by_net: Mapping[str, int],
    clearance: int,
    edge: int,
) -> dict[str, list[Obstacle]]:
    board = design.board
    assert board is not None
    found: dict[str, list[Obstacle]] = defaultdict(list)

    def add(layer_set: Iterable[str], spans: Iterable[_Span], kind: str, where: str) -> None:
        for span in spans:
            placed = line.along(span)
            if placed is None:
                continue
            for layer in layer_set:
                found[layer].append(Obstacle(placed[0], placed[1], kind, where))

    for shape, net in shapes:
        if shape.layer not in layers:
            continue
        grow = max(clearance, by_net.get(net, 0)) if net is not None else clearance
        if line.near(shape.shape, grow):
            add((shape.layer,), line.grown(shape.shape, grow), shape.kind, shape.where)
    for record in pads:
        if record.kind != "np_thru_hole" or not record.hole or record.drill is None:
            continue
        hole = Thick(record.hole, record.drill)
        if line.near(hole, clearance):
            where = f"{record.ref or record.footprint_id}-{record.number}" if record.number else record.ref
            add(layers, line.grown(hole, clearance), "hole", where)
    if boundary is not None and boundary.outer:
        outer = boundary.outer
        inside = line.inside(outer)
        marks = [Decimal(0), *[t for span in inside for t in span], Decimal(1)]
        outside = [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2) if marks[i] < marks[i + 1]]
        edges = Thick((*outer, outer[0]), 0)
        add(layers, outside + line.grown(edges, edge), "edge", "outline")
        for index, ring in enumerate(boundary.cutouts):
            add(layers, line.grown(Thick(ring, 0, filled=True), edge), "cutout", f"cutout {index}")
    for keepout in board.keepouts:
        if not keepout.no_tracks or len(keepout.outline) < 3:
            continue
        held = [layer for layer in layers if _layer_matches(keepout.layers, layer)]
        if held:
            add(held, line.inside(keepout.outline), "area", keepout.name or keepout.id)
    return found


def _demand(
    design: Design, pads: Sequence[BoardPad] | None, cut: Cut, copper: Mapping[str, Sequence[CopperShape]]
) -> list[Demand]:
    report = connectivity(design, pads=pads)
    opened: Counter[str] = Counter()
    for net in report.nets:
        for link in net.open:
            if classify_segments(link.a.position, link.b.position, cut.a, cut.b) != SegmentRelation.DISJOINT:
                opened[net.name] += 1
    routed: Counter[str] = Counter()
    across = Thick((cut.a, cut.b), 0)
    for net, shapes in copper.items():
        crossed = {s.entity_id for s in shapes if s.kind in ("track", "arc") and thick_touch(s.shape, across)}
        if crossed:
            routed[net] = len(crossed)
    names = sorted(set(opened) | set(routed))
    return [Demand(name, opened[name], routed[name]) for name in names]


def analyze_crossings(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    cuts: Sequence[Cut],
    boundary: BoardBoundary | None = None,
    width: int | None = None,
    clearance: int | None = None,
    arc_tol: int = ARC_TOL_NM,
) -> CrossingReport:
    """The ways and the demand of each cut of ``cuts`` on ``design.board``. ``width`` and ``clearance`` are
    those of a new track; without them, the narrowest class width and its class's clearance. ``boundary`` is
    the board's outline and cut-outs; without it the edge is no obstacle."""
    board = design.board
    if board is None:
        return CrossingReport()
    by_net, class_width, class_clearance, edge_rule = _clearances(design)
    width = width if width is not None else class_width
    clearance = clearance if clearance is not None else class_clearance
    issues: list[Issue] = []
    if width is None or clearance is None:
        missing = " and ".join(
            name for name, value in (("width", width), ("clearance", clearance)) if value is None
        )
        issues.append(
            issue(
                "analysis.input-missing",
                f"no {missing} of a new track: the board's classes give none, so no way is counted",
                where="crossings",
                hint="pass --width and --clearance",
            )
        )
    edge = edge_rule if edge_rule is not None else clearance
    records = tuple(pads or ())
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    shapes: list[tuple[CopperShape, str | None]] = [
        (shape, net) for net, held in copper.by_net.items() for shape in held
    ]
    shapes += [(shape, None) for shape in loose_copper(design, pads=pads, arc_tol=arc_tol)]
    layers = copper_layers(board)
    rows: list[CrossingRow] = []
    with localcontext() as context:
        context.prec = DIGITS
        for cut in cuts:
            line = CutLine(cut)
            demand = _demand(design, pads, cut, copper.by_net)
            per_layer: list[LayerWays] = []
            if width is not None and clearance is not None and line.length > 0:
                assert edge is not None
                blocked = _obstacles(design, line, layers, shapes, records, boundary, by_net, clearance, edge)
                for layer in layers:
                    obstacles = sorted(
                        blocked.get(layer, []), key=lambda o: (o.start, o.end, o.kind, o.where)
                    )
                    ways = _ways(line, obstacles, width, clearance)
                    per_layer.append(
                        LayerWays(layer, ways, sum(way.tracks for way in ways), tuple(obstacles))
                    )
            supply = sum(entry.tracks for entry in per_layer)
            opened = sum(entry.open for entry in demand)
            rows.append(
                CrossingRow(
                    cut=cut.name,
                    a=cut.a,
                    b=cut.b,
                    length=line.length,
                    width=width,
                    clearance=clearance,
                    layers=tuple(per_layer),
                    supply=supply,
                    demand=tuple(demand),
                    open=opened,
                    routed=sum(entry.routed for entry in demand),
                )
            )
            if per_layer and opened > supply:
                issues.append(
                    issue(
                        "analysis.crossings-short",
                        f"the cut {cut.name} must carry {opened} open connection(s) and its ways fit "
                        f"{supply} track(s) on all layers",
                        where=cut.name,
                        hint="widen the gaps, move parts, open a layer, or route nets around the barrier",
                    )
                )
    issues += [
        issue(
            "analysis.item-unsupported",
            f"{count} {kind} item(s) could not be shaped and are no obstacle",
            where=kind,
        )
        for kind, count in sorted(copper.unsupported.items())
    ]
    level = Level.UNVERIFIED if copper.unsupported or pads is None else EVIDENCE.level
    summary = {
        "cuts": len(rows),
        "short": sum(1 for found in issues if found.code == "analysis.crossings-short"),
    }
    return CrossingReport(
        tuple(rows), tuple(issues), Evidence(level, hypotheses=EVIDENCE.hypotheses), summary
    )


__all__ = [
    "EVIDENCE",
    "CrossingReport",
    "CrossingRow",
    "Cut",
    "CutLine",
    "Demand",
    "LayerWays",
    "Obstacle",
    "Way",
    "analyze_crossings",
    "fits",
]
