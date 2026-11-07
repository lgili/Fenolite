# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Narrow exact native pad/via cache proof helpers (c0340; S-1208).

This module does not alter the editable model, ordinary zones or pure equivalence.
A successful common-tool proof must still compare all existing model levels.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TypeAlias
from uuid import UUID

from fenolite.backends.kicad.layers import COPPER_ROW_TYPES
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.backends.kicad.teardrops import project
from fenolite.core.evidence import Evidence, Level
from fenolite.core.trig import ONE, cos_sin_fixed

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DERIVED-TD-PROOF",))
"""Qualification and exact comparison only; native execution remains separately source-bound."""

Point: TypeAlias = tuple[Fraction, Fraction]
Tree: TypeAlias = tuple[object, ...]
ZONE_KEYS = frozenset(
    {
        "net",
        "net_name",
        "name",
        "layer",
        "layers",
        "uuid",
        "tstamp",
        "priority",
        "attr",
        "hatch",
        "connect_pads",
        "min_thickness",
        "filled_areas_thickness",
        "fill",
        "polygon",
        "filled_polygon",
    }
)


def _one(node: Node, name: str) -> Node:
    found = node.nodes(name)
    if len(found) != 1:
        raise ValueError(f"{node.name} requires exactly one {name}")
    return found[0]


def _word(node: Node, name: str) -> str:
    child = _one(node, name)
    if child.nodes() or len(child.atoms()) != 1:
        raise ValueError(f"malformed {name}")
    return child.atoms()[0].value


def _xy(node: Node) -> Point:
    atoms = node.atoms()
    if len(atoms) != 2 or node.nodes() or any(a.kind != AtomKind.NUMBER for a in atoms):
        raise ValueError("malformed exact point")
    return Fraction(atoms[0].text), Fraction(atoms[1].text)


def _ring(node: Node) -> tuple[Point, ...]:
    if node.atoms() or any(c.name != "xy" for c in node.nodes()):
        raise ValueError("only exact polygon vertices qualify")
    points = tuple(_xy(c) for c in node.nodes())
    if len(points) < 3 or len(set(points)) < 3:
        raise ValueError("degenerate cache ring")
    area2 = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, (*points[1:], points[0]), strict=True))
    if not area2:
        raise ValueError("zero-area cache ring")

    # Keep every exact vertex and its multiplicity; normalize only start and direction.
    return min(ring[i:] + ring[:i] for ring in (points, tuple(reversed(points))) for i in range(len(ring)))


def crossing_count(ring: tuple[Point, ...]) -> int:
    """Exact proper edge-pair crossing count; no geometry change or validity claim."""

    def orient(a: Point, b: Point, c: Point) -> Fraction:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    edges = tuple(zip(ring, (*ring[1:], ring[0]), strict=True))
    return sum(
        1
        for i, (a, b) in enumerate(edges)
        for c, d in edges[i + 1 :]
        if orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0
    )


def crossing_counts(root: Node) -> dict[str, int]:
    """Counts over complete derived outline/fill rings; original data are never normalized away."""
    counts = [
        crossing_count(_ring(_one(poly, "pts")))
        for zone in root.nodes("zone")
        if _derived(zone)
        for poly in (*zone.nodes("polygon"), *zone.nodes("filled_polygon"))
    ]
    return {
        "rings_with_proper_crossings": sum(bool(value) for value in counts),
        "proper_edge_pair_crossings": sum(counts),
    }


def _tree(node: Node | Atom) -> Tree:
    if isinstance(node, Atom):
        if node.kind == AtomKind.NUMBER:
            value = Fraction(node.text)
            return "number", value.numerator, value.denominator
        return node.kind.value, node.value
    if node.name == "pts":
        return "pts", tuple((x.numerator, x.denominator, y.numerator, y.denominator) for x, y in _ring(node))
    return node.name, tuple(_tree(c) for c in node.children)


def _derived(zone: Node) -> bool:
    attr = zone.nodes("attr")
    if not attr:
        return False
    if len(attr) != 1 or attr[0].atoms() or len(attr[0].nodes()) != 1:
        raise ValueError("unqualified zone attributes")
    teardrop = _one(attr[0], "teardrop")
    if teardrop.atoms() or len(teardrop.nodes()) != 1 or _word(teardrop, "type") != "padvia":
        raise ValueError("only padvia derived caches qualify")
    return True


def native_net(node: Node, root: Node) -> str:
    net = _one(node, "net")
    atoms = list(net.atoms())
    if net.nodes() or not atoms or len(atoms) > 2:
        raise ValueError("malformed net")
    if atoms[-1].kind == AtomKind.STRING:
        return atoms[-1].value
    if len(atoms) != 1:
        raise ValueError("malformed net code")
    matches = [n.atoms() for n in root.nodes("net") if n.atoms() and n.atoms()[0].value == atoms[0].value]
    if len(matches) != 1 or len(matches[0]) != 2 or matches[0][1].kind != AtomKind.STRING:
        raise ValueError("cache net code has no unique declaration")
    return matches[0][1].value


def _scalar(node: Node, *, positive: bool = False) -> Fraction:
    atoms = node.atoms()
    if node.nodes() or len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
        raise ValueError("malformed derived numeric setting")
    value = Fraction(atoms[0].text)
    if value < 0 or (positive and value == 0):
        raise ValueError("invalid derived numeric setting")
    return value


def _metadata(zone: Node) -> None:
    if zone.nodes("name") and _word(zone, "name") != "$teardrop_padvia$":
        raise ValueError("unqualified named derived cache")
    for name in ("uuid", "tstamp"):
        if zone.nodes(name):
            UUID(_word(zone, name))
    if zone.nodes("min_thickness"):
        _scalar(_one(zone, "min_thickness"), positive=True)
    if zone.nodes("filled_areas_thickness") and _word(zone, "filled_areas_thickness") not in {"yes", "no"}:
        raise ValueError("malformed filled thickness flag")
    if zone.nodes("hatch"):
        hatch = _one(zone, "hatch")
        atoms = hatch.atoms()
        if (
            hatch.nodes()
            or len(atoms) != 2
            or atoms[0].kind != AtomKind.SYMBOL
            or atoms[0].value not in {"edge", "none", "full"}
            or atoms[1].kind != AtomKind.NUMBER
        ):
            raise ValueError("unqualified hatch metadata")
        if Fraction(atoms[1].text) <= 0:
            raise ValueError("invalid hatch pitch")
    for name, allowed in (
        ("connect_pads", {"clearance"}),
        ("fill", {"thermal_gap", "thermal_bridge_width", "island_removal_mode", "island_area_min"}),
    ):
        if not zone.nodes(name):
            continue
        item = _one(zone, name)
        atoms = item.atoms()
        valid_flags = {"yes", "no"} if name == "fill" else {"yes", "no", "thru_hole_only"}
        if len(atoms) > 1 or (
            atoms and (atoms[0].kind != AtomKind.SYMBOL or atoms[0].value not in valid_flags)
        ):
            raise ValueError("malformed derived metadata flag")
        if any(c.name not in allowed for c in item.nodes()):
            raise ValueError("unknown derived cache nested field")
        for key in allowed:
            if len(item.nodes(key)) > 1:
                raise ValueError("duplicate derived cache nested field")
            if item.nodes(key):
                value = _scalar(_one(item, key))
                if key == "island_removal_mode" and (value.denominator != 1 or value != 1):
                    raise ValueError("invalid native island removal mode")


def regions(root: Node, nets: Mapping[str, tuple[str, ...]]) -> tuple[Tree, ...]:
    """Complete exact derived geometry/settings multiset, with L2-verified net partition bindings.

    Only identifiers and derived priority ordinals are excluded. All polygon and fill children,
    including holes/islands, layer and duplicate multiplicity remain part of the equality key.
    """
    found: list[Tree] = []
    for zone in root.nodes("zone"):
        if not _derived(zone):
            continue
        _metadata(zone)
        if zone.atoms() or any(c.name not in ZONE_KEYS for c in zone.nodes()):
            raise ValueError("unknown derived cache field")
        for key in ZONE_KEYS - {"polygon", "filled_polygon"}:
            if len(zone.nodes(key)) > 1:
                raise ValueError(f"duplicate derived cache {key}")
        if zone.nodes("priority"):
            priority = _one(zone, "priority")
            atoms = priority.atoms()
            if priority.nodes() or len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
                raise ValueError("malformed derived priority ordinal")
            value = Fraction(atoms[0].text)
            if value.denominator != 1 or value < 0:
                raise ValueError("malformed derived priority ordinal")
        if zone.nodes("layer") and zone.nodes("layers"):
            raise ValueError("ambiguous derived copper layer")
        if zone.nodes("net_name") and _word(zone, "net_name") != native_net(zone, root):
            raise ValueError("contradictory derived net name")
        if not zone.nodes("polygon"):
            raise ValueError("cache lacks polygon")
        for polygon in (*zone.nodes("polygon"), *zone.nodes("filled_polygon")):
            allowed = {"pts"} if polygon.name == "polygon" else {"pts", "layer", "island"}
            if polygon.atoms() or any(c.name not in allowed for c in polygon.nodes()):
                raise ValueError("unknown derived polygon field")
            for key in allowed:
                if len(polygon.nodes(key)) > 1:
                    raise ValueError("duplicate derived polygon field")
            _one(polygon, "pts")
            if polygon.nodes("island"):
                if _word(polygon, "island") != "yes":
                    raise ValueError("unqualified island marker")
            if polygon.nodes("layer"):
                layer = _one(polygon, "layer")
                if layer.nodes() or len(layer.atoms()) != 1 or layer.atoms()[0].kind != AtomKind.STRING:
                    raise ValueError("malformed filled layer")
        name = native_net(zone, root)
        if name not in nets or not nets[name]:
            raise ValueError("cache net has no verified numbered-pad partition")
        if zone.nodes("layer"):
            layer = _word(zone, "layer")
            if not layer.endswith(".Cu"):
                raise ValueError("derived cache must be copper")
        elif not zone.nodes("layers"):
            raise ValueError("cache lacks copper layer")
        children = tuple(
            sorted(
                (
                    _tree(c)
                    for c in zone.children
                    if not isinstance(c, Node)
                    or c.name not in {"net", "net_name", "uuid", "tstamp", "priority"}
                ),
                key=repr,
            )
        )
        found.append((nets[name], children))
    return tuple(sorted(found, key=repr))


def _inside(point: Point, ring: tuple[Point, ...]) -> bool:
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(ring, (*ring[1:], ring[0]), strict=True):
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross == 0 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            return True
        if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay):
            inside = not inside
    return inside


QUARTER = 90_000_000
FULL = 360_000_000
MARGIN = Fraction(1, 2**100)
"""Bound on the error of a non-quarter pose (c0413).

``cos_sin_fixed`` is within 2**-128 of cos and sin. With every coordinate within ``FRAME`` mm, a turned pad
centre and a point in the pad frame are each within 2**-113 mm of their exact values, far inside this bound.
"""
FRAME = Fraction(4096)
"""Coordinates beyond this many millimetres refuse a non-quarter pose (KiCad boards stay within ±2148 mm)."""


def _at(node: Node) -> tuple[Point, int]:
    """Position and angle in whole microdegrees, in ``[0, FULL)``; a finer angle refuses (c0413)."""
    at = _one(node, "at")
    atoms = at.atoms()
    if at.nodes() or len(atoms) not in (2, 3) or any(a.kind != AtomKind.NUMBER for a in atoms):
        raise ValueError("malformed parent pose")
    angle = Fraction(atoms[2].text) * 1_000_000 if len(atoms) == 3 else Fraction(0)
    if angle.denominator != 1:
        raise ValueError("inexact parent angle")
    return (Fraction(atoms[0].text), Fraction(atoms[1].text)), int(angle) % FULL


def _cos_sin(udeg: int) -> tuple[Fraction, Fraction, bool]:
    """Exact at quarter turns; otherwise the fixed-point values, flagged inexact."""
    quarter, rest = divmod(udeg % FULL, QUARTER)
    if not rest:
        return ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)), (Fraction(-1), Fraction(0)),
                (Fraction(0), Fraction(-1)))[quarter] + (True,)  # fmt: skip
    c, s = cos_sin_fixed(udeg)
    return Fraction(c, ONE), Fraction(s, ONE), False


def _turn(point: Point, udeg: int) -> tuple[Point, bool]:
    """The board-frame image of a footprint-frame offset (KiCad's Y-down, counter-clockwise angle)."""
    c, s, exact = _cos_sin(udeg)
    x, y = point
    return (x * c + y * s, -x * s + y * c), exact


def _d2(a: Point, b: Point) -> Fraction:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _point_segment_d2(p: Point, a: Point, b: Point) -> Fraction:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if not length2:
        return _d2(p, a)
    t = min(Fraction(1), max(Fraction(0), ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return _d2(p, (a[0] + t * dx, a[1] + t * dy))


def _orient(a: Point, b: Point, c: Point) -> Fraction:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_meet(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Closed segments share a point, exactly (collinear overlap included)."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    return any(
        o == 0 and min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])
        for o, p, q, r in ((o1, a, b, c), (o2, a, b, d), (o3, c, d, a), (o4, c, d, b))
    )


def _segment_d2(a: Point, b: Point, c: Point, d: Point) -> Fraction:
    if _segments_meet(a, b, c, d):
        return Fraction(0)
    return min(
        _point_segment_d2(a, c, d), _point_segment_d2(b, c, d),
        _point_segment_d2(c, a, b), _point_segment_d2(d, a, b),
    )  # fmt: skip


def _within(d2: Fraction, radius: Fraction) -> bool:
    return radius >= 0 and d2 <= radius * radius


@dataclass(frozen=True)
class _Body:
    """One known copper subset of a custom pad in the pad frame (c0413).

    ``capsule``: the points within ``radius`` of the segment ``points``; ``disc``: within ``radius`` of
    ``points[0]`` (``radius2`` exact, ``radius`` a lower and ``outer`` an upper bound); ``polygon``: the
    closed ring ``points``, used only by an exact (quarter-turn) parent.
    """

    kind: str
    points: tuple[Point, ...]
    radius: Fraction = Fraction(0)
    radius2: Fraction = Fraction(0)
    outer: Fraction = Fraction(0)

    def contains(self, q: Point, grow: Fraction) -> bool:
        if self.kind == "capsule":
            return _within(_point_segment_d2(q, *self.points), self.radius + grow)
        if self.kind == "disc":
            d2 = _d2(q, self.points[0])
            if not grow:
                return d2 <= self.radius2
            return _within(d2, (self.radius if grow < 0 else self.outer) + grow)
        return _inside(q, self.points)

    def intersects(self, a: Point, b: Point, grow: Fraction) -> bool:
        if self.kind == "capsule":
            return _within(_segment_d2(a, b, *self.points), self.radius + grow)
        if self.kind == "disc":
            d2 = _point_segment_d2(self.points[0], a, b)
            if not grow:
                return d2 <= self.radius2
            return _within(d2, (self.radius if grow < 0 else self.outer) + grow)
        edges = zip(self.points, (*self.points[1:], self.points[0]), strict=True)
        return (
            _inside(a, self.points)
            or _inside(b, self.points)
            or any(_segments_meet(a, b, c, d) for c, d in edges)
        )


def _pad_contains(shape: str, size: Point, corner: Fraction, q: Point) -> bool:
    x, y = q
    hx, hy = size[0] / 2, size[1] / 2
    if hx < 0 or hy < 0:
        return False
    if shape == "rect":
        return abs(x) <= hx and abs(y) <= hy
    if shape == "circle":
        return x * x + y * y <= hx * hx
    # Native oval pads are the capsule formed by a line segment and circular end caps.
    radius = corner if shape == "roundrect" else min(hx, hy)
    dx = max(abs(x) - (hx - radius), Fraction(0))
    dy = max(abs(y) - (hy - radius), Fraction(0))
    return dx * dx + dy * dy <= radius * radius


def _pad_intersects(shape: str, size: Point, corner: Fraction, start: Point, end: Point) -> bool:
    hx, hy = size[0] / 2, size[1] / 2
    if hx < 0 or hy < 0:
        return False
    radius = corner if shape == "roundrect" else min(hx, hy) if shape in {"circle", "oval"} else Fraction(0)

    def rectangle(x: Fraction, y: Fraction) -> bool:
        lo, hi = Fraction(0), Fraction(1)
        for v, w, bound in zip(start, end, (x, y), strict=True):
            delta = w - v
            if not delta:
                if abs(v) > bound:
                    return False
                continue
            first, last = sorted(((-bound - v) / delta, (bound - v) / delta))
            lo, hi = max(lo, first), min(hi, last)
        return lo <= hi

    if rectangle(hx - radius, hy) or rectangle(hx, hy - radius):
        return True
    for cx in (-(hx - radius), hx - radius):
        for cy in (-(hy - radius), hy - radius):
            if _within(_point_segment_d2((cx, cy), start, end), radius):
                return True
    return False


@dataclass(frozen=True)
class _Parent:
    """An enabled teardrop parent: its anchor shape and known primitive copper (c0340, c0413).

    ``rotation`` is the pad's absolute angle in microdegrees. ``margin`` bounds the error of a non-quarter
    pose: zero means every coordinate is exact. With a margin, a test holds only if it holds for the bodies
    shrunk by it, fails only if it fails for them grown by it, and refuses otherwise.
    """

    center: Point
    net: str
    layers: tuple[str, ...]
    shape: str
    size: Point
    rotation: int
    corner_radius: Fraction = Fraction(0)
    extra: tuple[_Body, ...] = ()
    margin: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        if self.rotation % QUARTER and not self.margin:
            raise ValueError("a non-quarter parent needs its error bound")

    def _local(self, point: Point) -> Point:
        if self.margin and max(abs(v) for v in (*point, *self.center)) > FRAME:
            raise ValueError("non-quarter parent outside the bounded board frame")
        c, s, _ = _cos_sin(self.rotation)
        x, y = point[0] - self.center[0], point[1] - self.center[1]
        return x * c - y * s, x * s + y * c

    def _anchor(self, grow: Fraction) -> tuple[Point, Fraction]:
        size = (self.size[0] + 2 * grow, self.size[1] + 2 * grow)
        corner = max(self.corner_radius + grow, Fraction(0)) if self.shape == "roundrect" else Fraction(0)
        return size, corner

    def _decide(self, test: Callable[[Fraction], bool]) -> bool:
        if not self.margin:
            return test(Fraction(0))
        if test(-self.margin):
            return True
        if not test(self.margin):
            return False
        raise ValueError("undecidable non-quarter parent contact")

    def _bodies(self, polygons: bool) -> tuple[_Body, ...]:
        return tuple(b for b in self.extra if polygons or b.kind != "polygon")

    def contains(self, point: Point) -> bool:
        q = self._local(point)

        def test(grow: Fraction) -> bool:
            size, corner = self._anchor(grow)
            return _pad_contains(self.shape, size, corner, q) or any(
                body.contains(q, grow) for body in self._bodies(not self.margin)
            )

        return self._decide(test)

    def intersects(self, a: Point, b: Point) -> bool:
        start, end = self._local(a), self._local(b)

        def test(grow: Fraction) -> bool:
            size, corner = self._anchor(grow)
            return _pad_intersects(self.shape, size, corner, start, end) or any(
                body.intersects(start, end, grow) for body in self._bodies(not self.margin)
            )

        return self._decide(test)

    def centre_in(self, ring: tuple[Point, ...]) -> bool:
        """Whether the anchor centre lies in ``ring``; an approximate centre must clear every edge."""
        inside = _inside(self.center, ring)
        if not self.margin:
            return inside
        edges = zip(ring, (*ring[1:], ring[0]), strict=True)
        if all(not _within(_point_segment_d2(self.center, a, b), self.margin) for a, b in edges):
            return inside
        raise ValueError("undecidable non-quarter parent centre")


def _via_span(root: Node, endpoints: tuple[str, ...]) -> tuple[str, ...]:
    if len(endpoints) != 2:
        raise ValueError("via requires exactly two declared endpoints")
    table = _one(root, "layers")
    if table.atoms():
        raise ValueError("malformed declared layer stack")
    identifiers: set[int] = set()
    names: set[str] = set()
    copper: list[str] = []
    for row in table.nodes():
        atoms = row.atoms()
        if not row.name.isdigit() or row.nodes() or len(atoms) not in (2, 3):
            raise ValueError("malformed declared layer row")
        identifier = int(row.name)
        if atoms[0].kind != AtomKind.STRING or atoms[1].kind != AtomKind.SYMBOL:
            raise ValueError("malformed declared layer name/type")
        name = atoms[0].value
        if identifier in identifiers or name in names:
            raise ValueError("duplicate declared layer identity")
        identifiers.add(identifier)
        names.add(name)
        if name.endswith(".Cu"):
            if atoms[1].value not in COPPER_ROW_TYPES:
                raise ValueError("unknown declared copper row type")
            copper.append(name)
    # Native table order is physical order; ordinals are not physical positions (B.Cu is2 on9/10).
    count = len(copper)
    expected = ["F.Cu", *(f"In{i}.Cu" for i in range(1, count - 1)), "B.Cu"]
    if count < 2 or count > 32 or count % 2 or copper != expected:
        raise ValueError("unknown or inconsistent declared copper stack")
    if any(name not in copper for name in endpoints):
        raise ValueError("via endpoint outside declared copper stack")
    start, end = (copper.index(name) for name in endpoints)
    if start >= end:
        raise ValueError("invalid via endpoint ordering")
    return tuple(copper[start : end + 1])


def _custom_anchor(pad: Node) -> str:
    options = _one(pad, "options")
    if options.atoms() or any(c.name not in {"anchor", "clearance"} for c in options.nodes()):
        raise ValueError("unknown custom anchor options")
    anchor = _one(options, "anchor")
    atoms = anchor.atoms()
    if (
        anchor.nodes()
        or len(atoms) != 1
        or atoms[0].kind != AtomKind.SYMBOL
        or atoms[0].value not in {"rect", "circle"}
    ):
        raise ValueError("unknown/malformed custom anchor")
    if len(options.nodes("clearance")) > 1:
        raise ValueError("duplicate custom clearance options")
    if options.nodes("clearance"):
        clearance = _one(options, "clearance")
        values = clearance.atoms()
        # Both modes shape only the clearance outline; the anchor stays copper (c0413, S-1740).
        if (
            clearance.nodes()
            or len(values) != 1
            or values[0].kind != AtomKind.SYMBOL
            or values[0].value not in {"outline", "convexhull"}
        ):
            raise ValueError("unknown custom clearance option")
    return atoms[0].value


def _root(value: Fraction) -> tuple[Fraction, Fraction]:
    """Rational bounds ``lo ≤ √value ≤ hi``, 2**-64 apart."""
    scale = 1 << 64
    low = math.isqrt(math.floor(value * scale * scale))
    return Fraction(low, scale), Fraction(low + 1, scale)


def _width(item: Node) -> Fraction | None:
    widths = [*item.nodes("width"), *(w for s in item.nodes("stroke") for w in s.nodes("width"))]
    if len(widths) != 1:
        return None
    try:
        return _scalar(widths[0])
    except ValueError:
        return None


def _filled(item: Node) -> bool:
    fills = item.nodes("fill")
    return (
        len(fills) == 1
        and not fills[0].nodes()
        and [a.value for a in fills[0].atoms()] in (["yes"], ["solid"])
    )


def _primitives(pad: Node) -> tuple[_Body, ...]:
    """Primitive copper Fenolite can bound from inside, in the pad frame (c0413).

    A line is its round-capped stroke; a filled circle its disc; a filled polygon or rectangle its interior.
    The stroke beyond a filled shape, arcs, unfilled shapes, curves and anything malformed add nothing, so
    the result is a subset of the pad's copper.
    """
    bodies: list[_Body] = []
    for group in pad.nodes("primitives"):
        for item in group.nodes():
            try:
                width = _width(item)
                if item.name == "gr_line" and width:
                    a, b = _xy(_one(item, "start")), _xy(_one(item, "end"))
                    bodies.append(_Body("capsule", (a, b), width / 2))
                elif item.name == "gr_circle" and _filled(item):
                    centre, end = _xy(_one(item, "center")), _xy(_one(item, "end"))
                    radius2 = _d2(centre, end)
                    if radius2:
                        low, high = _root(radius2)
                        bodies.append(_Body("disc", (centre,), low, radius2, high))
                elif item.name == "gr_rect" and _filled(item):
                    (x0, y0), (x1, y1) = _xy(_one(item, "start")), _xy(_one(item, "end"))
                    if x0 != x1 and y0 != y1:
                        bodies.append(_Body("polygon", ((x0, y0), (x1, y0), (x1, y1), (x0, y1))))
                elif item.name == "gr_poly" and _filled(item):
                    bodies.append(_Body("polygon", _ring(_one(item, "pts"))))
            except (ValueError, IndexError):
                continue
    return tuple(bodies)


def _parents(root: Node) -> tuple[_Parent, ...]:
    result: list[_Parent] = []
    for node in (*root.nodes("via"), *root.nodes("footprint")):
        position, rotation = _at(node)
        back = node.name == "footprint" and bool(node.nodes("layer")) and _word(node, "layer") == "B.Cu"
        for pad in (node,) if node.name == "via" else node.nodes("pad"):
            settings = pad.nodes("teardrops")
            if not settings:
                continue
            config = project(settings[0]) if len(settings) == 1 else None
            if config is None:
                raise ValueError("malformed parent teardrop settings")
            if not config.enabled or not pad.nodes("net"):
                continue
            if pad.nodes("padstack") or pad.nodes("chamfer") or pad.nodes("chamfer_ratio"):
                # These change the copper body; no unshifted or uncut body may qualify contact.
                continue
            local, pad_rotation = ((Fraction(0), Fraction(0)), 0) if node.name == "via" else _at(pad)
            (x, y), exact = _turn(local, rotation)
            exact = exact and not pad_rotation % QUARTER
            center = (position[0] + x, position[1] + y)
            layers = _one(pad, "layers").atoms()
            if not layers or any(a.kind != AtomKind.STRING for a in layers):
                raise ValueError("malformed parent copper layers")
            parent_layers = tuple(a.value for a in layers)
            if node.name == "via":
                parent_layers = _via_span(root, parent_layers)
            shape = "circle" if node.name == "via" else pad.atoms()[2].value
            offsets = tuple(offset for drill in pad.nodes("drill") for offset in drill.nodes("offset"))
            if offsets:
                if (
                    node.name == "via"
                    or pad.atoms()[1].value != "thru_hole"
                    or shape not in {"rect", "roundrect"}
                    or pad_rotation % QUARTER
                ):
                    continue
                if len(offsets) != 1 or len(pad.nodes("drill")) != 1:
                    raise ValueError("ambiguous drill offset")
                ox, oy = _xy(offsets[0])
                if any((coordinate * 1_000_000).denominator != 1 for coordinate in (ox, oy)):
                    raise ValueError("inexact drill offset; no rounding")
                (ox, oy), _ = _turn((ox, oy), pad_rotation)
                center = (center[0] + ox, center[1] + oy)
            extra: tuple[_Body, ...] = ()
            if shape == "custom":
                shape = _custom_anchor(pad)
                # Bottom-side primitive frames are not measured; the anchor alone stays a subset.
                extra = () if back else _primitives(pad)
            if shape not in {"circle", "rect", "oval", "roundrect"}:
                continue
            size = _one(pad, "size")
            if node.name == "via":
                atoms = size.atoms()
                if size.nodes() or len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
                    raise ValueError("malformed via size")
                dimensions = (Fraction(atoms[0].text), Fraction(atoms[0].text))
            else:
                dimensions = _xy(size)
            if min(dimensions) <= 0 or (shape == "circle" and dimensions[0] != dimensions[1]):
                raise ValueError("malformed parent size")
            radius = Fraction(0)
            if shape == "roundrect":
                ratio = _one(pad, "roundrect_rratio")
                atoms = ratio.atoms()
                if ratio.nodes() or len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
                    raise ValueError("malformed roundrect radius")
                value = Fraction(atoms[0].text)
                if not 0 <= value <= Fraction(1, 2):
                    raise ValueError("roundrect radius outside its exact body")
                radius = min(dimensions) * value
            result.append(
                _Parent(
                    center,
                    native_net(pad, root),
                    parent_layers,
                    shape,
                    dimensions,
                    pad_rotation,
                    radius,
                    extra,
                    Fraction(0) if exact else MARGIN,
                )
            )
    return tuple(result)


def qualifies(root: Node, *, allow_empty: bool = False) -> bool:
    """All derived caches must overlap an enabled same-net/layer parent anchored to copper.

    Any whole-microdegree parent pose; a non-quarter contact the error bound cannot settle refuses
    (c0413). A custom parent is its anchor plus the primitive copper ``_primitives`` bounds from inside.
    Unknown or unattached caches refuse; this is deliberately narrower than all native teardrop features.
    Empty generated caches may qualify only with an enabled attached parent and an independently
    qualified nonempty original.
    """
    try:
        caches = [zone for zone in root.nodes("zone") if _derived(zone)]
        parents = _parents(root)
        tracks = [
            (
                _xy(_one(t, "start")),
                _xy(_one(t, "end")),
                native_net(t, root),
                _word(t, "layer"),
                t.name == "segment",
            )
            for t in (*root.nodes("segment"), *root.nodes("arc"))
        ]
        attached = [
            parent
            for parent in parents
            if any(
                parent.net == tn
                and (layer in parent.layers or "*.Cu" in parent.layers or "F&B.Cu" in parent.layers)
                and (parent.intersects(a, b) if linear else parent.contains(a) or parent.contains(b))
                for a, b, tn, layer, linear in tracks
            )
        ]
        if not caches:
            return allow_empty and bool(attached)
        for zone in caches:
            net, layer = native_net(zone, root), _word(zone, "layer")
            rings = tuple(_ring(_one(poly, "pts")) for poly in zone.nodes("polygon"))
            ring_facts = tuple(
                (ring, not crossing_count(ring), tuple(zip(ring, (*ring[1:], ring[0]), strict=True)))
                for ring in rings
            )
            if not rings or not any(
                net == parent.net
                and (layer in parent.layers or "*.Cu" in parent.layers or "F&B.Cu" in parent.layers)
                and any(
                    (simple and parent.centre_in(ring)) or any(parent.intersects(a, b) for a, b in edges)
                    for ring, simple, edges in ring_facts
                )
                for parent in attached
            ):
                return False
        return True
    except (ValueError, IndexError):
        return False


def without_regions(root: Node) -> Node:
    """Strip only already-qualified derived padvia nodes from a private native input copy."""
    return root.with_children(
        tuple(
            child
            for child in root.children
            if not (isinstance(child, Node) and child.name == "zone" and _derived(child))
        )
    )
