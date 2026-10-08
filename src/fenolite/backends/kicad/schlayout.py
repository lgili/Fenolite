# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layout of a generated schematic sheet: where each unit of each symbol goes, and where its pins
connect (capability ``kicad-schematic``, "Pin connection points" and "Deterministic sheet layout"; changes
c0061 and c0070).

Every unit takes one cell; cells fill rows from the left, a module starts a new row, the references to
the sheets of sub-modules take rows of their own, and the power flags take the last row. A 2-pin part
that fits beside an IC pin of its net is snapped there and joined to it by one straight wire
(``snap_satellites``); the IC and its satellites then flow as one cell. The paper is
the smallest A size that holds the rows. The pin frame is a fact of ``docs/formats/kicad/schematic.md``
(``H-K-SCH-PINFRAME``); every length constant is a Fenolite choice. Lengths are integer nanometres and no
float is used.
"""

# evidence: see schgen, sch

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.geometry.shelf import shelf_pack

GRID = 1_270_000
"""The connection grid of KiCad's schematic editor (50 mil): pin ends off it draw an ERC warning."""
ORIGIN_STEP = 2_540_000
"""Symbol origins and cell corners are multiples of this, so a pin on ``GRID`` in its library stays on it."""
CHAR_ROOM = 1_524_000
"""Room kept for one character of a label."""
LABEL_ROOM = 5_080_000
"""Room kept for the frame of a global label, on each side of a unit."""
CELL_MARGIN = 5_080_000
"""Free border of a cell, on each side."""
TEXT_ROOM = 7_620_000
"""Room above a unit for its Reference and Value."""
PAGE_MARGIN = 12_700_000
"""Free border of the page, on each side."""
TITLE_BAND = 40_640_000
"""The band at the bottom of the page that is kept free for the title block."""
SNAP_REACH = 5_080_000
"""The length of the wire between an anchor pin and the near pin of the satellite snapped to it."""
REF_HEIGHT = 12_700_000
"""The height of the box of a sheet reference."""
REF_MIN_WIDTH = 25_400_000
"""The least width of the box of a sheet reference."""
REF_TEXT = 2_540_000
"""Room above and below the box of a sheet reference, for its name and its file."""
REF_PREFIX = "#sheet:"
"""The layout key of a sheet reference is this prefix and its module path; no component path starts with
``#``."""
PAPERS: tuple[tuple[str, int, int], ...] = (
    ("A4", 297_000_000, 210_000_000),
    ("A3", 420_000_000, 297_000_000),
    ("A2", 594_000_000, 420_000_000),
    ("A1", 841_000_000, 594_000_000),
    ("A0", 1_189_000_000, 841_000_000),
)
"""The papers a layout may choose, landscape: name, width, height."""
ROTATIONS: tuple[int, ...] = (0, 90, 180, 270)
MIRRORS: tuple[str, ...] = ("", "x", "y")
PROVED_FRAMES: frozenset[tuple[int, str]] = frozenset((r, m) for r in ROTATIONS for m in MIRRORS)
"""The (rotation in degrees, mirror) pairs for which ``pin_point`` is where KiCad 9.0.9 and 10.0.6 connect
a pin (probes ``sch-pin-frame-<angle>-<mirror>``; the order of the rotation and the mirror is read from the
demo sheets of the corpus and checked by ``tests/kicad/schematic/test_pin_frame_oracle.py``, change c0137).
A placements file may ask for no other pair."""
_TURN: Mapping[int, tuple[int, int, int, int]] = MappingProxyType(
    {0: (1, 0, 0, 1), 90: (0, -1, 1, 0), 180: (-1, 0, 0, -1), 270: (0, 1, -1, 0)}
)
"""Counter-clockwise rotation in the library frame (Y up): (x′, y′) = (a·x + b·y, c·x + d·y)."""
_NATURAL = re.compile(r"(\d+)")


@dataclass(frozen=True, slots=True)
class SymbolPlacement:
    """Where a unit's symbol origin lies: nanometres, a rotation in degrees and a mirror axis."""

    x: int
    y: int
    rotation: int = 0
    mirror: str = ""


@dataclass(frozen=True, slots=True)
class UnitPin:
    """A pin of a unit in its library frame: the connection point, the angle the pin is drawn at (it
    points from the connection point to the body) and the length of its label text (0 without one)."""

    number: str
    at: Point
    angle: int = 0
    label: int = 0


@dataclass(frozen=True, slots=True)
class UnitBox:
    """What the layout needs of one unit. ``key`` is the component path, with ``#<unit>`` for a unit above
    1; ``body`` is the box ``(x0, y0, x1, y1)`` of what the unit draws, in its library frame (Y up);
    ``symbol`` names the library symbol in messages."""

    key: str
    pins: tuple[UnitPin, ...]
    body: tuple[int, int, int, int]
    symbol: str = ""
    text: int = 0
    """The length of the longer of its Reference and Value, in characters."""


@dataclass(frozen=True, slots=True)
class RefBox:
    """What the layout needs of one sheet reference: the path of its module, the name written above its
    box and the file text written below it."""

    path: str
    name: str
    file: str = ""


@dataclass(frozen=True, slots=True)
class SheetLayout:
    """The chosen paper, each unit's placement and cell ``(x0, y0, x1, y1)`` on the sheet, and the
    layout's issues."""

    paper: str
    origins: Mapping[str, SymbolPlacement]
    cells: Mapping[str, tuple[int, int, int, int]]
    issues: tuple[Issue, ...] = ()


def turned(x: int, y: int, rotation: int, mirror: str) -> tuple[int, int]:
    """A library vector (Y up) after the rotation and then the mirror of an instance.

    KiCad turns first and mirrors the turned symbol (change c0137, measured on the demo sheets of the
    corpus): ``"x"`` then negates the turned y and ``"y"`` the turned x. For 0 and 180 degrees the order
    does not matter; for 90 and 270 degrees the other order swaps the two mirrors."""
    if rotation not in _TURN:
        raise ValueError(f"symbol rotation {rotation} is not 0, 90, 180 or 270 degrees")
    if mirror not in MIRRORS:
        raise ValueError(f"symbol mirror {mirror!r} is not '', 'x' or 'y'")
    a, b, c, d = _TURN[rotation]
    x, y = a * x + b * y, c * x + d * y
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    return x, y


def pin_point(origin: Point, pin: Point, rotation: int = 0, mirror: str = "") -> Point:
    """The sheet position at which a pin connects, for a symbol instance at ``origin``.

    ``pin`` is the pin's position in the library frame, whose Y axis points up. The rotation by
    ``rotation`` degrees counter-clockwise is applied first, then the mirror (``"x"`` negates the turned y,
    ``"y"`` the turned x), and the sheet turns Y down: ``(x + px′, y − py′)``.
    """
    px, py = turned(pin.x, pin.y, rotation, mirror)
    return Point(origin.x + px, origin.y - py)


def label_angle(pin_angle: int, rotation: int = 0, mirror: str = "") -> int:
    """The angle (0, 90, 180 or 270 degrees) of a label that points away from the body of a pin drawn at
    ``pin_angle`` in its library, on an instance with ``rotation`` and ``mirror``."""
    steps = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
    dx, dy = steps[pin_angle % 360]
    tx, ty = turned(-dx, -dy, rotation, mirror)
    return next(angle for angle, step in steps.items() if step == (tx, ty))


def natural_key(text: str) -> tuple[tuple[int, int | str], ...]:
    """A sort key that orders ``R2`` before ``R10``."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in _NATURAL.split(text) if part)


def unit_key(path: str, unit: int) -> str:
    """The key of one unit of a component: its path, with ``#<unit>`` for a unit above 1."""
    return path if unit <= 1 else f"{path}#{unit}"


def ref_key(path: str) -> str:
    """The layout key of the sheet reference of the module at ``path``."""
    return f"{REF_PREFIX}{path}"


def sheet_ref_size(name: str) -> int:
    """The width of the box of a sheet reference named ``name``: room for the name and a character on
    each side, at least ``REF_MIN_WIDTH``, rounded up to ``ORIGIN_STEP``."""
    return _up(max(REF_MIN_WIDTH, CHAR_ROOM * (len(name) + 2)))


def ref_extent(ref: RefBox) -> tuple[int, int, int, int]:
    """The cell of a sheet reference relative to the top-left corner of its box: the box, the room of its
    name above and of its file below, and the margin."""
    width = max(sheet_ref_size(ref.name), _up(CHAR_ROOM * len(ref.file)))
    return (
        -CELL_MARGIN,
        -(CELL_MARGIN + REF_TEXT),
        width + CELL_MARGIN,
        REF_HEIGHT + REF_TEXT + CELL_MARGIN,
    )


def _split(key: str) -> tuple[str, int]:
    path, sep, unit = key.rpartition("#")
    if sep and unit.isdigit():
        return path, int(unit)
    return key, 1


def _order(key: str) -> tuple[object, ...]:
    path, unit = _split(key)
    module = path.split("/", 1)[0] if "/" in path else ""
    return (module != "", natural_key(module), natural_key(path), unit)


def _module(key: str) -> str:
    path = _split(key)[0]
    return path.split("/", 1)[0] if "/" in path else ""


def _up(value: int, step: int = ORIGIN_STEP) -> int:
    return -(-value // step) * step


def _down(value: int, step: int = ORIGIN_STEP) -> int:
    return (value // step) * step


def extent(unit: UnitBox, rotation: int = 0, mirror: str = "") -> tuple[int, int, int, int]:
    """The cell of ``unit`` relative to its origin, in the sheet frame (Y down): the body and the pin
    ends, the room of the labels on each side, the margin and the text room above, rounded outwards to
    ``ORIGIN_STEP``."""
    x0, y0, x1, y1 = unit.body
    corners = [pin_point(Point(0, 0), Point(x, y), rotation, mirror) for x in (x0, x1) for y in (y0, y1)]
    ends = [pin_point(Point(0, 0), pin.at, rotation, mirror) for pin in unit.pins]
    xs = [p.x for p in (*corners, *ends)] or [0]
    ys = [p.y for p in (*corners, *ends)] or [0]
    longest = {0: 0, 90: 0, 180: 0, 270: 0}
    for pin in unit.pins:
        side = label_angle(pin.angle, rotation, mirror)
        longest[side] = max(longest[side], pin.label)
    room = {side: chars * CHAR_ROOM + LABEL_ROOM + CELL_MARGIN for side, chars in longest.items()}
    return (
        _down(min(xs) - room[180]),
        _down(min(ys) - max(room[90], TEXT_ROOM + CELL_MARGIN)),
        _up(max(xs) + room[0]),
        _up(max(ys) + room[270]),
    )


# --- satellites (change c0070) --------------------------------------------------------------------

Box = tuple[int, int, int, int]
_STEP: Mapping[int, tuple[int, int]] = MappingProxyType({0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)})
"""The step of a sheet angle (0 right, 90 up, 180 left, 270 down) on the sheet, whose Y axis points down."""
_LIB_STEP: Mapping[int, tuple[int, int]] = MappingProxyType(
    {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
)


@dataclass(frozen=True, slots=True)
class SnapWire:
    """The wire of a snapped satellite, from the connection point of ``anchor_pin`` to that of the
    satellite's ``near_pin``; the points are relative to the origin of the anchor."""

    satellite: str
    anchor_pin: str
    near_pin: str
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class SnapLabel:
    """The one label of a wired pair: at the satellite's near pin ``pin``, turned to ``angle`` degrees;
    the point is relative to the origin of the anchor."""

    satellite: str
    pin: str
    at: Point
    angle: int


@dataclass(frozen=True, slots=True)
class Cluster:
    """An anchor and the satellites snapped to its pins. Every position is relative to the origin of the
    anchor: ``satellites`` holds each satellite's key and placement, ``wires`` and ``labels`` one entry
    per satellite, and ``boxes`` what the satellites, their wires and their labels cover."""

    anchor: str
    satellites: tuple[tuple[str, SymbolPlacement], ...]
    wires: tuple[SnapWire, ...]
    labels: tuple[SnapLabel, ...]
    boxes: tuple[Box, ...] = ()


def _overlap(a: Box, b: Box) -> bool:
    """Whether two boxes share more than an edge; a wire is a box without a width."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _bounds(points: Sequence[Point]) -> Box:
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def _shift(box: Box, dx: int, dy: int) -> Box:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def body_box(unit: UnitBox, rotation: int = 0, mirror: str = "") -> Box:
    """What ``unit`` draws, relative to its origin on the sheet."""
    x0, y0, x1, y1 = unit.body
    return _bounds(
        [pin_point(Point(0, 0), Point(x, y), rotation, mirror) for x in (x0, x1) for y in (y0, y1)]
    )


def unit_bounds(unit: UnitBox, rotation: int = 0, mirror: str = "") -> Box:
    """The body of ``unit`` and its pin connection points, relative to its origin on the sheet."""
    x0, y0, x1, y1 = body_box(unit, rotation, mirror)
    ends = [pin_point(Point(0, 0), pin.at, rotation, mirror) for pin in unit.pins]
    return _bounds([Point(x0, y0), Point(x1, y1), *ends])


def turned_text_room(
    bounds: Box,
    ends: Sequence[Point],
    origin: Point,
    upwards: bool,
    length: int,
    across: tuple[Point, int] | None = None,
) -> Box:
    """The room of the Reference and the Value of a turned or mirrored unit: two lines of ``ORIGIN_STEP``,
    ``length`` long. The writer centres the Reference in its upper half and the Value in its lower half.

    ``bounds`` is the box of the unit's body and pin ends and ``ends`` its pin connection points, in the
    frame of ``origin``. With a pin that leaves the unit upwards the room lies to the right of the unit,
    around the height of ``origin``. Otherwise it lies above the unit, from its left edge, clear of the
    labels that continue its pins. ``across`` is a label at one of the pins that points up (90) or down
    (270), across the unit's axis: the room then lies on the label's side of the unit, ``ORIGIN_STEP``
    from the label's axis, and extends towards the other pins.
    """
    left, top, right, bottom = bounds
    if upwards:
        x0 = right + ORIGIN_STEP
        return (x0, origin.y - ORIGIN_STEP, x0 + length, origin.y + ORIGIN_STEP)
    ys = [point.y for point in ends] or [top, bottom]
    x0 = left
    below = False
    if across is not None and across[1] in (90, 270):
        at, angle = across
        below = angle == 270
        beyond = all(point.x >= at.x for point in ends)  # the other pins lie to the right of the label
        x0 = at.x + ORIGIN_STEP if beyond else at.x - ORIGIN_STEP - length
    if below:
        base = max(bottom, max(ys) + GRID)
        return (x0, base, x0 + length, base + 2 * ORIGIN_STEP)
    base = min(top, min(ys) - GRID)
    return (x0, base - 2 * ORIGIN_STEP, x0 + length, base)


def text_box(
    unit: UnitBox, rotation: int = 0, mirror: str = "", across: tuple[Point, int] | None = None
) -> Box | None:
    """The room of the Reference and the Value of ``unit`` where the writer puts them, relative to the
    unit's origin: above the unit, or to its right when one of its pins leaves it upwards. For a turned
    or mirrored unit whose pins leave it sideways the room is that of ``turned_text_room``, where
    ``across`` is the label at one of its pins that points across its axis. ``None`` for a unit without
    a text length."""
    if not unit.text:
        return None
    left, top, right, _ = bounds = unit_bounds(unit, rotation, mirror)
    length = unit.text * CHAR_ROOM
    if any(label_angle(pin.angle, rotation, mirror) == 90 for pin in unit.pins):
        return (right, -ORIGIN_STEP, right + ORIGIN_STEP + length, ORIGIN_STEP)
    if rotation or mirror:
        ends = [pin_point(Point(0, 0), pin.at, rotation, mirror) for pin in unit.pins]
        return turned_text_room(bounds, ends, Point(0, 0), False, length, across)
    return (left, top - 2 * ORIGIN_STEP, left + length, top)


def label_room(at: Point, angle: int, chars: int) -> Box:
    """The room of a global label of ``chars`` characters at ``at``, turned to ``angle`` degrees."""
    length = chars * CHAR_ROOM + LABEL_ROOM
    dx, dy = _STEP[angle]
    end = Point(at.x + dx * length, at.y + dy * length)
    x0, y0, x1, y1 = _bounds([at, end])
    return (x0 - GRID, y0, x1 + GRID, y1) if dx == 0 else (x0, y0 - GRID, x1, y1 + GRID)


def _on_wire(point: Point, start: Point, end: Point) -> bool:
    return min(start.x, end.x) <= point.x <= max(start.x, end.x) and min(start.y, end.y) <= point.y <= max(
        start.y, end.y
    )


def is_satellite(unit: UnitBox, nets: Mapping[tuple[str, str], str], single: bool) -> bool:
    """Whether ``unit`` may be snapped: the one unit of its component, with exactly two pins that face
    each other along one axis, at least one of them on a net and the two not on one net."""
    if unit.key.startswith("#") or not single or len(unit.pins) != 2:
        return False
    first, second = unit.pins
    one, two = nets.get((unit.key, first.number)), nets.get((unit.key, second.number))
    if (one is None and two is None) or one == two:
        return False
    dx, dy = second.at.x - first.at.x, second.at.y - first.at.y
    if (dx == 0) == (dy == 0):
        return False
    towards = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    return _LIB_STEP[first.angle % 360] == towards and _LIB_STEP[second.angle % 360] == (
        -towards[0],
        -towards[1],
    )


@dataclass
class _Around:
    """What lies around one anchor, relative to its origin: the obstacles a satellite may not overlap, the
    boxes of the satellites snapped so far, their wires and every pin point."""

    unit: UnitBox
    place: SymbolPlacement | None
    obstacles: list[Box]
    rooms: dict[str, Box]
    points: dict[str, Point]
    taken: set[str]
    boxes: list[Box]
    wires: list[tuple[Point, Point]]
    pins: list[Point]
    satellites: list[tuple[str, SymbolPlacement]]
    snap_wires: list[SnapWire]
    labels: list[SnapLabel]


def _around(
    anchor: UnitBox,
    nets: Mapping[tuple[str, str], str],
    fixed: Mapping[str, SymbolPlacement],
    others: Sequence[UnitBox],
) -> _Around:
    place = fixed.get(anchor.key)
    rotation, mirror = (place.rotation, place.mirror) if place is not None else (0, "")
    obstacles = [body_box(anchor, rotation, mirror)]
    text = text_box(anchor, rotation, mirror)
    if text is not None:
        obstacles.append(text)
    if place is not None:  # around a placed anchor the cells of the other placed units are known
        for other in others:
            at = fixed[other.key]
            obstacles.append(_shift(extent(other, at.rotation, at.mirror), at.x - place.x, at.y - place.y))
    points = {pin.number: pin_point(Point(0, 0), pin.at, rotation, mirror) for pin in anchor.pins}
    rooms = {
        pin.number: label_room(
            points[pin.number], label_angle(pin.angle, rotation, mirror), len(nets[(anchor.key, pin.number)])
        )
        for pin in anchor.pins
        if (anchor.key, pin.number) in nets
    }
    return _Around(anchor, place, obstacles, rooms, points, set(), [], [], list(points.values()), [], [], [])


def _try(
    around: _Around,
    pin: UnitPin,
    satellite: UnitBox,
    near: UnitPin,
    far: UnitPin,
    nets: Mapping[tuple[str, str], str],
    fixed: Mapping[str, SymbolPlacement],
) -> bool:
    """Snap ``satellite`` with its pin ``near`` to the anchor pin ``pin`` when every condition holds."""
    anchor = around.unit
    turn, flip = (around.place.rotation, around.place.mirror) if around.place is not None else (0, "")
    start = around.points[pin.number]
    outward = label_angle(pin.angle, turn, flip)
    facing = (outward + 180) % 360
    rotation = next(
        (r for r in ROTATIONS if (r, "") in PROVED_FRAMES and label_angle(near.angle, r, "") == facing), None
    )
    if rotation is None:
        return False
    dx, dy = _STEP[outward]
    end = Point(start.x + dx * SNAP_REACH, start.y + dy * SNAP_REACH)
    offset = pin_point(Point(0, 0), near.at, rotation, "")
    origin = Point(end.x - offset.x, end.y - offset.y)
    if origin.x % GRID or origin.y % GRID:
        return False
    placed = fixed.get(satellite.key)
    if placed is not None:
        if around.place is None:
            return False
        wanted = SymbolPlacement(around.place.x + origin.x, around.place.y + origin.y, rotation, "")
        if placed != wanted:
            return False
    far_point = pin_point(origin, far.at, rotation, "")
    body = _shift(body_box(satellite, rotation, ""), origin.x, origin.y)
    new: list[Box] = [_shift(unit_bounds(satellite, rotation, ""), origin.x, origin.y)]
    # the label of the pair points away from the centre line of the anchor's body, across the wire
    x0, y0, x1, y1 = around.obstacles[0]
    if dy == 0:
        angle = 90 if 2 * start.y <= y0 + y1 else 270
    else:
        angle = 180 if 2 * start.x <= x0 + x1 else 0
    # the Reference and the Value of a satellite turned on its side lie beside that label, on its side
    text = text_box(satellite, rotation, "", (offset, angle))
    if text is not None:
        text = _shift(text, origin.x, origin.y)
        new.append(text)
    far_net = nets.get((satellite.key, far.number))
    if far_net is not None:
        new.append(label_room(far_point, label_angle(far.angle, rotation, ""), len(far_net)))
    pair = label_room(end, angle, len(nets[(anchor.key, pin.number)]))
    if _overlap(pair, body) or (text is not None and _overlap(pair, text)):
        return False
    wire = _bounds([start, end])
    new += [pair, wire]
    rooms = [
        room for number, room in around.rooms.items() if number != pin.number and number not in around.taken
    ]
    if any(_overlap(box, other) for box in new for other in (*around.obstacles, *rooms, *around.boxes)):
        return False
    if any(_on_wire(point, start, end) for point in (*around.pins, far_point) if point != start):
        return False
    if any(
        point in around.pins or _on_wire(point, *other)
        for point in (end, far_point)
        for other in around.wires
    ):
        return False
    if end in around.pins or far_point in around.pins:
        return False
    around.taken.add(pin.number)
    around.boxes += new
    around.wires.append((start, end))
    around.pins += [end, far_point]
    around.satellites.append((satellite.key, SymbolPlacement(origin.x, origin.y, rotation, "")))
    around.snap_wires.append(SnapWire(satellite.key, pin.number, near.number, start, end))
    around.labels.append(SnapLabel(satellite.key, near.number, end, angle))
    return True


def snap_satellites(
    units: Sequence[UnitBox],
    nets: Mapping[tuple[str, str], str],
    *,
    placements: Mapping[str, SymbolPlacement] | None = None,
) -> tuple[Cluster, ...]:
    """Each 2-pin part of one sheet that fits beside an IC pin of its net, joined to it by one wire.

    ``nets`` maps (unit key, pin number) to the label text of that pin. An anchor is a unit with three
    pins or more; a satellite is the one unit of a component with two pins that face each other
    (``is_satellite``). Satellites are tried in the natural order of their paths, on the free anchor
    pins of their nets in anchor order and then in natural pin order, and the first pin that fits is
    taken: the satellite is turned so that its near pin faces the anchor pin, ``SNAP_REACH`` away from
    it, and it must overlap neither the anchor's body, texts and other labels nor a satellite already
    snapped. A placed satellite is snapped only around a placed anchor, at exactly the snapped place.
    The result holds one ``Cluster`` per anchor that took a satellite, in anchor order.
    """
    fixed = {key: place for key, place in (placements or {}).items()}
    by_path: dict[str, int] = {}
    for unit in units:
        by_path[_split(unit.key)[0]] = by_path.get(_split(unit.key)[0], 0) + 1
    candidates = [u for u in units if is_satellite(u, nets, by_path[_split(u.key)[0]] == 1)]
    names = {unit.key for unit in candidates}
    anchors = sorted(
        (u for u in units if len(u.pins) >= 3 and not u.key.startswith("#")), key=lambda u: _order(u.key)
    )
    others = [u for u in units if u.key in fixed and u.key not in names]
    around = [_around(a, nets, fixed, [o for o in others if o.key != a.key]) for a in anchors]
    for satellite in sorted(candidates, key=lambda u: natural_key(u.key)):
        first, second = satellite.pins
        wanted = {
            nets[(satellite.key, near.number)]: (near, far)
            for near, far in ((second, first), (first, second))
            if (satellite.key, near.number) in nets
        }
        done = False
        for state in around:
            for pin in sorted(state.unit.pins, key=lambda p: natural_key(p.number)):
                net = nets.get((state.unit.key, pin.number))
                if net is None or net not in wanted or pin.number in state.taken:
                    continue
                near, far = wanted[net]
                if _try(state, pin, satellite, near, far, nets, fixed):
                    done = True
                    break
            if done:
                break
    return tuple(
        Cluster(
            state.unit.key,
            tuple(state.satellites),
            tuple(state.snap_wires),
            tuple(state.labels),
            tuple(state.boxes),
        )
        for state in around
        if state.satellites
    )


def cluster_extent(unit: UnitBox, cluster: Cluster, rotation: int = 0, mirror: str = "") -> Box:
    """The cell of an anchor with its cluster, relative to the anchor's origin: the anchor's own cell and
    every box of the cluster grown by ``CELL_MARGIN``, rounded outwards to ``ORIGIN_STEP``."""
    x0, y0, x1, y1 = extent(unit, rotation, mirror)
    for a, b, c, d in cluster.boxes:
        x0, y0 = min(x0, a - CELL_MARGIN), min(y0, b - CELL_MARGIN)
        x1, y1 = max(x1, c + CELL_MARGIN), max(y1, d + CELL_MARGIN)
    return (_down(x0), _down(y0), _up(x1), _up(y1))


def _issue(code: str, severity: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, severity, message, where=where, hint=hint)  # type: ignore[arg-type]


def _flow(
    groups: Sequence[Sequence[tuple[int, int]]], usable_width: int
) -> tuple[list[list[tuple[int, int]]], int]:
    """Each group packed in rows of its own, the groups one under the other: offsets and total height."""
    offsets: list[list[tuple[int, int]]] = []
    top = 0
    for cells in groups:
        packed, height = shelf_pack(cells, usable_width)
        offsets.append([(x, top + y) for x, y in packed])
        top += height
    return offsets, top


def layout_units(
    units: Sequence[UnitBox],
    *,
    placements: Mapping[str, SymbolPlacement] | None = None,
    flags: Sequence[UnitBox] = (),
    clusters: Sequence[Cluster] = (),
    refs: Sequence[RefBox] = (),
    sheet: str = "",
) -> SheetLayout:
    """Place every unit, every sheet reference and every power flag of one sheet on its page.

    Units are ordered by top-level module (units outside a module first), then by the natural order of
    their component path, then by unit; the first unit of a module starts a new row. A cluster takes
    the place of its anchor, in one cell, and its satellites leave the order. The sheet references
    follow in rows of their own, in the natural order of their module paths, and the flags take the last
    row. A unit named by ``placements`` takes the given origin, rotation and mirror and leaves the flow.
    The paper is the first of ``PAPERS`` in which the flow fits; ``sheet`` names the sheet in the issue
    that says none does.
    """
    fixed = dict(placements or {})
    issues: list[Issue] = []
    known = {unit.key for unit in units}
    if len(known) != len(units):
        raise ValueError("two units share a key")
    for key in sorted(set(fixed) - known):
        issues.append(
            _issue(
                "build.symbol-placement-unknown",
                "warning",
                f"schematic-placements.toml names {key!r}, which is no unit of the design",
                key,
                "a unit is named by its component path, with #<unit> for a unit above 1",
            )
        )
    seen: set[str] = set()
    for unit in (*units, *flags):
        if unit.symbol in seen or all(p.at.x % GRID == 0 and p.at.y % GRID == 0 for p in unit.pins):
            continue
        seen.add(unit.symbol)
        issues.append(
            _issue(
                "kicad.sch.pin-off-grid",
                "info",
                f"symbol {unit.symbol} has a pin off the 1.27 mm grid; KiCad's ERC warns about such pin ends",
                unit.symbol,
            )
        )
    around = {cluster.anchor: cluster for cluster in clusters}
    snapped = {key for cluster in clusters for key, _ in cluster.satellites}

    def cell(unit: UnitBox, rotation: int = 0, mirror: str = "") -> Box:
        if unit.key in around:
            return cluster_extent(unit, around[unit.key], rotation, mirror)
        return extent(unit, rotation, mirror)

    ordered = sorted(
        (u for u in units if u.key not in fixed and u.key not in snapped), key=lambda u: _order(u.key)
    )
    unit_groups: list[list[UnitBox]] = []
    for unit in ordered:
        if not unit_groups or _module(unit_groups[-1][0].key) != _module(unit.key):
            unit_groups.append([])
        unit_groups[-1].append(unit)
    boxes = sorted(refs, key=lambda ref: natural_key(ref.path))
    groups: list[list[str]] = [[unit.key for unit in group] for group in unit_groups]
    extents = [[cell(unit) for unit in group] for group in unit_groups]
    if boxes:
        groups.append([ref_key(ref.path) for ref in boxes])
        extents.append([ref_extent(ref) for ref in boxes])
    if flags:
        groups.append([flag.key for flag in flags])
        extents.append([extent(flag) for flag in flags])
    sizes = [[(x1 - x0, y1 - y0) for x0, y0, x1, y1 in group] for group in extents]
    chosen: tuple[str, int, int] | None = None
    for name, width, height in PAPERS:
        usable = _down(width - 2 * PAGE_MARGIN)
        if any(w > usable for group in sizes for w, _ in group):
            continue
        if _flow(sizes, usable)[1] <= height - PAGE_MARGIN - TITLE_BAND:
            chosen = (name, width, height)
            break
    if chosen is None:
        chosen = PAPERS[-1]
        count = len(units) + len(flags)
        named = f"sheet {sheet}: " if sheet else ""
        issues.append(
            _issue(
                "build.schematic-too-large",
                "error",
                f"{named}{count} units do not fit one A0 page",
                sheet,
                "put parts into modules (each module gets a sheet of its own), or build with "
                "--schematic skip",
            )
        )
    offsets = _flow(sizes, _down(chosen[1] - 2 * PAGE_MARGIN))[0]
    origins: dict[str, SymbolPlacement] = {}
    cells: dict[str, tuple[int, int, int, int]] = {}
    for group, found, places in zip(groups, extents, offsets, strict=True):
        for key, (x0, y0, x1, y1), (left, top) in zip(group, found, places, strict=True):
            x, y = PAGE_MARGIN + left - x0, PAGE_MARGIN + top - y0
            origins[key] = SymbolPlacement(x, y)
            cells[key] = (x + x0, y + y0, x + x1, y + y1)
    by_key = {unit.key: unit for unit in units}
    for key in sorted(set(fixed) & known):
        place = fixed[key]
        x0, y0, x1, y1 = cell(by_key[key], place.rotation, place.mirror)
        origins[key] = place
        cells[key] = (place.x + x0, place.y + y0, place.x + x1, place.y + y1)
    for cluster in clusters:  # a satellite lies where its anchor puts it, inside the anchor's cell
        anchor = origins[cluster.anchor]
        for key, place in cluster.satellites:
            at = SymbolPlacement(anchor.x + place.x, anchor.y + place.y, place.rotation, place.mirror)
            origins[key] = at
            cells[key] = _shift(unit_bounds(by_key[key], at.rotation, at.mirror), at.x, at.y)
    if fixed:
        issues += _collisions([*units, *flags], origins, cells, set(fixed) & known, snapped)
    return SheetLayout(chosen[0], MappingProxyType(origins), MappingProxyType(cells), tuple(issues))


def _collisions(
    units: Sequence[UnitBox],
    origins: Mapping[str, SymbolPlacement],
    cells: Mapping[str, tuple[int, int, int, int]],
    fixed: set[str],
    snapped: frozenset[str] | set[str] = frozenset(),
) -> list[Issue]:
    """``build.symbol-short`` for two units with a common connection point, and ``build.symbol-overlap``
    for a placed unit whose cell overlaps another cell without a short. A snapped satellite lies inside
    the cell of its cluster, so its own cell is not compared."""
    found: list[Issue] = []
    at: dict[Point, str] = {}
    shorts: set[tuple[str, str]] = set()
    for unit in sorted(units, key=lambda u: _order(u.key)):
        place = origins[unit.key]
        for pin in unit.pins:
            point = pin_point(Point(place.x, place.y), pin.at, place.rotation, place.mirror)
            other = at.setdefault(point, unit.key)
            if other != unit.key and (other, unit.key) not in shorts:
                shorts.add((other, unit.key))
                found.append(
                    _issue(
                        "build.symbol-short",
                        "error",
                        f"a pin of {other} and a pin of {unit.key} connect at the same point of the sheet",
                        unit.key,
                        "move one of them in schematic-placements.toml",
                    )
                )
    keys = sorted((key for key in cells if key not in snapped), key=_order)
    for index, first in enumerate(keys):
        for second in keys[index + 1 :]:
            if first not in fixed and second not in fixed:
                continue
            if (first, second) in shorts or (second, first) in shorts:
                continue
            a, b = cells[first], cells[second]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                found.append(
                    _issue(
                        "build.symbol-overlap",
                        "warning",
                        f"the cells of {first} and {second} overlap on the sheet",
                        second if second in fixed else first,
                    )
                )
    return found


__all__ = [
    "CELL_MARGIN",
    "CHAR_ROOM",
    "GRID",
    "LABEL_ROOM",
    "MIRRORS",
    "ORIGIN_STEP",
    "PAGE_MARGIN",
    "PAPERS",
    "PROVED_FRAMES",
    "REF_HEIGHT",
    "REF_MIN_WIDTH",
    "REF_PREFIX",
    "REF_TEXT",
    "ROTATIONS",
    "SNAP_REACH",
    "TEXT_ROOM",
    "TITLE_BAND",
    "Cluster",
    "RefBox",
    "SheetLayout",
    "SnapLabel",
    "SnapWire",
    "SymbolPlacement",
    "UnitBox",
    "UnitPin",
    "body_box",
    "cluster_extent",
    "extent",
    "is_satellite",
    "label_angle",
    "label_room",
    "layout_units",
    "natural_key",
    "pin_point",
    "snap_satellites",
    "text_box",
    "turned_text_room",
    "unit_bounds",
    "ref_extent",
    "ref_key",
    "sheet_ref_size",
    "turned",
    "unit_key",
]
