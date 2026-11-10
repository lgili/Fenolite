# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The symbol of a placed Altium component, from the records it embeds in its sheet (change c0470, design
D2; capability design-conversion, "Source symbols kept").

A schematic document stores each placed component with its own pins and body graphics, already turned and
mirrored onto the sheet. ``component_symbol`` undoes that pose: Altium mirrors about the vertical axis and
then turns counter-clockwise, so a point of the symbol frame (Y up, origin at the component location) is the
sheet offset turned back and then mirrored. With the mirror of ``drawn_read`` (``y`` at 0 and 180 degrees,
``x`` at 90 and 270) KiCad's own pose (turn, then mirror) puts every pin back on its sheet point.

Only the display mode that the component shows is drawn (KiCad body style 1); the records of its other
display modes are counted. Lines, polylines, polygons, rectangles, circles and pie charts map to KiCad
shapes; ellipses, arcs, elliptical arcs, round rectangles and Bézier curves are drawn as polylines; texts
and IEEE symbols of a body are not drawn. Each record that is not drawn as it is counts under its reason
(``CHANGED``). Every fact here is ``INFERRED`` (``drawn_read.EVIDENCE``).
"""

# evidence: see drawn_read

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from fenolite.backends.altium.adapter.pins import pin_etype, pin_shape
from fenolite.backends.altium.read.sch import (
    Arc,
    Bezier,
    Component,
    Ellipse,
    EllipticalArc,
    IeeeSymbol,
    Label,
    Line,
    Parameter,
    PieChart,
    Pin,
    Polygon,
    Polyline,
    Rectangle,
    RoundRectangle,
    SchDocument,
    SchLength,
    SchRecord,
)
from fenolite.backends.altium.read.sheet import LINE_WIDTHS
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.core.trig import FULL_TURN, ONE, cos_sin_fixed
from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

QUARTER = 90_000_000
ARC_STEPS = 32
"""Segments of a full circle drawn as a polyline; a partial arc gets its share, at least two."""
BEZIER_STEPS = 8
"""Segments of one cubic Bézier span."""

CHANGED_ARC = "an arc, elliptical arc or ellipse of the symbol body is drawn as a polyline"
CHANGED_ROUND = "a round rectangle of the symbol body is drawn as a polyline with round corners"
CHANGED_BEZIER = "a Bézier curve of the symbol body is drawn as a polyline"
CHANGED_TEXT = "a text of the symbol body is not drawn"
CHANGED_IEEE = "an IEEE symbol of the symbol body is not drawn"
CHANGED_MODE = "a display mode that the component does not show is not drawn"
CHANGED: tuple[str, ...] = (
    CHANGED_ARC,
    CHANGED_ROUND,
    CHANGED_BEZIER,
    CHANGED_TEXT,
    CHANGED_IEEE,
    CHANGED_MODE,
)
"""The reasons of the ``symbol-graphic`` rows (design D5), in report order."""
BODY = (Pin, Line, Polyline, Polygon, Rectangle, RoundRectangle, Arc, Ellipse, PieChart, Bezier,
        EllipticalArc, Label, IeeeSymbol)  # fmt: skip
"""The records of a symbol body: pins and graphics."""


class Pose:
    """The pose of a placed component: its location in fraction units, its quarter turns and its mirror."""

    def __init__(self, component: Component) -> None:
        location = component.location
        self.x = location[0].value
        self.y = location[1].value
        self.turns = component.orientation % 4
        self.mirrored = component.mirrored

    def local(self, at: tuple[SchLength, SchLength]) -> Point:
        """The symbol-frame point (nm, Y up) of the sheet point ``at``."""
        x, y = at[0].value - self.x, at[1].value - self.y
        for _ in range(self.turns):  # turn back: clockwise quarter turns
            x, y = y, -x
        if self.mirrored:
            x = -x
        return Point(SchLength(x).nm(), SchLength(y).nm())

    def direction(self, direction: int) -> int:
        """The symbol-frame direction (0 right, 1 up, 2 left, 3 down) of a sheet direction."""
        local = (direction - self.turns) % 4
        if self.mirrored and local % 2 == 0:
            local = 2 - local
        return local


def _width(record: SchRecord) -> int:
    props = record.props
    return LINE_WIDTHS.get(props.int("LINEWIDTH") if props is not None else 0, LINE_WIDTHS[0])


def _filled(record: SchRecord) -> bool:
    props = record.props
    if props is None or not props.bool("ISSOLID"):
        return False
    return not props.bool("TRANSPARENT")


def _scaled(radius: int, fixed: int) -> int:
    """``radius`` times the fixed-point ``fixed`` of ``core.trig``, rounded half to even."""
    quotient, remainder = divmod(radius * fixed, ONE)
    twice = 2 * remainder
    return quotient + (1 if twice > ONE or (twice == ONE and quotient % 2) else 0)


def _arc_points(
    pose: Pose, centre: tuple[SchLength, SchLength], rx: int, ry: int, start: int, end: int
) -> tuple[Point, ...]:
    """A polyline along an ellipse arc of radii ``rx`` and ``ry`` (fraction units), from ``start`` to ``end``
    microdegrees counter-clockwise; equal angles draw the whole ellipse."""
    sweep = (end - start) % FULL_TURN or FULL_TURN
    steps = max(2, -(-ARC_STEPS * sweep // FULL_TURN))
    points: list[Point] = []
    for step in range(steps + 1):
        cos, sin = cos_sin_fixed((start + sweep * step // steps) % FULL_TURN)
        x = centre[0].value + _scaled(rx, cos)
        y = centre[1].value + _scaled(ry, sin)
        points.append(pose.local((SchLength(x), SchLength(y))))
    return tuple(points)


def _bezier(points: Sequence[tuple[SchLength, SchLength]], pose: Pose) -> tuple[Point, ...]:
    values = [(p[0].value, p[1].value) for p in points]
    out = [pose.local(points[0])]
    for start in range(0, len(values) - 3, 3):
        p0, p1, p2, p3 = values[start : start + 4]
        for step in range(1, BEZIER_STEPS + 1):
            t = step / BEZIER_STEPS
            u = 1 - t
            x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
            y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
            out.append(pose.local((SchLength(round(x)), SchLength(round(y)))))
    return tuple(out)


def _round_rect(record: RoundRectangle, pose: Pose) -> tuple[Point, ...]:
    (x0, y0), (x1, y1) = sorted([record.location, record.corner], key=lambda p: (p[0].value, p[1].value))
    left, right = min(x0.value, x1.value), max(x0.value, x1.value)
    bottom, top = min(y0.value, y1.value), max(y0.value, y1.value)
    rx = min(record.corner_x_radius.value, (right - left) // 2)
    ry = min(record.corner_y_radius.value, (top - bottom) // 2)
    corners = ((right - rx, top - ry, 0), (left + rx, top - ry, 90), (left + rx, bottom + ry, 180),
               (right - rx, bottom + ry, 270))  # fmt: skip
    points: list[Point] = []
    for cx, cy, start in corners:
        points += _arc_points(pose, (SchLength(cx), SchLength(cy)), rx, ry, start * 1_000_000,
                              (start + 90) * 1_000_000)  # fmt: skip
    return (*points, points[0])


def graphic(record: SchRecord, pose: Pose) -> tuple[SymbolGraphic | None, str]:
    """The KiCad shape of one body record (``None`` when it is not drawn) and the reason of its change
    (``""`` when it is drawn as it is)."""
    width, filled = _width(record), _filled(record)
    if isinstance(record, Line):
        return SymbolGraphic("line", (pose.local(record.location), pose.local(record.corner)), width), ""
    if isinstance(record, Bezier):
        return SymbolGraphic("line", _bezier(record.points, pose), width), CHANGED_BEZIER
    if isinstance(record, Polyline):
        points = tuple(pose.local(p) for p in record.points)
        return (SymbolGraphic("line", points, width), "") if len(points) >= 2 else (None, "")
    if isinstance(record, Polygon):
        points = tuple(pose.local(p) for p in record.points)
        if len(points) < 3:
            return None, ""
        return SymbolGraphic("polygon", points, width, filled), ""
    if isinstance(record, RoundRectangle):
        return SymbolGraphic("polygon", _round_rect(record, pose), width, filled), CHANGED_ROUND
    if isinstance(record, Rectangle):
        return SymbolGraphic(
            "rect", (pose.local(record.location), pose.local(record.corner)), width, filled
        ), ""
    if isinstance(record, PieChart):
        r = record.radius.value
        points = _arc_points(pose, record.location, r, r, record.start_angle, record.end_angle)
        return SymbolGraphic("polygon", (pose.local(record.location), *points), width, filled), ""
    if isinstance(record, Arc | EllipticalArc):
        r = record.radius.value
        ry = record.secondary_radius.value if isinstance(record, EllipticalArc) else r
        whole = record.start_angle % 360_000_000 == record.end_angle % 360_000_000
        if whole and ry == r:
            centre = pose.local(record.location)
            return SymbolGraphic("circle", (centre, Point(centre.x + SchLength(r).nm(), centre.y)), width), ""
        points = _arc_points(pose, record.location, r, ry, record.start_angle, record.end_angle)
        return SymbolGraphic("line", points, width), CHANGED_ARC
    if isinstance(record, Ellipse):
        r, ry = record.radius.value, record.secondary_radius.value
        if r == ry:
            centre = pose.local(record.location)
            edge = Point(centre.x + SchLength(r).nm(), centre.y)
            return SymbolGraphic("circle", (centre, edge), width, filled), ""
        return SymbolGraphic(
            "polygon", _arc_points(pose, record.location, r, ry, 0, 0), width, filled
        ), CHANGED_ARC
    if isinstance(record, Label):
        return None, CHANGED_TEXT
    if isinstance(record, IeeeSymbol):
        return None, CHANGED_IEEE
    return None, ""


def _pin(pin: Pin, pose: Pose) -> SymbolPin:
    etype, _ = pin_etype(pin)
    shape, _ = pin_shape(pin)
    direction = pose.direction(pin.direction)
    return SymbolPin(
        number=pin.designator,
        name=pin.name,
        etype=etype,
        position=pose.local(pin.hot_end),
        shape=shape,
        rotation=((direction + 2) % 4) * QUARTER,
        length=pin.length.nm(),
        unit=max(pin.owner_part, 1),
        body_style=1,
        hidden=pin.hidden,
    )


def component_symbol(
    document: SchDocument, component: Component, *, name: str, library: str
) -> tuple[SymbolDef, Counter[str]]:
    """The KiCad symbol ``name`` of library ``library`` that draws ``component`` as its sheet shows it: one
    unit per part, the shown display mode as body style 1. The
    counter holds the body records per reason of ``CHANGED``."""
    pose = Pose(component)
    changed: Counter[str] = Counter()
    raw_pins: list[Pin] = []
    pins: list[SymbolPin] = []
    graphics: list[SymbolGraphic] = []
    mode = component.display_mode
    for child in document.children_of(component):
        if child.owner_display_mode != mode and isinstance(child, BODY):
            changed[CHANGED_MODE] += 1
            continue
        if isinstance(child, Pin):
            raw_pins.append(child)
            pins.append(_pin(child, pose))
            continue
        shape, reason = graphic(child, pose)
        if reason:
            changed[reason] += 1
        if shape is not None:
            unit = child.owner_part if child.owner_part > 0 else 0
            graphics.append(SymbolGraphic(shape.kind, shape.points, shape.width, shape.filled, unit, 0))
    parts = component.part_count  # the reader's PARTCOUNT − 1
    properties: dict[str, str] = {"Reference": _prefix(document, component)}
    comment = next((c.text for c in document.children_of(component) if isinstance(c, Parameter)
                    and c.name == "Comment"), "")  # fmt: skip
    properties["Value"] = "" if comment == "*" else comment
    native = f"{library}:{name}"
    pin_names_hidden = bool(raw_pins) and not any(p.name_shown and p.name not in ("", "~") for p in raw_pins)
    pin_numbers_hidden = bool(raw_pins) and not any(p.designator_shown for p in raw_pins)
    return (
        SymbolDef(
            id=derived_id("sym", "altium-sheet", native),
            name=name,
            library=library,
            properties=properties,
            pin_names_hidden=pin_names_hidden,
            pin_numbers_hidden=pin_numbers_hidden,
            units=tuple(SymbolUnit(unit, 1) for unit in range(1, parts + 1)),
            pins=tuple(pins),
            graphics=tuple(graphics),
        ),
        changed,
    )


def _prefix(document: SchDocument, component: Component) -> str:
    from fenolite.backends.altium.read.sch import Designator

    text = next((c.text for c in document.children_of(component) if isinstance(c, Designator)), "")
    prefix = text.rstrip("0123456789?").rstrip("_") or "U"
    return prefix


STEM = 2_540_000
"""The stem of a power symbol: 100 mil along +x from its pin, the direction of orientation 0."""


def _bars(widths: Sequence[int], step: int) -> tuple[SymbolGraphic, ...]:
    return tuple(
        SymbolGraphic("line", (Point(STEM + n * step, -w), Point(STEM + n * step, w)), 254_000)
        for n, w in enumerate(widths)
    )


def power_symbol(style: str, library: str = "AltiumPower") -> SymbolDef:
    """The KiCad power symbol ``library:style`` that stands for an Altium power port of that style
    (``drawn_read.POWER_STYLES``): flagged ``power global``, one hidden ``power_in`` pin of length 0 at the
    origin, a stem along +x and a mark of the style. Authored for Fenolite; the marks only recall the
    styles."""
    stem = SymbolGraphic("line", (Point(0, 0), Point(STEM, 0)), 254_000)
    half = 1_270_000
    marks: tuple[SymbolGraphic, ...]
    if style in ("bar", "gost_bar"):
        marks = _bars((half,), 0)
    elif style in ("power_ground", "gost_power_ground"):
        marks = _bars((half, 762_000, 254_000), 508_000)
    elif style in ("earth", "gost_earth"):
        marks = (SymbolGraphic("polygon", (Point(STEM, -half), Point(STEM, half), Point(STEM + half, 0)),
                               254_000),)  # fmt: skip
    elif style == "signal_ground":
        marks = (SymbolGraphic("polygon", (Point(STEM, -half), Point(STEM, half), Point(STEM + half, 0)),
                               254_000, True),)  # fmt: skip
    elif style == "circle":
        marks = (SymbolGraphic("circle", (Point(STEM + 635_000, 0), Point(STEM + 1_270_000, 0)), 254_000),)
    elif style in ("arrow", "gost_arrow"):
        marks = (SymbolGraphic("line", (Point(STEM - 635_000, -635_000), Point(STEM, 0),
                                        Point(STEM - 635_000, 635_000)), 254_000),)  # fmt: skip
    else:  # wave
        marks = (SymbolGraphic("line", (Point(STEM, -half), Point(STEM + 635_000, -635_000),
                                        Point(STEM, 0), Point(STEM + 635_000, 635_000), Point(STEM, half)),
                               254_000),)  # fmt: skip
    native = f"{library}:{style}"
    return SymbolDef(
        id=derived_id("sym", "altium-power", native),
        name=style,
        library=library,
        power="global",
        properties={"Reference": "#PWR", "Value": style},
        in_bom=False,
        on_board=False,
        pins=(SymbolPin("1", "", "power_in", Point(0, 0), length=0, hidden=True),),
        graphics=(stem, *marks),
    )


def power_flag(library: str, name: str = "PWR_FLAG") -> SymbolDef:
    """The KiCad power flag ``library:name`` carried through Altium (change c0470): flagged ``power``, one
    ``power_out`` pin at the origin, which names no net, a stem along +x and a diamond. Authored for
    Fenolite."""
    half = 635_000
    diamond = (Point(STEM, 0), Point(STEM + half, -half), Point(STEM + 2 * half, 0), Point(STEM + half, half),
               Point(STEM, 0))  # fmt: skip
    return SymbolDef(
        id=derived_id("sym", "altium-power-flag", f"{library}:{name}"),
        name=name,
        library=library,
        power="global",
        properties={"Reference": "#FLG", "Value": name},
        in_bom=False,
        on_board=False,
        pins=(SymbolPin("1", "pwr", "power_out", Point(0, 0), length=0),),
        graphics=(
            SymbolGraphic("line", (Point(0, 0), Point(STEM, 0)), 254_000),
            SymbolGraphic("line", diamond, 254_000),
        ),
    )


__all__ = ["CHANGED", "STEM", "Pose", "component_symbol", "graphic", "power_flag", "power_symbol"]
