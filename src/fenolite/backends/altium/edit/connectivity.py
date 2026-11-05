# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper connectivity of a PCB document that the commit of an edit session compares (capability
altium-edit, "Commit gates"; change c0241).

The pads, tracks, arcs and vias are joined where their copper touches on a shared layer: a track or an arc
as a stroke of its width, a pad as its top, middle or bottom box (a circle of its larger size when it is
turned by other than a quarter turn), a via as a disc of its diameter on the layers it spans. Poured copper
is left out: a pour is computed again by the native tool. The signature of a document is the set of net
pairs that some joined group holds (a short) and, per net, the number of groups that hold its pads (an
open when it grows). It is a geometric reading by Fenolite, not a design-rule check.
"""

# evidence: see edit.session

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from fenolite.backends.altium.read.pcb import PcbDocument
from fenolite.backends.altium.read.pcbprims import ArcRecord, PadRecord, TrackRecord, ViaRecord

MULTI_LAYER = 74
COPPER = range(1, 33)
CELL = 400_000
"""The side of a cell of the spatial hash: 40 mil in units."""
SLACK = 2


@dataclass(frozen=True, slots=True)
class _Shape:
    """One copper piece: a stroke (``ax``…``by`` with half width ``r``) or a box (``ax``…``by``)."""

    net: int | None
    layers: frozenset[int]
    stroke: bool
    ax: float
    ay: float
    bx: float
    by: float
    r: float
    pad: bool

    def bounds(self) -> tuple[float, float, float, float]:
        if self.stroke:
            return (min(self.ax, self.bx) - self.r, min(self.ay, self.by) - self.r,
                    max(self.ax, self.bx) + self.r, max(self.ay, self.by) + self.r)  # fmt: skip
        return self.ax, self.ay, self.bx, self.by


def _point_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segments_cross(a: _Shape, b: _Shape) -> bool:
    def orient(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    o1 = orient(a.ax, a.ay, a.bx, a.by, b.ax, b.ay)
    o2 = orient(a.ax, a.ay, a.bx, a.by, b.bx, b.by)
    o3 = orient(b.ax, b.ay, b.bx, b.by, a.ax, a.ay)
    o4 = orient(b.ax, b.ay, b.bx, b.by, a.bx, a.by)
    return o1 * o2 < 0 and o3 * o4 < 0


def _segment_distance(a: _Shape, b: _Shape) -> float:
    if _segments_cross(a, b):
        return 0.0
    return min(
        _point_segment(a.ax, a.ay, b.ax, b.ay, b.bx, b.by),
        _point_segment(a.bx, a.by, b.ax, b.ay, b.bx, b.by),
        _point_segment(b.ax, b.ay, a.ax, a.ay, a.bx, a.by),
        _point_segment(b.bx, b.by, a.ax, a.ay, a.bx, a.by),
    )


def _box_segment(box: _Shape, s: _Shape) -> float:
    inside = box.ax <= s.ax <= box.bx and box.ay <= s.ay <= box.by
    if inside or (box.ax <= s.bx <= box.bx and box.ay <= s.by <= box.by):
        return 0.0
    corners = ((box.ax, box.ay), (box.bx, box.ay), (box.bx, box.by), (box.ax, box.by))
    edges = [_Shape(None, box.layers, True, *corners[i], *corners[(i + 1) % 4], 0.0, False) for i in range(4)]
    return min(_segment_distance(edge, s) for edge in edges)


def _touch(a: _Shape, b: _Shape) -> bool:
    if not a.layers & b.layers:
        return False
    if a.stroke and b.stroke:
        return _segment_distance(a, b) <= a.r + b.r + SLACK
    if not a.stroke and not b.stroke:
        return a.ax <= b.bx + SLACK and b.ax <= a.bx + SLACK and a.ay <= b.by + SLACK and b.ay <= a.by + SLACK
    box, stroke = (a, b) if b.stroke else (b, a)
    return _box_segment(box, stroke) <= stroke.r + SLACK


def _pad_shapes(pad: PadRecord) -> Iterable[_Shape]:
    layers = frozenset(COPPER) if pad.prefix.layer == MULTI_LAYER else frozenset({pad.prefix.layer})
    quarter = math.isclose((pad.rotation % 90.0), 0.0, abs_tol=1e-6) or math.isclose(
        pad.rotation % 90.0, 90.0
    )
    turned = round(pad.rotation / 90.0) % 2 == 1
    sizes = (
        {pad.size_top, pad.size_mid, pad.size_bottom} if pad.prefix.layer == MULTI_LAYER else {pad.size_top}
    )
    for sx, sy in sizes:
        if not quarter:
            r = max(sx, sy) / 2
            yield _Shape(pad.prefix.net, layers, True, pad.x, pad.y, pad.x, pad.y, r, True)
            continue
        hx, hy = (sy / 2, sx / 2) if turned else (sx / 2, sy / 2)
        yield _Shape(pad.prefix.net, layers, False, pad.x - hx, pad.y - hy, pad.x + hx, pad.y + hy, 0.0, True)


def _arc_strokes(arc: ArcRecord) -> Iterable[_Shape]:
    start, end = arc.start_angle, arc.end_angle
    sweep = (end - start) % 360.0 or 360.0
    steps = max(2, math.ceil(sweep / 15.0))
    points = [
        (arc.cx + arc.radius * math.cos(math.radians(start + sweep * k / steps)),
         arc.cy + arc.radius * math.sin(math.radians(start + sweep * k / steps)))
        for k in range(steps + 1)
    ]  # fmt: skip
    for (ax, ay), (bx, by) in zip(points, points[1:], strict=False):
        yield _Shape(
            arc.prefix.net, frozenset({arc.prefix.layer}), True, ax, ay, bx, by, arc.width / 2, False
        )


def shapes(doc: PcbDocument) -> list[_Shape]:
    """The copper pieces of ``doc`` outside pours."""
    out: list[_Shape] = []
    for pad in doc.pads:
        if isinstance(pad, PadRecord):
            out += _pad_shapes(pad)
    for track in doc.tracks:
        if isinstance(track, TrackRecord) and track.prefix.layer in COPPER and track.prefix.polygon is None:
            out.append(_Shape(track.prefix.net, frozenset({track.prefix.layer}), True, track.x1, track.y1,
                              track.x2, track.y2, track.width / 2, False))  # fmt: skip
    for arc in doc.arcs:
        if isinstance(arc, ArcRecord) and arc.prefix.layer in COPPER and arc.prefix.polygon is None:
            out += _arc_strokes(arc)
    for via in doc.vias:
        if isinstance(via, ViaRecord):
            low, high = sorted((via.start_layer, via.end_layer))
            layers = frozenset(range(low, high + 1)) if low >= 1 else frozenset(COPPER)
            out.append(
                _Shape(via.prefix.net, layers, True, via.x, via.y, via.x, via.y, via.diameter / 2, False)
            )
    return out


@dataclass(frozen=True, slots=True)
class Signature:
    """The shorts (pairs of net names) and the number of pad groups of each net."""

    shorts: frozenset[tuple[str, str]]
    groups: tuple[tuple[str, int], ...]


def signature(doc: PcbDocument) -> Signature:
    pieces = shapes(doc)
    parent = list(range(len(pieces)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for number, piece in enumerate(pieces):
        x0, y0, x1, y1 = piece.bounds()
        for cx in range(math.floor(x0 / CELL), math.floor(x1 / CELL) + 1):
            for cy in range(math.floor(y0 / CELL), math.floor(y1 / CELL) + 1):
                cells[(cx, cy)].append(number)
    seen: set[tuple[int, int]] = set()
    for members in cells.values():
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                if root(a) != root(b) and _touch(pieces[a], pieces[b]):
                    parent[root(a)] = root(b)
    names: dict[int | None, str] = {None: ""}
    for index, net in enumerate(doc.nets):
        names[index] = net.name or ""
    held: dict[int, set[str]] = defaultdict(set)
    pad_groups: dict[str, set[int]] = defaultdict(set)
    for number, piece in enumerate(pieces):
        name = names.get(piece.net, "")
        if name:
            held[root(number)].add(name)
            if piece.pad:
                pad_groups[name].add(root(number))
    shorts = {(a, b) for nets in held.values() for a in nets for b in nets if a < b}
    return Signature(frozenset(shorts), tuple(sorted((net, len(g)) for net, g in pad_groups.items())))


def changes(before: Signature, after: Signature) -> list[tuple[tuple[str, ...], str]]:
    """The nets each change names and a sentence: a new short, or a net whose pads lie in more or fewer
    groups."""
    out: list[tuple[tuple[str, ...], str]] = []
    for a, b in sorted(after.shorts - before.shorts):
        out.append(((a, b), f"the copper of {a} now touches the copper of {b}"))
    for a, b in sorted(before.shorts - after.shorts):
        out.append(((a, b), f"the copper of {a} no longer touches the copper of {b}"))
    old, new = dict(before.groups), dict(after.groups)
    for net in sorted(set(old) | set(new)):
        if old.get(net, 0) != new.get(net, 0):
            out.append(
                ((net,), f"the pads of {net} lie in {new.get(net, 0)} groups, before {old.get(net, 0)}")
            )
    return out


__all__ = ["Signature", "changes", "shapes", "signature"]
