# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The wired layout of a generated schematic sheet (capability ``kicad-schematic``, "Wired sheet layout",
"Power symbols on a generated sheet" and "Net names on a wired sheet"; change c0406).

A sheet is drawn the way public drafting practice describes a readable schematic
(``docs/schematic-drafting.md``): every part with three pins or more is an anchor, drawn unturned; every
two-pin part is drawn beside the anchor pin it serves (a series part in line with the pin, a part between
a signal and a supply ending in a power symbol, a part between two supplies in a decoupling row under the
anchor); the clusters run from left to right along the direction of their pins; supplies are power
symbols, rails pointing up and grounds pointing down; every other net is routed orthogonally on the
1.27 mm grid by an A* search (S-1309) that joins each terminal to the tree of its net; and each drawn
group of a net carries one label, the net's name.

Everything here is a Fenolite choice except the pin frame and the connection rules, which are facts of
``docs/formats/kicad/schematic.md``. Lengths are integer nanometres, no float is used, and two calls with
equal arguments return equal results.
"""

# evidence: see schgen, sch

from __future__ import annotations

import heapq
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.schlayout import (
    GRID,
    ORIGIN_STEP,
    PAGE_MARGIN,
    PAPERS,
    TITLE_BAND,
    RefBox,
    SymbolPlacement,
    label_angle,
    natural_key,
    pin_point,
)
from fenolite.core.coords import Point

STEP = ORIGIN_STEP
CHAR = schlayout.CHAR_ROOM
"""Room kept for one character of a text (as the readable layout keeps it)."""
LINE = ORIGIN_STEP
"""The height kept for one line of a field."""
STUB = ORIGIN_STEP
"""The length of the wire between a pin and the power symbol it ends on."""
GLYPH = ORIGIN_STEP
"""The length of a power symbol's glyph from its pin, and its width."""
CHANNEL = 4 * ORIGIN_STEP
"""The free room between an anchor's side (with its power symbols) and the first column of its parts."""
SLOT_GAP = ORIGIN_STEP
"""The free room between two slots of a column, and between two columns of one cluster."""
CLUSTER_GAP = 6 * ORIGIN_STEP
"""The least free room between two clusters of one sheet column."""
COLUMN_GAP = 8 * ORIGIN_STEP
"""The least routing channel between two sheet columns; it grows with the nets that cross it."""
COLUMN_HEIGHT = 152_400_000
"""The height a column of clusters may take before it wraps into a further column."""
ROUTE_REACH = 101_600_000
"""Two clusters of a net further apart than this (Manhattan, between their boxes) are joined by labels."""
WINDOW = 24
"""The search window of a terminal: the box of the terminal and the tree, grown by this many cells."""
BUDGET = 40_000
"""The most points the search of one terminal expands before the terminal is labelled instead."""
BEND = 6
FLAG_VALUE = "PWR_FLAG"
FLAG_VALUE_RISE = 3_810_000
"""The height of a power flag's Value above its pin (the flag symbol of ``symembed``)."""
CROSS = 12
BUS_KINDS = frozenset({"i2c", "spi", "uart", "usb2"})
"""Interface kinds whose nets are drawn per cluster and joined by labels."""
DRIVERS = frozenset({"output", "power_out", "open_collector", "open_emitter", "tri_state"})
SINKS = frozenset({"input", "power_in"})
_GROUND = re.compile(
    r"^(?:[ADPCSE]?GND\d*|GND[A-Z0-9]{0,2}|0V|VSS[A-Z0-9]{0,2}|EARTH|CHASSIS)$", re.IGNORECASE
)
_NEGATIVE = re.compile(r"^(?:-\d+(?:\.\d+)?V\d*|-V[A-Z0-9]{1,5}|VEE[A-Z0-9]{0,2}|V-|VNEG)$", re.IGNORECASE)
_RAIL = re.compile(
    r"^(?:\+\d+(?:\.\d+)?V\d*[A-Z0-9]{0,4}|\+V[A-Z0-9]{1,5}|\d+V\d*|\d+\.\d+V|"
    r"V(?:CC|DD)[A-Z0-9]{0,3}|V(?:IN|BAT|BUS|SYS|USB|MAIN|SUP|PP)\d*|V\d+V\d*|VPOS)$",
    re.IGNORECASE,
)
SUPPLY_NAMES: tuple[re.Pattern[str], ...] = (_GROUND, _NEGATIVE, _RAIL)
"""The name forms of a supply net: ground, negative and rail (design D2 of change c0406)."""

Box = tuple[int, int, int, int]
_DIRS: Mapping[int, tuple[int, int]] = MappingProxyType({0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)})
"""A sheet angle → its step on the sheet (Y down)."""
_ANGLE_OF: Mapping[tuple[int, int], int] = MappingProxyType({v: k for k, v in _DIRS.items()})


# --- inputs and outputs --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WPin:
    """A pin of a unit in its library frame: number, name, connection point, angle (pointing from the
    connection point to the body) and electrical type."""

    number: str
    name: str
    at: Point
    angle: int
    etype: str = "passive"


@dataclass(frozen=True, slots=True)
class WUnit:
    """One unit to draw: its layout key, pins, body box in the library frame (Y up), the longer of its
    Reference and Value in characters, and whether it is the only unit of its component."""

    key: str
    pins: tuple[WPin, ...]
    body: Box
    text: int = 0
    single: bool = True


@dataclass(frozen=True, slots=True)
class WNet:
    """A net of the sheet: its id, the text of its label on this sheet, its role (``signal``, ``ground``,
    ``negative`` or ``rail``), whether a bus interface names it, and the name its power symbols show."""

    id: str
    text: str
    role: str = "signal"
    bus: bool = False
    value: str = ""


@dataclass(frozen=True, slots=True)
class WLabel:
    """A label of a drawn group of ``net``: at ``at``, turned to ``angle`` degrees; ``group`` numbers the
    groups of one net on the sheet from 0; ``pin`` is the unit key and pin number it lies on, if any."""

    net: str
    at: Point
    angle: int
    group: int
    pin: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class WPower:
    """A power symbol of ``net`` whose pin lies at ``at``, turned by ``rotation`` degrees, of ``kind``
    (``ground`` or ``rail``), its Value written centred at ``value_at``."""

    net: str
    at: Point
    rotation: int
    kind: str
    value_at: Point
    value_angle: int


@dataclass(frozen=True, slots=True)
class WField:
    """Where the Reference and the Value of a unit are written, centred, and their angle in degrees."""

    reference: Point
    value: Point
    angle: int


@dataclass(frozen=True, slots=True)
class WFlag:
    """A power flag of ``net`` whose pin lies at ``at``, its Value written centred at ``value_at``."""

    net: str
    at: Point
    value_at: Point


@dataclass(frozen=True)
class WiredLayout:
    """The drawing of one sheet: the paper; each unit's (and sheet reference's) placement; the field
    poses; the wires (cut at their junctions); the junctions; the labels; the power symbols; the flags;
    whether it fits a paper, and the nets drawn per cluster because a terminal could not be joined."""

    paper: str
    origins: Mapping[str, SymbolPlacement]
    fields: Mapping[str, WField]
    wires: tuple[tuple[Point, Point], ...]
    junctions: tuple[Point, ...]
    labels: tuple[WLabel, ...]
    powers: tuple[WPower, ...]
    flags: tuple[WFlag, ...] = ()
    fits: bool = True
    fallbacks: int = 0
    rooms: tuple[Box, ...] = ()


# --- net roles ----------------------------------------------------------------------------------


def name_role(name: str) -> str:
    """The supply role a net name has by its form (``ground``, ``negative``, ``rail``), else ``""``."""
    if _GROUND.match(name):
        return "ground"
    if _NEGATIVE.match(name):
        return "negative"
    if _RAIL.match(name):
        return "rail"
    return ""


def net_role(name: str, *, power_pin: bool = False, declared: str = "") -> str:
    """The role of a net named ``name``: ``declared`` is ``"ground"`` or ``"power"`` when an interface of
    that kind names it, and ``power_pin`` tells whether a fitted part has a ``power_in`` or ``power_out``
    pin on it (design D2 of change c0406)."""
    by_name = name_role(name)
    if declared == "ground":
        return "ground"
    if declared == "power" or power_pin or by_name:
        if by_name in ("ground", "negative"):
            return by_name
        return "rail"
    return "signal"


def is_supply(role: str) -> bool:
    return role in ("ground", "negative", "rail")


# --- geometry helpers ---------------------------------------------------------------------------


def _up(value: int, step: int = GRID) -> int:
    return -(-value // step) * step


def _down(value: int, step: int = GRID) -> int:
    return (value // step) * step


def _shift(box: Box, dx: int, dy: int) -> Box:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _union(boxes: Sequence[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _grow(box: Box, by: int) -> Box:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def _step(point: Point, angle: int, length: int) -> Point:
    dx, dy = _DIRS[angle]
    return Point(point.x + dx * length, point.y + dy * length)


def _box_of(points: Sequence[Point]) -> Box:
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def text_room(centre: Point, chars: int, lines: int = 1) -> Box:
    """The room of ``lines`` centred lines of ``chars`` characters around ``centre``."""
    half = _up(chars * CHAR // 2 + GRID // 2)
    height = lines * LINE
    return (centre.x - half, centre.y - height // 2, centre.x + half, centre.y + height // 2)


def _rotation_for(lib_angle: int, wanted: int) -> int:
    """The rotation (no mirror) that turns a pin drawn at ``lib_angle`` so it points outwards to the sheet
    angle ``wanted``."""
    for rotation in schlayout.ROTATIONS:
        if label_angle(lib_angle, rotation, "") == wanted:
            return rotation
    raise AssertionError("every outward direction has a rotation")


def _power_rotation(kind: str, towards: int) -> int:
    """The rotation of a power symbol of ``kind`` whose glyph points to the sheet angle ``towards``: the
    ground glyph points down (270) and the rail glyph up (90) when not turned."""
    natural = 270 if kind == "ground" else 90
    return (towards - natural) % 360


def _natural(role: str) -> int:
    """The sheet angle a supply of ``role`` points to: ground and negative down, rails up."""
    return 270 if role in ("ground", "negative") else 90


def _symbol_kind(role: str) -> str:
    return "ground" if role == "ground" else "rail"


@dataclass(frozen=True, slots=True)
class _Placed:
    """A unit at a placement: its pins' sheet points and outward angles, body and pin-line boxes."""

    unit: WUnit
    place: SymbolPlacement
    points: Mapping[str, Point]
    outward: Mapping[str, int]
    body: Box
    lines: tuple[Box, ...]


def _place(unit: WUnit, x: int, y: int, rotation: int = 0, mirror: str = "") -> _Placed:
    origin = Point(x, y)
    points: dict[str, Point] = {}
    outward: dict[str, int] = {}
    lines: list[Box] = []
    for pin in unit.pins:
        point = pin_point(origin, pin.at, rotation, mirror)
        points.setdefault(pin.number, point)
        out = label_angle(pin.angle, rotation, mirror)
        outward.setdefault(pin.number, out)
        # the pin line runs from the connection point towards the body (inwards)
        inner = _step(point, (out + 180) % 360, GRID)
        lines.append(_box_of([point, inner]))
    x0, y0, x1, y1 = unit.body
    corners = [pin_point(origin, Point(a, b), rotation, mirror) for a in (x0, x1) for b in (y0, y1)]
    body = _box_of(corners) if unit.body != (0, 0, 0, 0) else _box_of(list(points.values()) or [origin])
    return _Placed(unit, SymbolPlacement(x, y, rotation, mirror), points, outward, body, tuple(lines))


def _moved(placed: _Placed, dx: int, dy: int) -> _Placed:
    place = placed.place
    return _Placed(
        placed.unit,
        SymbolPlacement(place.x + dx, place.y + dy, place.rotation, place.mirror),
        {k: Point(p.x + dx, p.y + dy) for k, p in placed.points.items()},
        placed.outward,
        _shift(placed.body, dx, dy),
        tuple(_shift(b, dx, dy) for b in placed.lines),
    )


# --- drawing primitives of a cluster -------------------------------------------------------------


@dataclass
class _Drawing:
    """What a cluster (or a sheet) draws, in one frame: units, fixed wires with their nets, power symbols,
    field poses, the rooms nothing may overlap, and the terminals left for the router."""

    units: dict[str, _Placed] = field(default_factory=lambda: {})
    wires: list[tuple[str, Point, Point]] = field(default_factory=lambda: [])
    powers: list[WPower] = field(default_factory=lambda: [])
    fields: dict[str, WField] = field(default_factory=lambda: {})
    rooms: list[Box] = field(default_factory=lambda: [])
    labels: list[WLabel] = field(default_factory=lambda: [])
    flags: list[WFlag] = field(default_factory=lambda: [])

    def boxes(self) -> list[Box]:
        found = list(self.rooms)
        for placed in self.units.values():
            found.append(placed.body)
            found += placed.lines
            found += [_box_of([p]) for p in placed.points.values()]
        for _, a, b in self.wires:
            found.append(_box_of([a, b]))
        return found

    def moved(self, dx: int, dy: int) -> _Drawing:
        def pt(p: Point) -> Point:
            return Point(p.x + dx, p.y + dy)

        return _Drawing(
            {k: _moved(v, dx, dy) for k, v in self.units.items()},
            [(n, pt(a), pt(b)) for n, a, b in self.wires],
            [WPower(p.net, pt(p.at), p.rotation, p.kind, pt(p.value_at), p.value_angle) for p in self.powers],
            {k: WField(pt(f.reference), pt(f.value), f.angle) for k, f in self.fields.items()},
            [_shift(b, dx, dy) for b in self.rooms],
            [WLabel(lb.net, pt(lb.at), lb.angle, lb.group, lb.pin) for lb in self.labels],
            [WFlag(f.net, pt(f.at), pt(f.value_at)) for f in self.flags],
        )

    def merge(self, other: _Drawing) -> None:
        self.units.update(other.units)
        self.wires += other.wires
        self.powers += other.powers
        self.fields.update(other.fields)
        self.rooms += other.rooms
        self.labels += other.labels
        self.flags += other.flags


def _power(drawing: _Drawing, net: WNet, start: Point, towards: int) -> None:
    """A power symbol of ``net`` at ``start``, its glyph pointing to the sheet angle ``towards``, with the
    room of its glyph and of its Value."""
    kind = _symbol_kind(net.role)
    rotation = _power_rotation(kind, towards)
    tip = _step(start, towards, GLYPH)
    dx, dy = _DIRS[towards]
    chars = len(net.value)
    if dy:  # vertical glyph: the Value beyond its tip, level
        centre = _step(tip, towards, LINE // 2 + GRID // 2)
        value = text_room(centre, chars)
    else:  # sideways glyph: the Value beyond its tip, level, starting there
        half = _up(chars * CHAR // 2 + GRID // 2)
        centre = Point(tip.x + dx * (GRID + half), tip.y)
        value = text_room(centre, chars)
    glyph = _box_of([_step(start, towards, GRID // 2), tip])
    across = (towards + 90) % 360
    glyph = _union([glyph, _box_of([_step(tip, across, GRID), _step(tip, (across + 180) % 360, GRID)])])
    drawing.powers.append(WPower(net.id, start, rotation, kind, centre, 0))
    drawing.rooms += [glyph, value]


def _wire(drawing: _Drawing, net: str, a: Point, b: Point) -> None:
    if a != b:
        drawing.wires.append((net, a, b))


# --- fields ---------------------------------------------------------------------------------------


def _fields(placed: _Placed) -> tuple[WField, Box] | None:
    """The field poses and their room for a unit: two centred lines above an anchor's body (to its right
    when one of its pins leaves it upwards), above a level two-pin part, beside a standing one."""
    unit = placed.unit
    if not unit.text:
        return None
    length = unit.text
    left, top, right, bottom = placed.body
    ends = list(placed.points.values())
    if ends:
        top = min(top, min(p.y for p in ends))
        bottom = max(bottom, max(p.y for p in ends))
    # KiCad turns a field with its symbol: 90 degrees on a turned symbol draws the text level
    angle = 90 if placed.place.rotation % 180 else 0
    upwards = any(out == 90 for out in placed.outward.values())
    half = _up(length * CHAR // 2 + GRID // 2)
    two_pin = len(unit.pins) == 2 and unit.single
    standing = two_pin and len({p.x for p in ends}) == 1
    if standing:  # standing part: beside it, on its right
        cx = _up(right + GRID + half)
        cy = _down((placed.body[1] + placed.body[3]) // 2)
    elif upwards and not two_pin:
        cx = _up(right + STEP + half)
        cy = placed.place.y
    else:
        cx = _down((left + right) // 2)
        cy = _down(min(top, placed.body[1]) - LINE - 2 * GRID)
    room = text_room(Point(cx, cy), length, 2)
    return WField(Point(cx, cy - LINE // 2), Point(cx, cy + LINE // 2), angle), room


def _add_fields(drawing: _Drawing, placed: _Placed) -> None:
    found = _fields(placed)
    if found is not None:
        drawing.fields[placed.unit.key] = found[0]
        drawing.rooms.append(found[1])


# --- clusters ---------------------------------------------------------------------------------------


@dataclass
class _Attached:
    """A two-pin part attached to a node: its unit, the pin facing the node and the other one."""

    unit: WUnit
    near: WPin
    far: WPin
    kind: str  # "series", "term" (a supply or nothing at the far pin) or "decouple"


@dataclass
class _Node:
    """A point that parts attach to: the anchor's key and pin (or a part's far pin), its net and side."""

    owner: str
    pin: str
    net: str
    terms: list[_Attached] = field(default_factory=lambda: [])
    series: _Attached | None = None


@dataclass
class _Cluster:
    anchor: WUnit | None
    nodes: dict[tuple[str, str], _Node] = field(default_factory=lambda: {})
    decouple: list[_Attached] = field(default_factory=lambda: [])
    bridges: list[_Attached] = field(default_factory=lambda: [])
    loose: WUnit | None = None
    chain: list[tuple[WUnit, WPin, WPin]] = field(default_factory=lambda: [])
    """Two-pin parts that serve no anchor and join each other in a path: (part, upper pin, lower pin)."""
    rank: int = 0
    drawing: _Drawing = field(default_factory=_Drawing)
    box: Box = (0, 0, 0, 0)
    column: int = 0
    order: int = 0
    mirror: str = ""
    beside: tuple[int, int] | None = None
    """For a one-sided anchor: the index of the cluster it stands beside and the side (-1 left, 1 right)."""


def _two_pin(unit: WUnit) -> bool:
    """Whether ``unit`` is a two-pin part: the one unit of its component, two pins on one axis facing each
    other (``schlayout.is_satellite`` without its net conditions)."""
    if unit.key.startswith("#") or not unit.single or len(unit.pins) != 2:
        return False
    first, second = unit.pins
    dx, dy = second.at.x - first.at.x, second.at.y - first.at.y
    if (dx == 0) == (dy == 0):
        return False
    towards = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    lib = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
    return lib[first.angle % 360] == towards and lib[second.angle % 360] == (-towards[0], -towards[1])


def one_sided(unit: WUnit) -> bool:
    """Whether every pin of ``unit`` leaves its body on one side (a connector, a header, a test point)."""
    return len(unit.pins) > 0 and len({pin.angle % 360 for pin in unit.pins}) == 1


def _order(key: str) -> tuple[object, ...]:
    path, _, unit = key.rpartition("#")
    if not (path and unit.isdigit()):
        path, unit = key, "1"
    return (natural_key(path), int(unit))


class _Sheet:
    """The state of one sheet's layout."""

    def __init__(
        self,
        units: Sequence[WUnit],
        nets: Mapping[tuple[str, str], WNet],
        marks: frozenset[tuple[str, str]] | set[tuple[str, str]],
        groups: Sequence[Sequence[str]],
    ) -> None:
        self.units = {u.key: u for u in sorted(units, key=lambda u: _order(u.key))}
        self.nets = nets
        self.marks = marks
        self.groups = groups
        self.by_net: dict[str, list[tuple[str, str]]] = {}
        for unit in self.units.values():
            for pin in unit.pins:
                net = nets.get((unit.key, pin.number))
                if net is not None:
                    self.by_net.setdefault(net.id, []).append((unit.key, pin.number))
        self.info: dict[str, WNet] = {}
        for net in nets.values():
            self.info.setdefault(net.id, net)

    def net(self, key: str, pin: str) -> WNet | None:
        return self.nets.get((key, pin))

    def role(self, key: str, pin: str) -> str:
        net = self.net(key, pin)
        return net.role if net is not None else ""

    # --- attachment -------------------------------------------------------------------------------

    def clusters(self) -> list[_Cluster]:
        anchors = [u for u in self.units.values() if not _two_pin(u)]
        parts = [u for u in self.units.values() if _two_pin(u)]
        clusters = [_Cluster(a) for a in anchors]
        owner: dict[str, _Cluster] = {}
        nodes: dict[str, list[tuple[_Cluster, _Node]]] = {}  # net id → nodes in order
        # a part serves an IC before a connector: the nodes of anchors with pins on several sides first,
        # the anchors with more pins first
        ranked = sorted(range(len(clusters)), key=lambda i: (one_sided(anchors[i]), -len(anchors[i].pins), i))
        for position, index in enumerate(ranked):
            clusters[index].rank = position
        for cluster in (clusters[i] for i in ranked):
            anchor = cluster.anchor
            assert anchor is not None
            owner[anchor.key] = cluster
            for pin in sorted(anchor.pins, key=lambda p: natural_key(p.number)):
                net = self.net(anchor.key, pin.number)
                if net is None or is_supply(net.role):
                    continue
                node = _Node(anchor.key, pin.number, net.id)
                cluster.nodes[(anchor.key, pin.number)] = node
                nodes.setdefault(net.id, []).append((cluster, node))
        left = list(parts)
        progress = True
        while progress and left:
            progress = False
            rest: list[WUnit] = []
            for part in left:
                if self._attach(part, clusters, owner, nodes):
                    progress = True
                else:
                    rest.append(part)
            left = rest
        for chain in self._chains(left):
            clusters.append(_Cluster(None, loose=chain[0][0], chain=chain if len(chain) > 1 else []))
        return clusters

    def _chains(self, parts: Sequence[WUnit]) -> list[list[tuple[WUnit, WPin, WPin]]]:
        """The parts that serve no anchor in paths joined by signal nets, each part with its upper and
        lower pin; a part on a net that three of them share stands alone."""
        on: dict[str, list[WUnit]] = {}
        for part in parts:
            for pin in part.pins:
                net = self.net(part.key, pin.number)
                if net is not None and not is_supply(net.role):
                    on.setdefault(net.id, []).append(part)
        crowded = {part.key for found in on.values() if len(found) > 2 for part in found}

        def link(part: WUnit, pin: WPin) -> WUnit | None:
            net = self.net(part.key, pin.number)
            if net is None or is_supply(net.role):
                return None
            others = [o for o in on.get(net.id, ()) if o.key != part.key]
            return others[0] if len(others) == 1 and others[0].key not in crowded else None

        done: set[str] = set()
        found: list[list[tuple[WUnit, WPin, WPin]]] = []

        def end_rank(part: WUnit) -> tuple[int, tuple[object, ...]]:
            free = [pin for pin in part.pins if link(part, pin) is None]
            roles = [self.role(part.key, pin.number) for pin in free]
            return (
                0 if "rail" in roles else 1 if not roles or "" in roles or "signal" in roles else 2,
                _order(part.key),
            )

        for part in sorted(parts, key=lambda p: _order(p.key)):
            if part.key in done:
                continue
            if part.key in crowded:
                done.add(part.key)
                found.append([(part, part.pins[0], part.pins[1])])
                continue
            # walk to the ends of this path and start from the better end
            group = [part]
            seen = {part.key}
            frontier = [part]
            while frontier:
                current = frontier.pop()
                for pin in current.pins:
                    other = link(current, pin)
                    if other is not None and other.key not in seen:
                        seen.add(other.key)
                        group.append(other)
                        frontier.append(other)
            ends = [g for g in group if sum(1 for pin in g.pins if link(g, pin) is not None) <= 1]
            if not ends:  # a ring: no path
                for g in group:
                    done.add(g.key)
                    found.append([(g, g.pins[0], g.pins[1])])
                continue
            start = min(ends, key=end_rank)
            chain: list[tuple[WUnit, WPin, WPin]] = []
            previous: WUnit | None = None
            current: WUnit | None = start
            while current is not None and current.key not in done:
                done.add(current.key)
                a, b = current.pins
                if previous is None:
                    upper, lower = (
                        (a, b) if link(current, b) is not None or link(current, a) is None else (b, a)
                    )
                    if link(current, a) is None and link(current, b) is None:
                        rb = self.role(current.key, b.number)
                        upper, lower = (b, a) if rb == "rail" else (a, b)
                else:
                    upper, lower = (a, b) if link(current, a) is previous else (b, a)
                chain.append((current, upper, lower))
                previous, current = current, link(current, lower)
            found.append(chain)
        return found

    def _attach(
        self,
        part: WUnit,
        clusters: Sequence[_Cluster],
        owner: dict[str, _Cluster],
        nodes: dict[str, list[tuple[_Cluster, _Node]]],
    ) -> bool:
        a, b = part.pins
        na, nb = self.net(part.key, a.number), self.net(part.key, b.number)
        supply_a = na is not None and is_supply(na.role)
        supply_b = nb is not None and is_supply(nb.role)
        if supply_a and supply_b:
            assert na is not None and nb is not None
            if na.id == nb.id:
                return False
            rail = na if na.role != "ground" else nb
            for cluster in clusters:
                anchor = cluster.anchor
                if anchor is None:
                    continue
                if any(
                    (n := self.net(anchor.key, p.number)) is not None and n.id == rail.id for p in anchor.pins
                ):
                    near, far = (a, b) if na.id == rail.id else (b, a)
                    cluster.decouple.append(_Attached(part, near, far, "decouple"))
                    owner[part.key] = cluster
                    return True
            return False
        if na is not None and nb is not None and not supply_a and not supply_b and na.id != nb.id:
            # a part between two signal pins of one anchor (a feedback part): drawn level beside it
            for cluster in sorted(clusters, key=lambda c: c.rank):
                anchor = cluster.anchor
                if anchor is None or part.key in owner:
                    continue
                ids = {n.id for p in anchor.pins if (n := self.net(anchor.key, p.number)) is not None}
                if na.id in ids and nb.id in ids:
                    cluster.bridges.append(_Attached(part, a, b, "bridge"))
                    owner[part.key] = cluster
                    return True
        options: list[tuple[int, int, WPin, WPin, WNet | None, _Cluster, _Node]] = []
        for near, far, net, other in ((a, b, na, nb), (b, a, nb, na)):
            if net is None or is_supply(net.role):
                continue
            series = other is not None and not is_supply(other.role)
            for position, (cluster, node) in enumerate(nodes.get(net.id, ())):
                if series and node.series is not None:
                    continue
                options.append((cluster.rank, position, near, far, other, cluster, node))
                break
        if not options:
            return False
        _, _, near, far, other, cluster, node = min(options, key=lambda o: (o[0], o[1]))
        series = other is not None and not is_supply(other.role)
        attached = _Attached(part, near, far, "series" if series else "term")
        if series:
            node.series = attached
            assert other is not None
            far_node = _Node(part.key, far.number, other.id)
            cluster.nodes[(part.key, far.number)] = far_node
            nodes.setdefault(other.id, []).append((cluster, far_node))
        else:
            node.terms.append(attached)
        owner[part.key] = cluster
        return True


# --- drawing one cluster -----------------------------------------------------------------------------


@dataclass
class _Slot:
    """A part of a column, drawn at a trial place: its drawing, its box relative to its near pin, its
    node's point (the height or abscissa it wants) and its near pin's point."""

    attached: _Attached
    drawing: _Drawing
    box: Box
    want: int
    near: Point
    node_point: Point
    far_node: tuple[str, str] | None


def _draw_part(sheet: _Sheet, attached: _Attached, outward: int) -> tuple[_Drawing, Point, Point]:
    """``attached`` drawn with its near pin at (0, 0), lying along ``outward`` (the direction from its node
    to it): the part, its power symbol and its fields. Returns the drawing and its near and far points."""
    unit = attached.unit
    rotation = _rotation_for(attached.near.angle, (outward + 180) % 360)
    trial = _place(unit, 0, 0, rotation)
    near = trial.points[attached.near.number]
    placed = _moved(trial, -near.x, -near.y)
    drawing = _Drawing()
    drawing.units[unit.key] = placed
    far = placed.points[attached.far.number]
    net = sheet.net(unit.key, attached.far.number)
    if attached.kind == "term" and net is not None and is_supply(net.role):
        natural = _natural(net.role)
        if outward in (90, 270):
            end = _step(far, outward, STUB)
            _wire(drawing, net.id, far, end)
            _power(drawing, net, end, outward if natural == (outward + 180) % 360 else natural)
        else:
            end = _step(far, outward, STUB)
            _wire(drawing, net.id, far, end)
            _power(drawing, net, end, natural)
    _add_fields(drawing, placed)
    return drawing, Point(0, 0), far


def _draw_decoupler(sheet: _Sheet, attached: _Attached) -> _Drawing:
    """A part between two supplies, standing: its rail (or its first supply) above, the other below, each
    on a power symbol pointing away from it."""
    unit = attached.unit
    rotation = _rotation_for(attached.near.angle, 90)  # the rail pin points up
    placed = _place(unit, 0, 0, rotation)
    drawing = _Drawing()
    drawing.units[unit.key] = placed
    for pin, towards in ((attached.near, 90), (attached.far, 270)):
        net = sheet.net(unit.key, pin.number)
        assert net is not None
        point = placed.points[pin.number]
        end = _step(point, towards, STUB)
        _wire(drawing, net.id, point, end)
        _power(drawing, net, end, towards)
    _add_fields(drawing, placed)
    return drawing


def _sides(placed: _Placed) -> dict[int, list[str]]:
    found: dict[int, list[str]] = {0: [], 90: [], 180: [], 270: []}
    for number, out in placed.outward.items():
        found[out].append(number)
    return found


def _draw_anchor_powers(sheet: _Sheet, drawing: _Drawing, placed: _Placed) -> None:
    """The power symbols of the supply pins of an anchor: a stub from each pin, adjacent pins of one side
    and one supply joined, one glyph per run, pointing to the supply's natural side when the pin or its
    neighbours allow it, else outwards."""
    unit = placed.unit
    connected = {p.number for p in unit.pins if (unit.key, p.number) in sheet.nets}
    for side, numbers in _sides(placed).items():
        along = 1 if side in (0, 180) else 0  # 1: pins of this side spread along y
        ordered = sorted(numbers, key=lambda n: (placed.points[n].y, placed.points[n].x))
        if not along:
            ordered = sorted(numbers, key=lambda n: (placed.points[n].x, placed.points[n].y))
        runs: list[list[str]] = []
        for number in ordered:
            net = sheet.net(unit.key, number)
            if net is None or not is_supply(net.role):
                if number in connected:
                    runs.append([])
                continue
            if runs and runs[-1] and sheet.net(unit.key, runs[-1][-1]) == net:
                runs[-1].append(number)
            else:
                runs.append([number])
        for run in (r for r in runs if r):
            net = sheet.net(unit.key, run[0])
            assert net is not None
            natural = _natural(net.role)
            ends: list[Point] = []
            for number in run:
                point = placed.points[number]
                end = _step(point, side, STUB)
                _wire(drawing, net.id, point, end)
                ends.append(end)
            if len(ends) > 1:
                _wire(drawing, net.id, ends[0], ends[-1])
            if side == natural:
                _power(drawing, net, ends[0], side)
                continue
            if side == (natural + 180) % 360:
                _power(drawing, net, _step(ends[0], side, 0), side)
                continue
            # a side pin: the glyph hangs to the natural side when the pins beyond the run are free
            extreme = ends[-1] if natural == 270 else ends[0]
            index = ordered.index(run[-1] if natural == 270 else run[0])
            beyond = ordered[index + 1 :] if natural == 270 else ordered[:index]
            gap = abs(placed.points[beyond[0]].y - extreme.y) if beyond else 10 * STEP
            busy = any(n in connected for n in (beyond[:2] if natural == 270 else beyond[-2:]))
            if not busy or gap > 3 * STEP:
                _power(drawing, net, extreme, natural)
            else:
                tip = _step(extreme, side, STEP)
                _wire(drawing, net.id, extreme, tip)
                _power(drawing, net, tip, side)


def _pack(slots: list[_Slot], axis: int, blocked: Sequence[tuple[int, int]]) -> None:
    """Place ``slots`` along ``axis`` (1: y, 0: x) in their order, each as close to the place it wants as
    the slot before it and the ``blocked`` intervals allow, by moving its near point."""
    cursor: int | None = None
    for slot in slots:
        low, high = (slot.box[1], slot.box[3]) if axis else (slot.box[0], slot.box[2])
        at = slot.want
        if cursor is not None:
            at = max(at, cursor - low)
        at = _up(at)
        moved = True
        while moved:
            moved = False
            for lo, hi in blocked:
                if at + low < hi and lo < at + high:
                    at = _up(hi - low)
                    moved = True
        slot.near = Point(slot.near.x, at) if axis else Point(at, slot.near.y)
        cursor = at + high + SLOT_GAP


def _draw_cluster(sheet: _Sheet, cluster: _Cluster) -> None:
    """The drawing of ``cluster`` in the frame of its anchor's origin (or of its loose part)."""
    drawing = cluster.drawing
    if cluster.anchor is None and cluster.chain:
        _draw_chain(sheet, cluster.chain, drawing)
        return
    if cluster.anchor is None:
        assert cluster.loose is not None
        _draw_loose(sheet, cluster.loose, drawing)
        return
    anchor = _place(cluster.anchor, 0, 0, 0, cluster.mirror)
    drawing.units[anchor.unit.key] = anchor
    _draw_anchor_powers(sheet, drawing, anchor)
    _anchor_fields(sheet, drawing, anchor)
    sides = _sides(anchor)
    for side in (180, 0, 90, 270):
        _draw_side(sheet, cluster, anchor, side, sides[side])
    if cluster.bridges:
        _draw_bridges(sheet, cluster, anchor)
    if cluster.decouple:
        _draw_row(sheet, cluster, anchor)


def _draw_bridges(sheet: _Sheet, cluster: _Cluster, anchor: _Placed) -> None:
    """The parts between two signal pins of the anchor, level and centred above everything drawn over the
    anchor's span, each with its near pin on the side of the anchor pin of its net."""
    drawing = cluster.drawing
    centre = (anchor.body[0] + anchor.body[2]) // 2

    def pin_x(net: WNet | None) -> int:
        xs = [
            point.x
            for number, point in anchor.points.items()
            if net is not None
            and (found := sheet.net(anchor.unit.key, number)) is not None
            and found.id == net.id
        ]
        return min(xs, default=centre)

    for attached in sorted(cluster.bridges, key=lambda a: _order(a.unit.key)):
        near_x = pin_x(sheet.net(attached.unit.key, attached.near.number))
        far_x = pin_x(sheet.net(attached.unit.key, attached.far.number))
        part, _, _ = _draw_part(sheet, attached, 0 if near_x <= far_x else 180)
        box = _union(part.boxes())
        dx = _down(centre - (box[0] + box[2]) // 2, STEP)
        span = (box[0] + dx - STEP, box[2] + dx + STEP)
        over = [b[1] for b in drawing.boxes() if b[0] < span[1] and span[0] < b[2]]
        top = min(over, default=anchor.body[1])
        dy = _down(top - 2 * STEP - box[3], STEP)
        drawing.merge(part.moved(dx, dy))


def _anchor_fields(sheet: _Sheet, drawing: _Drawing, anchor: _Placed) -> None:
    """The fields of an anchor at the first free place: above its body (centred, then right or left of the
    pins that leave it upwards), at the right of its top, below it; free means clear of its body, pin
    lines, power symbols and of the first stretch of the wire of each connected pin."""
    unit = anchor.unit
    if not unit.text:
        return
    busy = drawing.boxes()
    for number, point in anchor.points.items():
        if (unit.key, number) in sheet.nets:
            busy.append(_box_of([point, _step(point, anchor.outward[number], 2 * STEP)]))
    left, top, right, bottom = anchor.body
    half = _up(unit.text * CHAR // 2 + GRID // 2)
    ups = [p.x for n, p in anchor.points.items() if anchor.outward[n] == 90]
    downs = [p.x for n, p in anchor.points.items() if anchor.outward[n] == 270]
    above = min([top, *(p.y for n, p in anchor.points.items() if anchor.outward[n] == 90)])
    centre = _down((left + right) // 2)
    high = _down(top - LINE - 2 * GRID)
    candidates = [Point(centre, high)]
    if ups:
        candidates += [
            Point(_up(max(ups) + 2 * GRID + half), high),
            Point(_down(min(ups) - 2 * GRID - half), high),
        ]
    candidates.append(Point(_up(right + STEP + half), _up(top + LINE)))
    candidates.append(Point(_down(left - STEP - half), _up(top + LINE)))
    low = _up(bottom + LINE + 2 * GRID)
    candidates.append(Point(centre, low))
    if downs:
        candidates.append(Point(_up(max(downs) + 2 * GRID + half), low))
    candidates.append(Point(centre, _down(above - LINE - 2 * GRID)))
    for centre_at in candidates:
        room = text_room(centre_at, unit.text, 2)
        if not any(_overlap(room, other) for other in busy):
            break
    else:
        centre_at = candidates[-1]
        room = text_room(centre_at, unit.text, 2)
    angle = 90 if anchor.place.rotation % 180 else 0
    drawing.fields[unit.key] = WField(
        Point(centre_at.x, centre_at.y - LINE // 2), Point(centre_at.x, centre_at.y + LINE // 2), angle
    )
    drawing.rooms.append(room)


def _draw_chain(sheet: _Sheet, chain: Sequence[tuple[WUnit, WPin, WPin]], drawing: _Drawing) -> None:
    """Parts that join each other in a path, standing one under the other: the wire between two of them
    is routed straight down; a supply at either end of the path is a power symbol."""
    cursor = 0
    for index, (unit, upper, lower) in enumerate(chain):
        trial = _place(unit, 0, 0, _rotation_for(upper.angle, 90))
        top = trial.points[upper.number]
        placed = _moved(trial, -top.x, cursor - top.y)
        drawing.units[unit.key] = placed
        for pin, end in ((upper, index == 0), (lower, index == len(chain) - 1)):
            net = sheet.net(unit.key, pin.number)
            if not end or net is None or not is_supply(net.role):
                continue
            point = placed.points[pin.number]
            out = placed.outward[pin.number]
            stub = _step(point, out, STUB)
            _wire(drawing, net.id, point, stub)
            natural = _natural(net.role)
            _power(drawing, net, stub, natural if natural != (out + 180) % 360 else out)
        _add_fields(drawing, placed)
        cursor = placed.points[lower.number].y + 2 * STEP


def _draw_loose(sheet: _Sheet, unit: WUnit, drawing: _Drawing) -> None:
    """A two-pin part that serves no anchor: standing with its supply to its side, else level."""
    a, b = unit.pins
    ra, rb = sheet.role(unit.key, a.number), sheet.role(unit.key, b.number)
    if is_supply(ra) or is_supply(rb):
        first, second = (
            (a, b)
            if (is_supply(rb) and _natural(rb) == 270) or (is_supply(ra) and _natural(ra) == 90)
            else (b, a)
        )
        placed = _place(unit, 0, 0, _rotation_for(first.angle, 90))
    else:
        placed = _place(unit, 0, 0, 0)
        first, second = a, b
    drawing.units[unit.key] = placed
    for pin in (first, second):
        net = sheet.net(unit.key, pin.number)
        if net is None or not is_supply(net.role):
            continue
        point = placed.points[pin.number]
        out = placed.outward[pin.number]
        end = _step(point, out, STUB)
        _wire(drawing, net.id, point, end)
        natural = _natural(net.role)
        _power(drawing, net, end, natural if natural != (out + 180) % 360 else out)
    _add_fields(drawing, placed)


def _draw_side(sheet: _Sheet, cluster: _Cluster, anchor: _Placed, side: int, numbers: list[str]) -> None:
    """The columns (or rows) of parts beside one side of the anchor."""
    drawing = cluster.drawing
    axis = 1 if side in (0, 180) else 0  # the axis along which the side's pins spread
    sign = _DIRS[side][0] if axis else _DIRS[side][1]
    current = [
        (anchor.unit.key, n)
        for n in sorted(numbers, key=lambda n: (anchor.points[n].y, anchor.points[n].x))
        if (anchor.unit.key, n) in cluster.nodes
    ]
    points = {(anchor.unit.key, n): anchor.points[n] for n in numbers}
    # the corridors of connected pins that pass every column: they stay free
    passing: list[int] = []
    for key in current:
        node = cluster.nodes[key]
        if not node.terms and node.series is None:
            point = points[key]
            passing.append(point.y if axis else point.x)
    front = _front(drawing, side)
    while current:
        slots: list[_Slot] = []
        nxt: list[tuple[str, str]] = []
        for key in current:
            node = cluster.nodes[key]
            point = points[key]
            members: list[_Attached] = []
            if node.series is not None:
                members.append(node.series)
            members += node.terms
            for attached in members:
                part, near, far = _draw_part(sheet, attached, side)
                box = _union(part.boxes())
                far_node = (attached.unit.key, attached.far.number) if attached is node.series else None
                slots.append(_Slot(attached, part, box, point.y if axis else point.x, near, point, far_node))
        if not slots:
            break
        column = front + sign * CHANNEL
        # the near points of a column line up; each slot's extent towards the anchor decides the line
        for slot in slots:
            reach = slot.box[2] if sign < 0 and axis else slot.box[0] if axis else 0
            del reach
        if axis:
            line = column - (max(s.box[2] for s in slots) if sign < 0 else min(s.box[0] for s in slots))
        else:
            line = column - (max(s.box[3] for s in slots) if sign < 0 else min(s.box[1] for s in slots))
        line = _up(line, STEP) if sign > 0 else _down(line, STEP)
        for slot in slots:
            slot.near = Point(line, 0) if axis else Point(0, line)
        blocked = [(c - 2 * GRID, c + 2 * GRID) for c in passing]
        _pack(slots, axis, blocked)
        outer = front
        for slot in slots:
            dx, dy = slot.near.x, slot.near.y
            moved = slot.drawing.moved(dx, dy)
            drawing.merge(moved)
            box = _shift(slot.box, dx, dy)
            outer = (
                (min(outer, box[0]) if sign < 0 else max(outer, box[2]))
                if axis
                else (min(outer, box[1]) if sign < 0 else max(outer, box[3]))
            )
            if slot.far_node is not None:
                placed = drawing.units[slot.far_node[0]]
                points[slot.far_node] = placed.points[slot.far_node[1]]
                node = cluster.nodes[slot.far_node]
                if node.terms or node.series is not None:
                    nxt.append(slot.far_node)
                else:
                    far = points[slot.far_node]
                    passing.append(far.y if axis else far.x)
        front = outer
        current = sorted(
            nxt, key=lambda k: (points[k].y, points[k].x) if axis else (points[k].x, points[k].y)
        )


def _front(drawing: _Drawing, side: int) -> int:
    """How far the drawing reaches so far towards ``side``."""
    boxes = drawing.boxes()
    box = _union(boxes)
    return {180: box[0], 0: box[2], 90: box[1], 270: box[3]}[side]


def _draw_row(sheet: _Sheet, cluster: _Cluster, anchor: _Placed) -> None:
    """The decoupling row under the anchor, packed from the side of its first rail pin."""
    drawing = cluster.drawing
    parts = [
        _draw_decoupler(sheet, attached)
        for attached in sorted(cluster.decouple, key=lambda a: _order(a.unit.key))
    ]
    boxes = [_union(p.boxes()) for p in parts]
    rail_x = min(anchor.points.values(), key=lambda p: p.x).x
    for attached in cluster.decouple:
        for number, point in anchor.points.items():
            net = sheet.net(anchor.unit.key, number)
            near_net = sheet.net(attached.unit.key, attached.near.number)
            if net is not None and near_net is not None and net.id == near_net.id:
                rail_x = point.x
                break
        break
    centre = (anchor.body[0] + anchor.body[2]) // 2
    width = sum(b[2] - b[0] for b in boxes) + SLOT_GAP * (len(boxes) - 1)
    x = _down(anchor.body[0] if rail_x <= centre else anchor.body[2] - width, STEP)
    span = (x - STEP, x + width + STEP)
    below = [b[3] for b in drawing.boxes() if b[0] < span[1] and span[0] < b[2] and b[3] >= anchor.body[1]]
    top = _up(max(below, default=anchor.body[3]) + 2 * STEP, STEP)
    for part, box in zip(parts, boxes, strict=True):
        dx = _up(x - box[0], STEP)
        dy = _up(top - box[1], STEP)
        drawing.merge(part.moved(dx, dy))
        x = dx + box[2] + SLOT_GAP


# --- placement of clusters ---------------------------------------------------------------------------


def _flow(sheet: _Sheet, clusters: list[_Cluster]) -> None:
    """The column of each cluster: the longest path of driven nets into it (design D5)."""
    member: dict[str, int] = {}
    for index, cluster in enumerate(clusters):
        for key in cluster.drawing.units:
            member[key] = index
    edges: dict[int, set[int]] = {i: set() for i in range(len(clusters))}
    neighbours: dict[int, set[int]] = {i: set() for i in range(len(clusters))}
    group_of: dict[int, int] = {}
    for rank, paths in enumerate(sheet.groups):
        wanted = set(paths)
        for index, cluster in enumerate(clusters):
            keys = [
                k.rpartition("#")[0] if "#" in k and k.rpartition("#")[2].isdigit() else k
                for k in cluster.drawing.units
            ]
            if index not in group_of and any(k in wanted for k in keys):
                group_of[index] = rank
    for net_id, pins in sheet.by_net.items():
        info = sheet.info[net_id]
        if info.role == "ground":
            continue
        drivers: set[int] = set()
        sinks: set[int] = set()
        touched: set[int] = set()
        for key, number in pins:
            index = member.get(key)
            if index is None:
                continue
            touched.add(index)
            pin = next(p for p in sheet.units[key].pins if p.number == number)
            if pin.etype in DRIVERS:
                drivers.add(index)
            elif pin.etype in SINKS:
                sinks.add(index)
        if not is_supply(info.role) and not drivers and sinks:
            # a net with inputs and no driver on the sheet: its passive-only clusters (connectors) feed it
            drivers = {i for i in touched if i not in sinks and clusters[i].anchor is not None}
        for a in drivers:
            for b in sinks:
                if a != b:
                    edges[a].add(b)
        if not is_supply(info.role):
            for a in touched:
                neighbours[a] |= touched - {a}
    column: dict[int, int] = {}

    def depth(index: int, trail: frozenset[int]) -> int:
        if index in column:
            return column[index]
        best = 0
        for source in sorted(i for i, ends in edges.items() if index in ends):
            if source in trail:
                continue
            best = max(best, depth(source, trail | {index}) + 1)
        column[index] = best
        return best

    for index in range(len(clusters)):
        depth(index, frozenset())
    for index in range(len(clusters)):
        has_edge = edges[index] or any(index in e for e in edges.values())
        if not has_edge:
            linked = sorted(neighbours[index])
            known = [column[i] for i in linked if edges[i] or any(i in e for e in edges.values())]
            column[index] = min(known) if known else 0
    for index, cluster in enumerate(clusters):
        if cluster.beside is not None and not edges[index] and not any(index in e for e in edges.values()):
            neighbour, side = cluster.beside
            column[index] = column[neighbour] + side
        elif cluster.beside is not None:
            neighbour, side = cluster.beside
            if side < 0:
                column[index] = min(column[index], column[neighbour] - 1)
            else:
                column[index] = max(column[index], column[neighbour] + 1)
    least = min(column.values(), default=0)
    for index in column:
        column[index] -= least
    if group_of:
        base = max(group_of.values()) + 1
        for index in range(len(clusters)):
            column[index] = group_of[index] if index in group_of else base + column[index]
    for index, cluster in enumerate(clusters):
        cluster.column = column[index]


def _arrange(
    sheet: _Sheet, clusters: list[_Cluster], refs: Sequence[tuple[str, Box]]
) -> dict[int, tuple[int, int]]:
    """The offset of each cluster on the drawing (before the page margin), by columns."""
    by_column: dict[int, list[int]] = {}
    for index, cluster in enumerate(clusters):
        by_column.setdefault(cluster.column, []).append(index)
    # one barycentre pass: a cluster follows the mean row of its neighbours in the column before
    member: dict[str, int] = {}
    for index, cluster in enumerate(clusters):
        for key in cluster.drawing.units:
            member[key] = index
    linked: dict[int, set[int]] = {i: set() for i in range(len(clusters))}
    for net_id, pins in sheet.by_net.items():
        if is_supply(sheet.info[net_id].role):
            continue
        touched = {member[k] for k, _ in pins if k in member}
        for a in touched:
            linked[a] |= touched - {a}
    rows: dict[int, int] = {}
    for col in sorted(by_column):
        indices = by_column[col]

        def centre(index: int, col: int = col) -> tuple[int, int]:
            before = [rows[i] for i in linked[index] if clusters[i].column < col and i in rows]
            return ((sum(before) * 2 + len(before) - 1) // (2 * len(before)) if before else 1 << 30, index)

        ordered = sorted(indices, key=centre)
        for row, index in enumerate(ordered):
            rows[index] = row
        by_column[col] = ordered
    # a column taller than the budget wraps into further columns beside it
    wrapped: dict[int, list[int]] = {}
    for col in sorted(by_column):
        budget = max(COLUMN_HEIGHT, max(clusters[i].box[3] - clusters[i].box[1] for i in by_column[col]))
        height = 0
        current: list[int] = []
        for index in by_column[col]:
            tall = clusters[index].box[3] - clusters[index].box[1]
            if current and height + tall > budget:
                wrapped[len(wrapped)] = current
                current, height = [], 0
            current.append(index)
            height += tall + CLUSTER_GAP
        wrapped[len(wrapped)] = current
    by_column = wrapped
    for col, indices in by_column.items():
        for index in indices:
            clusters[index].column = col
    offsets: dict[int, tuple[int, int]] = {}
    x = 0
    columns = sorted(by_column)
    for position, col in enumerate(columns):
        indices = by_column[col]
        width = max(clusters[i].box[2] - clusters[i].box[0] for i in indices)
        y = 0
        for index in indices:
            box = clusters[index].box
            offsets[index] = (_up(x - box[0], STEP), _up(y - box[1], STEP))
            y = offsets[index][1] + box[3] + CLUSTER_GAP
        crossing = 0
        if position + 1 < len(columns):
            here = set(indices)
            for pins in sheet.by_net.values():
                touched = {member[k] for k, _ in pins if k in member}
                if touched & here and touched - here:
                    crossing += 1
        x += width + COLUMN_GAP + GRID * 2 * min(crossing, 16)
    # a few passes: each cluster moves to the median height at which its signal pins meet the pins of their
    # nets in the other columns, the clusters of a column packed in that order
    heights: dict[int, dict[str, list[int]]] = {}
    for index, cluster in enumerate(clusters):
        found: dict[str, list[int]] = {}
        for key, placed in cluster.drawing.units.items():
            for number, point in placed.points.items():
                net = sheet.net(key, number)
                if net is not None and not is_supply(net.role):
                    found.setdefault(net.id, []).append(point.y)
        heights[index] = found
    for _ in range(3):
        for col in columns:
            wanted: dict[int, int] = {}
            for index in by_column[col]:
                deltas: list[int] = []
                for net_id, ys in heights[index].items():
                    for other in linked[index]:
                        theirs = heights[other].get(net_id)
                        if clusters[other].column == col or not theirs:
                            continue
                        deltas += [offsets[other][1] + ty - y for ty in theirs for y in ys]
                deltas.sort()
                wanted[index] = deltas[len(deltas) // 2] if deltas else offsets[index][1]
            cursor: int | None = None
            for index in sorted(by_column[col], key=lambda i: (wanted[i], i)):
                box = clusters[index].box
                oy = wanted[index] if cursor is None else max(wanted[index], cursor - box[1])
                oy = _up(oy, GRID)
                offsets[index] = (offsets[index][0], oy)
                cursor = oy + box[3] + CLUSTER_GAP
    return offsets


# --- routing ---------------------------------------------------------------------------------------


Cell = tuple[int, int]


class _Grid:
    """The routing grid of a sheet: cells of ``GRID``, the cells nothing may enter, the pin points, and
    the wires drawn so far by net and direction."""

    def __init__(self, bounds: Box) -> None:
        self.x0, self.y0 = bounds[0] // GRID, bounds[1] // GRID
        self.x1, self.y1 = bounds[2] // GRID, bounds[3] // GRID
        self.blocked: set[Cell] = set()
        self.pins: dict[Cell, str] = {}
        self.edges: dict[tuple[Cell, Cell], str] = {}
        self.dirs: dict[Cell, dict[str, set[int]]] = {}

    @staticmethod
    def cell(point: Point) -> Cell:
        return (point.x // GRID, point.y // GRID)

    @staticmethod
    def point(cell: Cell) -> Point:
        return Point(cell[0] * GRID, cell[1] * GRID)

    def block(self, box: Box) -> None:
        for x in range(box[0] // GRID, -(-box[2] // GRID) + 1):
            for y in range(box[1] // GRID, -(-box[3] // GRID) + 1):
                self.blocked.add((x, y))

    def block_inside(self, box: Box) -> None:
        """Block the cells strictly inside ``box`` and on its edges, except its corner-free outline? No:
        every cell of the box, edges included."""
        self.block(box)

    def add_wire(self, net: str, a: Point, b: Point) -> None:
        ca, cb = self.cell(a), self.cell(b)
        dx = (cb[0] > ca[0]) - (cb[0] < ca[0])
        dy = (cb[1] > ca[1]) - (cb[1] < ca[1])
        cur = ca
        while cur != cb:
            nxt = (cur[0] + dx, cur[1] + dy)
            self.add_edge(net, cur, nxt)
            cur = nxt

    def add_edge(self, net: str, a: Cell, b: Cell) -> None:
        key = (a, b) if a <= b else (b, a)
        self.edges[key] = net
        angle = _ANGLE_OF[(b[0] - a[0], b[1] - a[1])]
        self.dirs.setdefault(a, {}).setdefault(net, set()).add(angle)
        self.dirs.setdefault(b, {}).setdefault(net, set()).add((angle + 180) % 360)

    def edge(self, a: Cell, b: Cell) -> str | None:
        return self.edges.get((a, b) if a <= b else (b, a))

    def inside(self, cell: Cell) -> bool:
        return self.x0 <= cell[0] <= self.x1 and self.y0 <= cell[1] <= self.y1


@dataclass(frozen=True)
class _Terminal:
    cell: Cell
    out: int
    key: tuple[str, str]


def _search(
    grid: _Grid, net: str, start: _Terminal, tree: set[Cell], tree_pins: Mapping[Cell, int], window: Box
) -> list[Cell] | None:
    """The cheapest path from ``start`` (leaving along its outward direction) to a point of ``tree``."""
    tx0 = min(c[0] for c in tree)
    tx1 = max(c[0] for c in tree)
    ty0 = min(c[1] for c in tree)
    ty1 = max(c[1] for c in tree)

    def h(cell: Cell) -> int:
        dx = tx0 - cell[0] if cell[0] < tx0 else cell[0] - tx1 if cell[0] > tx1 else 0
        dy = ty0 - cell[1] if cell[1] < ty0 else cell[1] - ty1 if cell[1] > ty1 else 0
        return dx + dy

    first = (start.cell[0] + _DIRS[start.out][0], start.cell[1] + _DIRS[start.out][1])
    if not _enterable(grid, net, start.cell, first, start.out):
        return None
    begin = (first, start.out)
    cost: dict[tuple[Cell, int], int] = {begin: 1}
    back: dict[tuple[Cell, int], tuple[Cell, int] | None] = {begin: None}
    heap: list[tuple[int, int, int, int, int]] = [(1 + h(first), 1, first[0], first[1], start.out)]
    expanded = 0
    while heap:
        _, spent, cx, cy, angle = heapq.heappop(heap)
        state = ((cx, cy), angle)
        if cost.get(state, 1 << 60) < spent:
            continue
        cell = (cx, cy)
        expanded += 1
        if expanded > BUDGET:
            return None
        if cell in tree and _joinable(grid, net, cell, angle, tree_pins):
            path = [cell]
            cur: tuple[Cell, int] | None = state
            while cur is not None:
                prev = back[cur]
                if prev is not None:
                    path.append(prev[0])
                cur = prev
            path.append(start.cell)
            path.reverse()
            return path
        if cell in tree:
            continue
        crossing = _other_wire(grid, net, cell)
        for turn in (angle, (angle + 90) % 360, (angle + 270) % 360):
            if crossing and turn != angle:
                continue
            nxt = (cx + _DIRS[turn][0], cy + _DIRS[turn][1])
            if not (window[0] <= nxt[0] <= window[2] and window[1] <= nxt[1] <= window[3]):
                continue
            if not _enterable(grid, net, cell, nxt, turn):
                continue
            step = 1 + (BEND if turn != angle else 0) + (CROSS if _other_wire(grid, net, nxt) else 0)
            new = (nxt, turn)
            total = spent + step
            if total < cost.get(new, 1 << 60):
                cost[new] = total
                back[new] = state
                heapq.heappush(heap, (total + h(nxt), total, nxt[0], nxt[1], turn))
    return None


def _other_wire(grid: _Grid, net: str, cell: Cell) -> bool:
    return any(n != net for n in grid.dirs.get(cell, {}))


def _enterable(grid: _Grid, net: str, a: Cell, b: Cell, angle: int) -> bool:
    """Whether a wire of ``net`` may run from ``a`` into ``b`` along ``angle``."""
    if not grid.inside(b) or grid.edge(a, b) is not None:
        return False
    owner = grid.pins.get(b)
    if owner is not None:
        return owner == net  # a pin point only as the end of its own net (checked by the caller)
    if b in grid.blocked:
        return False
    found = grid.dirs.get(b, {})
    for other, dirs in found.items():
        if other == net:
            continue
        # another net may be crossed only where it runs straight across this direction
        if dirs not in ({90, 270}, {0, 180}) or angle in dirs or (angle + 180) % 360 in dirs:
            return False
        if len(found) > 1:
            return False
    return True


def _joinable(grid: _Grid, net: str, cell: Cell, angle: int, tree_pins: Mapping[Cell, int]) -> bool:
    """Whether a wire arriving along ``angle`` may end at the tree point ``cell``."""
    if any(other != net for other in grid.dirs.get(cell, {})):
        return False
    came = (angle + 180) % 360
    if cell in tree_pins:  # a pin of the tree without a wire: only from its outward side
        if grid.dirs.get(cell, {}).get(net):
            return False
        return came == tree_pins[cell]
    if grid.pins.get(cell) is not None:
        return False
    dirs = grid.dirs.get(cell, {}).get(net, set())
    return came not in dirs and len(dirs) + 1 <= 3


# --- the sheet ---------------------------------------------------------------------------------------


def _follower(unit: WUnit) -> bool:
    """Whether an anchor stands beside the cluster it serves rather than leading one: a one-sided anchor
    (a connector), or an anchor of four pins at most with no input or output pin (a switch, a crystal)."""
    if one_sided(unit):
        return True
    return len(unit.pins) <= 4 and all(pin.etype not in DRIVERS | SINKS for pin in unit.pins)


def _face(sheet: _Sheet, cluster: _Cluster, clusters: Sequence[_Cluster], late: Sequence[_Cluster]) -> None:
    """Where a one-sided anchor stands: beside the drawn cluster it shares the most signal nets with, on the
    side where that cluster's pins of those nets lie, its pins facing it (mirrored when they would face
    away)."""
    anchor = cluster.anchor
    assert anchor is not None
    own = {
        net.id
        for pin in anchor.pins
        if (net := sheet.net(anchor.key, pin.number)) is not None and not is_supply(net.role)
    }
    for attached in [a for node in cluster.nodes.values() for a in (*node.terms, node.series) if a]:
        net = sheet.net(attached.unit.key, attached.far.number)
        if net is not None and not is_supply(net.role):
            own.add(net.id)
    best: tuple[int, int, int] | None = None  # (shared count, -index, sign)
    for index, other in enumerate(clusters):
        if other is cluster or other in late or other.anchor is None:
            continue
        centre = (
            other.drawing.units[other.anchor.key].body[0] + other.drawing.units[other.anchor.key].body[2]
        ) // 2
        shared = 0
        sign = 0
        for key, placed in other.drawing.units.items():
            for number, point in placed.points.items():
                net = sheet.net(key, number)
                if net is not None and net.id in own:
                    shared += 1
                    sign += 1 if point.x > centre else -1 if point.x < centre else 0
        if shared and (best is None or (shared, -index) > best[:2]):
            best = (shared, -index, 1 if sign >= 0 else -1)
    if best is None:
        # nothing to stand beside: a connector faces right, where the circuit it feeds is drawn
        if one_sided(anchor) and label_angle(anchor.pins[0].angle, 0, "") == 180:
            cluster.mirror = "y"
        return
    side = best[2]
    cluster.beside = (-best[1], side)
    wanted = 180 if side > 0 else 0
    votes = 0
    for pin in anchor.pins:
        net = sheet.net(anchor.key, pin.number)
        facing = label_angle(pin.angle, 0, "")
        if net is not None and net.id in own and facing in (0, 180):
            votes += 1 if facing == wanted else -1
    if votes < 0:
        cluster.mirror = "y"


def layout_sheet(
    units: Sequence[WUnit],
    nets: Mapping[tuple[str, str], WNet],
    *,
    marks: frozenset[tuple[str, str]] | set[tuple[str, str]] = frozenset(),
    refs: Sequence[RefBox] = (),
    flags: Sequence[WNet] = (),
    groups: Sequence[Sequence[str]] = (),
    hold: Mapping[str, str] | None = None,
) -> WiredLayout:
    """The wired drawing of one sheet.

    ``units`` are the units of the sheet; ``nets`` maps (unit key, pin number) to the net of that pin on
    this sheet; ``marks`` are the pins with a no-connect flag; ``refs`` the sheet references (block sheet
    pins carry labels, as in the readable layout); ``flags`` the supply nets that need a power flag on this
    sheet; ``groups`` the component paths of each block schematic group, in order; ``hold`` maps a net id
    to the id of the cluster subset it must keep (unused).
    """
    del hold
    sheet = _Sheet(units, nets, marks, groups)
    clusters = sheet.clusters()
    late = sorted(
        (c for c in clusters if c.anchor is not None and _follower(c.anchor)),
        key=lambda c: (one_sided(c.anchor) if c.anchor else True, c.rank),
    )
    for cluster in clusters:
        if cluster not in late:
            _draw_cluster(sheet, cluster)
    for position, cluster in enumerate(late):
        _face(sheet, cluster, clusters, late[position:])
        _draw_cluster(sheet, cluster)
    for cluster in clusters:
        boxes = cluster.drawing.boxes()
        cluster.box = _grow(_union(boxes), STEP) if boxes else (0, 0, 0, 0)
    for index, cluster in enumerate(clusters):
        cluster.order = index
    _flow(sheet, clusters)
    ref_boxes = [
        (ref.path, schlayout.ref_extent(ref)) for ref in sorted(refs, key=lambda r: natural_key(r.path))
    ]
    offsets = _arrange(sheet, clusters, ref_boxes)
    drawing = _Drawing()
    for index, cluster in enumerate(clusters):
        dx, dy = offsets[index]
        drawing.merge(cluster.drawing.moved(dx, dy))
    content = drawing.boxes()
    box = _union(content) if content else (0, 0, STEP, STEP)
    origins: dict[str, SymbolPlacement] = {}
    # sheet references: a column of their own at the right; flags: a row at the bottom
    x = _up(box[2] + COLUMN_GAP, STEP)
    y = box[1]
    for path, (x0, y0, x1, y1) in ref_boxes:
        at = SymbolPlacement(_up(x - x0, STEP), _up(y - y0, STEP))
        origins[schlayout.ref_key(path)] = at
        drawing.rooms.append((at.x + x0, at.y + y0, at.x + x1, at.y + y1))
        y = at.y + y1 + CLUSTER_GAP
    if flags:
        content = drawing.boxes()
        bottom = _union(content)[3] if content else 0
        fx = _down(box[0] + 2 * STEP, STEP)
        fy = _up(bottom + 4 * STEP, STEP)
        flag_half = _up(len(FLAG_VALUE) * CHAR // 2 + GRID // 2)
        here = {found.id for found in nets.values()}
        for net in flags:
            # a power symbol of the net, a wire to the right, and the flag standing on its end
            start = Point(fx, fy)
            if net.id in here:
                _power(drawing, net, start, _natural(net.role))
                value_half = _up(len(net.value) * CHAR // 2 + GRID // 2)
                length = max(2 * STEP, _up(value_half + flag_half + GRID, STEP))
                at = _step(start, 0, length)
                _wire(drawing, net.id, start, at)
            else:
                # No pin of this sheet is on the net: KiCad reports the hidden pin of a power symbol whose
                # net holds only power symbols on the sheet as unconnected, so a global label of the net
                # lies on the flag's pin, as in the readable layout.
                at = _step(start, 0, _up(len(net.text) * CHAR + 2 * STEP, STEP))
                drawing.labels.append(WLabel(net.id, at, 180, 0))
                drawing.rooms.append(schlayout.label_room(at, 180, len(net.text)))
            value_at = Point(at.x, at.y - FLAG_VALUE_RISE)
            drawing.flags.append(WFlag(net.id, at, value_at))
            drawing.rooms += [
                text_room(value_at, len(FLAG_VALUE)),
                (at.x - GRID, at.y - 2 * STEP, at.x + 2 * STEP, at.y - GRID),
            ]
            fx = _up(at.x + flag_half + 3 * STEP + 3 * CHAR, STEP)
    content = drawing.boxes()
    box = _union(content) if content else (0, 0, STEP, STEP)
    width, height = box[2] - box[0], box[3] - box[1]
    chosen = None
    for name, paper_w, paper_h in PAPERS:
        if (
            width + 2 * PAGE_MARGIN + 2 * STEP <= paper_w
            and height + PAGE_MARGIN + TITLE_BAND + 2 * STEP <= paper_h
        ):
            chosen = (name, paper_w, paper_h)
            break
    fits = chosen is not None
    if chosen is None:
        chosen = PAPERS[-1]
    dx = _up(PAGE_MARGIN + STEP - box[0], STEP)
    dy = _up(PAGE_MARGIN + STEP - box[1], STEP)
    drawing = drawing.moved(dx, dy)
    for key, at in list(origins.items()):
        origins[key] = SymbolPlacement(at.x + dx, at.y + dy)
    page = (0, 0, chosen[1], chosen[2] - TITLE_BAND + PAGE_MARGIN)
    wires, junctions, labels, fallbacks = _route(sheet, clusters, offsets, drawing, (dx, dy), page)
    labels = (*labels, *drawing.labels)
    for key, placed in drawing.units.items():
        origins[key] = placed.place
    return WiredLayout(
        chosen[0],
        MappingProxyType(dict(sorted(origins.items()))),
        MappingProxyType(dict(sorted(drawing.fields.items()))),
        wires,
        junctions,
        labels,
        tuple(drawing.powers),
        tuple(drawing.flags),
        fits,
        fallbacks,
        tuple(drawing.rooms),
    )


def _route(
    sheet: _Sheet,
    clusters: Sequence[_Cluster],
    offsets: Mapping[int, tuple[int, int]],
    drawing: _Drawing,
    shift: tuple[int, int],
    page: Box,
) -> tuple[tuple[tuple[Point, Point], ...], tuple[Point, ...], tuple[WLabel, ...], int]:
    """Route every signal net of the sheet, add the labels, and cut the wires at their junctions."""
    grid = _Grid(page)
    member: dict[str, int] = {}
    for index, cluster in enumerate(clusters):
        for key in cluster.drawing.units:
            member[key] = index
    for placed in drawing.units.values():
        grid.block(placed.body)
        for line in placed.lines:
            grid.block(line)
    for room in drawing.rooms:
        grid.block(room)
    for placed in drawing.units.values():
        for number, point in placed.points.items():
            net = sheet.net(placed.unit.key, number)
            cell = grid.cell(point)
            grid.blocked.discard(cell)
            grid.pins[cell] = net.id if net is not None else f"#pin:{placed.unit.key}:{number}"
    for net, a, b in drawing.wires:
        grid.add_wire(net, a, b)
    for power in drawing.powers:
        grid.pins.setdefault(grid.cell(power.at), power.net)
    for flag in drawing.flags:
        grid.pins.setdefault(grid.cell(flag.at), flag.net)
    # terminals: every pin of a signal net (and each wired fixed stub), by net
    terminals: dict[str, list[_Terminal]] = {}
    for key, placed in drawing.units.items():
        for number, point in sorted(placed.points.items(), key=lambda item: natural_key(item[0])):
            net = sheet.net(key, number)
            if net is None or is_supply(net.role):
                continue
            terminals.setdefault(net.id, []).append(
                _Terminal(grid.cell(point), placed.outward[number], (key, number))
            )
    # labels of groups that are surely one pin: reserve their room before routing
    plans: dict[str, list[list[_Terminal]]] = {}
    for net_id in sorted(terminals, key=lambda n: (len(terminals[n]), n)):
        found = terminals[net_id]
        info = sheet.info[net_id]
        by_cluster: dict[int, list[_Terminal]] = {}
        for terminal in found:
            by_cluster.setdefault(member[terminal.key[0]], []).append(terminal)
        if info.bus:
            subsets = list(by_cluster.values())
        else:
            subsets = _reach(by_cluster, clusters, offsets)
        plans[net_id] = subsets
        for subset in subsets:
            if len(subset) == 1:
                terminal = subset[0]
                room = schlayout.label_room(grid.point(terminal.cell), terminal.out, len(info.text))
                inner = _step(grid.point(terminal.cell), terminal.out, GRID)
                grid.block(
                    (
                        min(room[0], inner.x),
                        min(room[1], inner.y),
                        max(room[2], inner.x),
                        max(room[3], inner.y),
                    )
                )
                grid.blocked.discard(terminal.cell)
    groups: dict[str, list[tuple[list[_Terminal], set[Cell]]]] = {}
    fallbacks = 0
    order = sorted(
        plans,
        key=lambda n: (max(len(s) for s in plans[n]), _span(plans[n]), natural_key(n)),
    )
    for net_id in order:
        for subset in plans[net_id]:
            for done, cells in _route_subset(grid, net_id, subset):
                groups.setdefault(net_id, []).append((done, cells))
            if len(groups[net_id]) > 1 and len(subset) > 1:
                pass
        wired = [g for g in groups.get(net_id, []) if g[1]]
        alone = [g for g in groups.get(net_id, []) if not g[1]]
        planned_alone = sum(1 for s in plans[net_id] if len(s) == 1)
        if len(alone) > planned_alone:
            fallbacks += 1
        del wired
    labels: list[WLabel] = []
    taken: list[Box] = []
    for net_id in sorted(groups, key=natural_key):
        info = sheet.info[net_id]
        for index, (members, cells) in enumerate(groups[net_id]):
            label = _label(grid, net_id, info, index, members, cells, taken)
            labels.append(label)
            taken.append(schlayout.label_room(label.at, label.angle, len(info.text)))
    wires, junctions = _segments(grid, drawing)
    return wires, junctions, tuple(labels), fallbacks


def _span(subsets: Sequence[Sequence[_Terminal]]) -> int:
    cells = [t.cell for s in subsets for t in s]
    return (
        max(c[0] for c in cells)
        - min(c[0] for c in cells)
        + max(c[1] for c in cells)
        - min(c[1] for c in cells)
    )


def _reach(
    by_cluster: Mapping[int, list[_Terminal]],
    clusters: Sequence[_Cluster],
    offsets: Mapping[int, tuple[int, int]],
) -> list[list[_Terminal]]:
    """The terminals of a net split into subsets of clusters that lie within ``ROUTE_REACH`` of each other
    (single linkage), in cluster order."""
    indices = sorted(by_cluster)
    boxes = {i: _shift(clusters[i].box, *offsets[i]) for i in indices}
    parent = {i: i for i in indices}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in indices:
        for b in indices:
            if a < b:
                ba, bb = boxes[a], boxes[b]
                gap_x = max(0, max(ba[0], bb[0]) - min(ba[2], bb[2]))
                gap_y = max(0, max(ba[1], bb[1]) - min(ba[3], bb[3]))
                if gap_x + gap_y <= ROUTE_REACH:
                    parent[find(b)] = find(a)
    found: dict[int, list[_Terminal]] = {}
    for i in indices:
        found.setdefault(find(i), []).extend(by_cluster[i])
    return [found[k] for k in sorted(found)]


def _distance(cell: Cell, bounds: tuple[int, int, int, int]) -> int:
    """The Manhattan distance from ``cell`` to the box ``bounds`` of cells."""
    x0, y0, x1, y1 = bounds
    dx = x0 - cell[0] if cell[0] < x0 else cell[0] - x1 if cell[0] > x1 else 0
    dy = y0 - cell[1] if cell[1] < y0 else cell[1] - y1 if cell[1] > y1 else 0
    return dx + dy


def _route_subset(
    grid: _Grid, net: str, subset: Sequence[_Terminal]
) -> list[tuple[list[_Terminal], set[Cell]]]:
    """Join the terminals of ``subset`` into trees: the first terminal starts a tree, each further one (the
    nearest first) is joined to it; a terminal that cannot be joined starts a group of its own."""
    if len(subset) == 1:
        return [([subset[0]], set())]
    pending = list(subset)
    first = pending.pop(0)
    tree_cells: set[Cell] = {first.cell}
    tree_pins: dict[Cell, int] = {first.cell: first.out}
    members = [first]
    wired: set[Cell] = set()
    alone: list[_Terminal] = []
    while pending:
        bounds = (
            min(c[0] for c in tree_cells),
            min(c[1] for c in tree_cells),
            max(c[0] for c in tree_cells),
            max(c[1] for c in tree_cells),
        )
        pending.sort(key=lambda t: (_distance(t.cell, bounds), natural_key(t.key[0]), natural_key(t.key[1])))
        terminal = pending.pop(0)
        xs = [c[0] for c in tree_cells] + [terminal.cell[0]]
        ys = [c[1] for c in tree_cells] + [terminal.cell[1]]
        window = (min(xs) - WINDOW, min(ys) - WINDOW, max(xs) + WINDOW, max(ys) + WINDOW)
        path = _search(grid, net, terminal, tree_cells, tree_pins, window)
        if path is None:
            alone.append(terminal)
            continue
        for a, b in zip(path, path[1:], strict=False):
            grid.add_edge(net, a, b)
        tree_cells |= set(path)
        wired |= set(path)
        tree_pins.pop(path[-1], None)
        tree_pins.pop(path[0], None)
        members.append(terminal)
        for cell in path:
            tree_pins.pop(cell, None)
    found: list[tuple[list[_Terminal], set[Cell]]] = [(members, wired if len(members) > 1 else set())]
    found += [([t], set()) for t in alone]
    return found


def _label(
    grid: _Grid,
    net: str,
    info: WNet,
    group: int,
    members: Sequence[_Terminal],
    cells: set[Cell],
    taken: Sequence[Box],
) -> WLabel:
    """The one label of a drawn group: at its pin for a group of one pin, else on the inside of one of its
    wires, across it, where its room is free (design D7)."""
    chars = len(info.text)
    if not cells:
        terminal = members[0]
        return WLabel(net, grid.point(terminal.cell), terminal.out, group, terminal.key)
    runs = _runs(grid, net, cells)
    runs.sort(key=lambda r: (-(r[1] == 1), -len(r[0]), r[0][0]))  # vertical runs first: level text
    for run, horizontal in runs:
        if len(run) < 3:
            continue
        inner = run[1:-1]
        middle = len(inner) // 2
        order = sorted(range(len(inner)), key=lambda i: (abs(i - middle), i))
        for i in order:
            cell = inner[i]
            dirs = grid.dirs.get(cell, {})
            if set(dirs) != {net} or len(dirs[net]) != 2 or cell in grid.pins:
                continue
            for angle in (90, 270) if horizontal == 0 else (0, 180):
                at = grid.point(cell)
                room = schlayout.label_room(at, angle, chars)
                if _room_free(grid, room, cell) and not any(_overlap(room, t) for t in taken):
                    return WLabel(net, at, angle, group)
    # no free point: the inner point and direction whose room holds the fewest busy cells
    best: tuple[int, Cell, int] | None = None
    for run, horizontal in runs:
        for cell in run[1:-1] or run:
            if set(grid.dirs.get(cell, {})) != {net} or len(grid.dirs[cell][net]) != 2:
                continue
            for angle in (90, 270) if horizontal == 0 else (0, 180):
                room = schlayout.label_room(grid.point(cell), angle, chars)
                score = _room_cost(grid, room, cell) + sum(4 for t in taken if _overlap(room, t))
                if best is None or (score, cell, angle) < best:
                    best = (score, cell, angle)
    if best is None:
        run, horizontal = runs[0] if runs else ([members[0].cell], 0)
        return WLabel(net, grid.point(run[len(run) // 2]), 90 if horizontal == 0 else 0, group)
    return WLabel(net, grid.point(best[1]), best[2], group)


def _room_cost(grid: _Grid, room: Box, anchor: Cell) -> int:
    count = 0
    for x in range(room[0] // GRID, -(-room[2] // GRID) + 1):
        for y in range(room[1] // GRID, -(-room[3] // GRID) + 1):
            cell = (x, y)
            if cell != anchor and (cell in grid.blocked or cell in grid.pins or cell in grid.dirs):
                count += 1
    return count


def _runs(grid: _Grid, net: str, cells: set[Cell]) -> list[tuple[list[Cell], int]]:
    """The straight runs of the wires of ``net`` among ``cells``: (cells in order, 0 horizontal / 1
    vertical)."""
    found: list[tuple[list[Cell], int]] = []
    for horizontal, step in ((0, (1, 0)), (1, (0, 1))):
        seen: set[Cell] = set()
        for cell in sorted(cells):
            if cell in seen:
                continue
            prev = (cell[0] - step[0], cell[1] - step[1])
            if grid.edge(prev, cell) == net:
                continue
            run = [cell]
            cur = cell
            while True:
                nxt = (cur[0] + step[0], cur[1] + step[1])
                if grid.edge(cur, nxt) != net:
                    break
                run.append(nxt)
                cur = nxt
            seen |= set(run)
            if len(run) > 1:
                found.append((run, horizontal))
    return found


def _room_free(grid: _Grid, room: Box, anchor: Cell) -> bool:
    for x in range(room[0] // GRID, -(-room[2] // GRID) + 1):
        for y in range(room[1] // GRID, -(-room[3] // GRID) + 1):
            cell = (x, y)
            if cell == anchor:
                continue
            if not grid.inside(cell) or cell in grid.blocked or cell in grid.pins or cell in grid.dirs:
                return False
    return True


def _segments(grid: _Grid, drawing: _Drawing) -> tuple[tuple[tuple[Point, Point], ...], tuple[Point, ...]]:
    """The wires of the sheet as straight segments cut at every corner, end, pin and junction, and the
    junctions: points where three directions of one net meet, a pin counting as one."""
    del drawing
    stops: set[Cell] = set()
    junctions: list[Point] = []
    for cell, nets_here in grid.dirs.items():
        for net, dirs in nets_here.items():
            degree = len(dirs) + (1 if grid.pins.get(cell) == net else 0)
            if degree >= 3:
                junctions.append(grid.point(cell))
            if degree != 2 or dirs not in ({0, 180}, {90, 270}) or cell in grid.pins:
                stops.add(cell)
    segments: list[tuple[Point, Point]] = []
    by_net: dict[str, list[tuple[Cell, Cell]]] = {}
    for (a, b), net in grid.edges.items():
        by_net.setdefault(net, []).append((a, b))
    for net in sorted(by_net, key=natural_key):
        edges = set(by_net[net])
        used: set[tuple[Cell, Cell]] = set()
        for a, b in sorted(edges):
            if (a, b) in used:
                continue
            step = (b[0] - a[0], b[1] - a[1])
            start = a
            while start not in stops:
                prev = (start[0] - step[0], start[1] - step[1])
                key = (prev, start) if prev <= start else (start, prev)
                if key not in edges:
                    break
                start = prev
            end = start
            while True:
                nxt = (end[0] + step[0], end[1] + step[1])
                key = (end, nxt) if end <= nxt else (nxt, end)
                if key not in edges:
                    break
                used.add(key)
                end = nxt
                if end in stops:
                    break
            segments.append((grid.point(start), grid.point(end)))
    return tuple(sorted(set(segments), key=lambda s: (s[0].x, s[0].y, s[1].x, s[1].y))), tuple(
        sorted(set(junctions), key=lambda p: (p.x, p.y))
    )


__all__ = [
    "BUS_KINDS",
    "ROUTE_REACH",
    "SUPPLY_NAMES",
    "WField",
    "WFlag",
    "WLabel",
    "WNet",
    "WPin",
    "WPower",
    "WUnit",
    "WiredLayout",
    "is_supply",
    "layout_sheet",
    "name_role",
    "net_role",
]
