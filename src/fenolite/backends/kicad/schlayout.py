# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layout of a generated schematic sheet: where each unit of each symbol goes, and where its pins
connect (capability ``kicad-schematic``, "Pin connection points" and "Deterministic sheet layout"; change
c0061).

Every unit takes one cell; cells fill rows from the left, a module starts a new row, and the power flags
take the last row. The paper is the smallest A size that holds the rows. The pin frame is a fact of
``docs/formats/kicad/schematic.md`` (``H-K-SCH-PINFRAME``); every length constant is a Fenolite choice.
Lengths are integer nanometres and no float is used. Readable drawings are another change (v0.2b).
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
a pin (probes ``sch-pin-frame-<angle>-<mirror>``). A placements file may ask for no other pair."""
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


@dataclass(frozen=True, slots=True)
class SheetLayout:
    """The chosen paper, each unit's placement and cell ``(x0, y0, x1, y1)`` on the sheet, and the
    layout's issues."""

    paper: str
    origins: Mapping[str, SymbolPlacement]
    cells: Mapping[str, tuple[int, int, int, int]]
    issues: tuple[Issue, ...] = ()


def turned(x: int, y: int, rotation: int, mirror: str) -> tuple[int, int]:
    """A library vector (Y up) after the mirror and then the rotation of an instance."""
    if rotation not in _TURN:
        raise ValueError(f"symbol rotation {rotation} is not 0, 90, 180 or 270 degrees")
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    elif mirror:
        raise ValueError(f"symbol mirror {mirror!r} is not '', 'x' or 'y'")
    a, b, c, d = _TURN[rotation]
    return a * x + b * y, c * x + d * y


def pin_point(origin: Point, pin: Point, rotation: int = 0, mirror: str = "") -> Point:
    """The sheet position at which a pin connects, for a symbol instance at ``origin``.

    ``pin`` is the pin's position in the library frame, whose Y axis points up. The mirror is applied
    first (``"x"`` negates y, ``"y"`` negates x), then the rotation by ``rotation`` degrees, and the sheet
    turns Y down: ``(x + px′, y − py′)``.
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
) -> SheetLayout:
    """Place every unit and every power flag on one page.

    Units are ordered by top-level module (units outside a module first), then by the natural order of
    their component path, then by unit; the first unit of a module starts a new row and the flags take
    the last row. A unit named by ``placements`` takes the given origin, rotation and mirror and leaves
    the flow. The paper is the first of ``PAPERS`` in which the flow fits.
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
    ordered = sorted((u for u in units if u.key not in fixed), key=lambda u: _order(u.key))
    groups: list[list[UnitBox]] = []
    for unit in ordered:
        if not groups or _module(groups[-1][0].key) != _module(unit.key):
            groups.append([])
        groups[-1].append(unit)
    if flags:
        groups.append(list(flags))
    extents = [[extent(unit) for unit in group] for group in groups]
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
        issues.append(
            _issue(
                "build.schematic-too-large",
                "error",
                f"{count} units do not fit one A0 page; a sheet per module is a later release (v0.2b)",
                hint="build with --schematic skip, or split the design",
            )
        )
    offsets = _flow(sizes, _down(chosen[1] - 2 * PAGE_MARGIN))[0]
    origins: dict[str, SymbolPlacement] = {}
    cells: dict[str, tuple[int, int, int, int]] = {}
    for group, boxes, places in zip(groups, extents, offsets, strict=True):
        for unit, (x0, y0, x1, y1), (left, top) in zip(group, boxes, places, strict=True):
            x, y = PAGE_MARGIN + left - x0, PAGE_MARGIN + top - y0
            origins[unit.key] = SymbolPlacement(x, y)
            cells[unit.key] = (x + x0, y + y0, x + x1, y + y1)
    by_key = {unit.key: unit for unit in units}
    for key in sorted(set(fixed) & known):
        place = fixed[key]
        x0, y0, x1, y1 = extent(by_key[key], place.rotation, place.mirror)
        origins[key] = place
        cells[key] = (place.x + x0, place.y + y0, place.x + x1, place.y + y1)
    if fixed:
        issues += _collisions([*units, *flags], origins, cells, set(fixed) & known)
    return SheetLayout(chosen[0], MappingProxyType(origins), MappingProxyType(cells), tuple(issues))


def _collisions(
    units: Sequence[UnitBox],
    origins: Mapping[str, SymbolPlacement],
    cells: Mapping[str, tuple[int, int, int, int]],
    fixed: set[str],
) -> list[Issue]:
    """``build.symbol-short`` for two units with a common connection point, and ``build.symbol-overlap``
    for a placed unit whose cell overlaps another cell without a short."""
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
    keys = sorted(cells, key=_order)
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
    "ROTATIONS",
    "TEXT_ROOM",
    "TITLE_BAND",
    "SheetLayout",
    "SymbolPlacement",
    "UnitBox",
    "UnitPin",
    "extent",
    "label_angle",
    "layout_units",
    "natural_key",
    "pin_point",
    "turned",
    "unit_key",
]
