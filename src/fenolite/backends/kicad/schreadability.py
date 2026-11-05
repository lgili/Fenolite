# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Readability measures of one schematic sheet (capability ``kicad-schematic``, "Readability measures of a
generated sheet"; change c0406).

The measures count what public drafting guidance asks a readable schematic to avoid
(``docs/schematic-drafting.md``): labels where a wire would do, wires that cross, run over a pin or a body,
four wires at one point, a wire that ends on another without a junction, and texts that overlap. They are
read from the sheet's own content and embedded definitions, so they apply to any created sheet; nothing
here reads a file or the circuit. Text extents are estimates: one character height per character, 2 mm
per line.
"""

# evidence: none, it measures a created sheet's drawing and states no fact about a file format or a tool

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import sch, schlayout, symembed
from fenolite.core.coords import Point
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SchematicSheet, SymbolInstance

Box = tuple[int, int, int, int]
CHAR = 1_270_000
"""The estimated width of one character of a field: one character height (1.27 mm)."""
LINE = 2_000_000
"""The estimated height of one line of text."""
SHOWN = frozenset({"Reference", "Value"})


@dataclass(frozen=True, slots=True)
class SheetMeasures:
    """The measures of one sheet: ``labels`` per kind, the number of wire segments, junctions and power
    symbol instances, and the counts of the faults a readable sheet avoids."""

    labels: Mapping[str, int]
    wires: int
    junctions: int
    power_symbols: int
    crossings: int
    wire_over_pin: int
    wire_over_body: int
    four_way: int
    bare_tees: int
    overlaps: int

    @property
    def label_count(self) -> int:
        return sum(self.labels.values())


def _transform(instance: SymbolInstance, point: Point) -> Point:
    rotation = (instance.rotation // 1_000_000) % 360
    return schlayout.pin_point(instance.position, point, rotation, instance.mirror)


def _box(points: Iterable[Point]) -> Box | None:
    found = list(points)
    if not found:
        return None
    xs = [p.x for p in found]
    ys = [p.y for p in found]
    return (min(xs), min(ys), max(xs), max(ys))


def _graphics_box(definition: SymbolDef, unit: int, body_style: int) -> list[Point]:
    """The corners of what a unit draws, in the library frame (pins left out)."""
    found: list[Point] = []
    for graphic in definition.graphics:
        if graphic.unit not in (0, unit) or graphic.body_style not in (0, body_style):
            continue
        points = list(graphic.points)
        if graphic.kind == "circle" and len(points) == 2:
            centre, rim = points
            radius = abs(rim.x - centre.x) + abs(rim.y - centre.y)
            low = Point(centre.x - radius, centre.y - radius)
            points = [low, Point(centre.x + radius, centre.y + radius)]
        found += points
    return found


def _strictly_inside(point: Point, start: Point, end: Point) -> bool:
    """Whether ``point`` lies on the straight wire from ``start`` to ``end`` and is neither of its ends."""
    if point in (start, end):
        return False
    if start.x == end.x == point.x:
        return min(start.y, end.y) < point.y < max(start.y, end.y)
    if start.y == end.y == point.y:
        return min(start.x, end.x) < point.x < max(start.x, end.x)
    return False


def _enters(box: Box, start: Point, end: Point) -> bool:
    """Whether the straight wire enters the inside of ``box`` (touching its edge does not count)."""
    x0, y0, x1, y1 = box
    if start.y == end.y:
        return y0 < start.y < y1 and min(start.x, end.x) < x1 and x0 < max(start.x, end.x)
    if start.x == end.x:
        return x0 < start.x < x1 and min(start.y, end.y) < y1 and y0 < max(start.y, end.y)
    return False


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _text(centre: Point, chars: int, level: bool) -> Box:
    half_w = chars * CHAR // 2
    half_h = LINE // 2
    if not level:
        half_w, half_h = half_h, half_w
    return (centre.x - half_w, centre.y - half_h, centre.x + half_w, centre.y + half_h)


def measure_sheet(sheet: SchematicSheet) -> SheetMeasures:
    """The readability measures of ``sheet`` ("Readability measures of a generated sheet")."""
    known = {definition.lib_id: definition for definition in sheet.lib_symbols}
    wires = [(wire.start, wire.end) for wire in sheet.wires]
    junctions = {junction.position for junction in sheet.junctions}
    pins: list[Point] = []
    rooms: list[tuple[str, Box]] = []  # (owner, room)
    power_count = 0
    bodies: list[Box] = []
    for index, instance in enumerate(sheet.symbols):
        definition = known.get(instance.lib_name or instance.lib_ref)
        if definition is None:
            continue
        owner = f"{index}"
        power = symembed.is_power_symbol(definition.lib_id) or symembed.is_power_flag(definition.lib_id)
        power_count += 1 if symembed.is_power_symbol(definition.lib_id) else 0
        for pin in definition.pins_of(instance.unit, instance.body_style):
            pins.append(_transform(instance, pin.position))
        corners = _graphics_box(definition, instance.unit, instance.body_style)
        body = _box(_transform(instance, corner) for corner in corners)
        if body is not None:
            rooms.append((owner, body))
            if not power:
                bodies.append(body)
        turned = (instance.rotation // 1_000_000) % 180 != 0
        for pose in sch.field_poses(instance).values():
            if pose.name not in SHOWN or pose.hide:
                continue
            text = instance.properties.get(pose.name, "")
            if not text:
                continue
            level = (((pose.rotation // 1_000_000) + (90 if turned else 0)) % 180) == 0
            rooms.append((owner, _text(pose.at, len(text), level)))
    for index, label in enumerate(sheet.labels):
        angle = (label.rotation // 1_000_000) % 360
        rooms.append((f"label:{index}", schlayout.label_room(label.position, angle, len(label.name))))
    # wires: crossings, pins on their inside, bodies they enter, four-way points, bare tees
    directions: dict[Point, set[int]] = defaultdict(set)
    for start, end in wires:
        dx = (end.x > start.x) - (end.x < start.x)
        dy = (end.y > start.y) - (end.y < start.y)
        directions[start].add(_angle(dx, dy))
        directions[end].add(_angle(-dx, -dy))
    crossings = 0
    for i, (a, b) in enumerate(wires):
        for c, d in wires[i + 1 :]:
            if a.y == b.y and c.x == d.x:
                point = Point(c.x, a.y)
            elif a.x == b.x and c.y == d.y:
                point = Point(a.x, c.y)
            else:
                continue
            if _strictly_inside(point, a, b) and _strictly_inside(point, c, d) and point not in junctions:
                crossings += 1
    for start, end in wires:
        for point in junctions:
            if _strictly_inside(point, start, end):
                directions[point] |= {_angle(*_unit(start, end)), _angle(*_unit(end, start))}
    over_pin = sum(1 for point in pins for start, end in wires if _strictly_inside(point, start, end))
    over_body = sum(1 for start, end in wires if any(_enters(body, start, end) for body in bodies))
    four_way = sum(1 for dirs in directions.values() if len(dirs) >= 4)
    ends = Counter(point for wire in wires for point in wire)
    bare = sum(
        1
        for point in ends
        if point not in junctions and any(_strictly_inside(point, start, end) for start, end in wires)
    )
    overlaps = _overlaps(rooms)
    kinds = Counter(label.kind for label in sheet.labels)
    return SheetMeasures(
        MappingProxyType(dict(sorted(kinds.items()))),
        len(wires),
        len(junctions),
        power_count,
        crossings,
        over_pin,
        over_body,
        four_way,
        bare,
        overlaps,
    )


def _unit(start: Point, end: Point) -> tuple[int, int]:
    return ((end.x > start.x) - (end.x < start.x), (end.y > start.y) - (end.y < start.y))


def _angle(dx: int, dy: int) -> int:
    return {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}.get((dx, dy), -1)


def _overlaps(rooms: Sequence[tuple[str, Box]]) -> int:
    """The pairs of rooms of different owners that overlap."""
    ordered = sorted(rooms, key=lambda item: item[1][0])
    count = 0
    for i, (owner, room) in enumerate(ordered):
        for other, found in ordered[i + 1 :]:
            if found[0] >= room[2]:
                break
            if other != owner and _overlap(room, found):
                count += 1
    return count


def measure_sheets(sheets: Iterable[SchematicSheet]) -> SheetMeasures:
    """The measures of several sheets (a root and its children), added up."""
    found = [measure_sheet(sheet) for sheet in sheets]
    labels: Counter[str] = Counter()
    for measures in found:
        labels.update(measures.labels)
    return SheetMeasures(
        MappingProxyType(dict(sorted(labels.items()))),
        *(sum(getattr(m, name) for m in found) for name in _COUNTS),
    )


_COUNTS = (
    "wires",
    "junctions",
    "power_symbols",
    "crossings",
    "wire_over_pin",
    "wire_over_body",
    "four_way",
    "bare_tees",
    "overlaps",
)


__all__ = ["SheetMeasures", "measure_sheet", "measure_sheets"]
