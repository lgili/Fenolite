# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library symbols of the Altium writer: the pins and bodies that a schematic library holds and that the
schematic draws (change c0034, capability altium-schematic-writer, "Library symbols from KiCad symbols"
and "Generic library symbols").

Facts: ``docs/formats/altium/schematic-library.md`` (pin fields, directions, electrical types, edge codes,
Part Zero, and the mapping from a KiCad symbol). Lengths are in mils, relative to the symbol's origin, X
rightwards and Y upwards, as in a library file; every value written lies on the 10-mil grid.

``from_generic`` turns c0032's generic body into a symbol of one part whose origin is the body's top-left
corner. ``from_symbol_def`` maps a resolved ``SymbolDef``: its pins exactly, and its own graphics
(``SymbolGraphic``, change c0086) when the model can say which part draws them; otherwise one synthesised
rectangle per part.
"""

# evidence: see project, schlib

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.symbols import PIN_LENGTH, PIN_PITCH, GenericSymbol, natural_key
from fenolite.core.errors import Issue, Severity
from fenolite.model.circuit import PinType
from fenolite.model.library import PinShape, SymbolDef, SymbolGraphic, SymbolPin

NM_PER_MIL = 25_400
GRID = 10
"""Library pins lie on the 10-mil grid of the file unit; finer positions would need ``PinFrac``."""
NM_GRID = GRID * NM_PER_MIL
MIN_BODY = 200
"""A part's rectangle is at least 200 mil on each side (a Fenolite choice)."""
EMPTY_PART = (-100, -100, 100, 100)
"""The rectangle of a part without pins, in mils."""
DEFAULT_PREFIX = "U"

RIGHT, UP, LEFT, DOWN = 0, 1, 2, 3
"""Pin directions, from the body end to the hot end (``PINCONGLOMERATE`` bits 0-1)."""
STEPS: Mapping[int, tuple[int, int]] = {RIGHT: (1, 0), UP: (0, 1), LEFT: (-1, 0), DOWN: (0, -1)}
DIRECTION_OF_ROTATION: Mapping[int, int] = {0: LEFT, 90_000_000: DOWN, 180_000_000: RIGHT, 270_000_000: UP}
"""A KiCad pin angle in microdegrees → the Altium direction (the reverse of KiCad's importer)."""
HIDDEN, NAME_SHOWN, NUMBER_SHOWN = 0x04, 0x08, 0x10

PASSIVE = 4
POWER = 7
ELECTRICAL: Mapping[str, int] = {
    "input": 0,
    "bidirectional": 1,
    "output": 2,
    "open_collector": 3,
    "passive": PASSIVE,
    "tri_state": 5,
    "open_emitter": 6,
    "power_in": POWER,
    "power_out": POWER,
    "free": PASSIVE,
    "unspecified": PASSIVE,
    "no_connect": PASSIVE,
}
"""KiCad electrical type → Altium ``ELECTRICAL``; the types of ``LOSSY_TYPES`` lose their meaning."""
LOSSY_TYPES = frozenset({"power_out", "free", "unspecified", "no_connect"})

DOT, CLOCK, LOW_IN, LOW_OUT = 1, 3, 4, 17
EDGE_CODES: Mapping[str, tuple[int, int]] = {
    "line": (0, 0),
    "inverted": (0, DOT),
    "clock": (CLOCK, 0),
    "inverted_clock": (CLOCK, DOT),
    "input_low": (0, LOW_IN),
    "output_low": (0, LOW_OUT),
    "clock_low": (CLOCK, LOW_IN),
    "edge_clock_high": (0, 0),
    "non_logic": (0, 0),
}
"""KiCad pin shape → (inner-edge code, outer-edge code); ``LOSSY_SHAPES`` have no Altium equivalent."""
LOSSY_SHAPES = frozenset({"edge_clock_high", "non_logic"})
MAX_TEXT = 255


@dataclass(frozen=True)
class AltiumPin:
    """A pin of a library symbol: its body end (``x``, ``y``), direction and length in mils."""

    designator: str
    name: str
    part: int
    x: int
    y: int
    direction: int
    length: int
    electrical: int = PASSIVE
    name_shown: bool = True
    number_shown: bool = True
    hidden: bool = False
    inner_edge: int = 0
    outer_edge: int = 0

    @property
    def hot_end(self) -> tuple[int, int]:
        """The electrical end: ``length`` away from the body end in the pin's direction."""
        dx, dy = STEPS[self.direction]
        return self.x + dx * self.length, self.y + dy * self.length

    @property
    def conglomerate(self) -> int:
        """``PINCONGLOMERATE``: the direction plus the visibility bits."""
        return (
            self.direction
            | (HIDDEN if self.hidden else 0)
            | (NAME_SHOWN if self.name_shown else 0)
            | (NUMBER_SHOWN if self.number_shown else 0)
        )


@dataclass(frozen=True)
class AltiumRect:
    """The rectangle of part ``part``: bottom-left (``x0``, ``y0``) and top-right (``x1``, ``y1``)."""

    part: int
    x0: int
    y0: int
    x1: int
    y1: int


GRAPHIC_KINDS: tuple[str, ...] = ("circle", "line", "polygon", "rect")
"""The kinds of ``SymbolGraphic`` that have a record: an ellipse of equal radii (record 8), a line (13),
a polygon (7) and a rectangle (14). A symbol with a graphic of another kind keeps its rectangles."""
GraphicKind = Literal["ellipse", "line", "polygon", "rectangle"]
SymbolBodies = Literal["generic", "graphics"]
"""How a resolved symbol is drawn: ``generic`` is one synthesised rectangle per part, ``graphics`` the
symbol's own graphics where the model can give them to a part (change c0086, ``--altium-symbols``)."""
DEFAULT_BODIES: SymbolBodies = "graphics"
"""The default since change c0086 (decision of the maintainer, 2026-10-06). The author reports before
that date covered the ``generic`` form, whose bytes ``tests/data/altium/generic/`` keeps; the graphics
form is unconfirmed in Altium until the report of Part Y (``docs/evidence/altium-schematic.md``)."""
FRAC_PER_UNIT = 100_000
"""A ``_FRAC`` key counts 1/100 000 of a file unit of 10 mil: one step is 2.54 nm."""
NM_PER_UNIT = 10 * NM_PER_MIL


def frac_units(nm: int) -> int:
    """A length in nanometres as a count of 1/100 000 file unit, rounded half up: exact for a multiple
    of 127 nm, and within 1.27 nm otherwise."""
    return (2 * nm * FRAC_PER_UNIT + NM_PER_UNIT) // (2 * NM_PER_UNIT)


def unit_and_frac(nm: int) -> tuple[int, int]:
    """The integer of a length key and of its ``_FRAC`` key for ``nm`` nanometres. The two keep their own
    signs: the length is ``unit × 100 000 + frac`` (``schematic-records.md``, "Units")."""
    total = frac_units(nm)
    unit = abs(total) // FRAC_PER_UNIT * (1 if total >= 0 else -1)
    return unit, total - unit * FRAC_PER_UNIT


@dataclass(frozen=True)
class AltiumGraphic:
    """One graphic of part ``part``, in nanometres, in the symbol's frame (X rightwards, Y upwards): a
    ``line`` from ``points[0]`` to ``points[1]``, a ``rectangle`` from its bottom-left to its top-right
    corner, a closed ``polygon`` through ``points``, or an ``ellipse`` of both radii ``radius`` around
    ``points[0]``. Unlike pins, graphics need no grid: the writers give each coordinate its ``_FRAC`` key.
    ``filled`` keeps the fill as a flag, never as a colour."""

    kind: GraphicKind
    part: int
    points: tuple[tuple[int, int], ...]
    filled: bool = False
    radius: int = 0


@dataclass(frozen=True)
class AltiumSymbol:
    """A library component: ``parts`` parts, pins ordered by part and then by natural designator, one
    rectangle per part, the designator prefix, the comment, the description and the footprint link.

    ``graphics`` (change c0086) are the symbol's own graphics. When it is not empty the writers draw them
    and no rectangle: ``rectangles`` then only bound what each part draws, for the layout and the texts.
    When it is empty the writers draw the rectangles."""

    lib_ref: str
    parts: int
    pins: tuple[AltiumPin, ...]
    rectangles: tuple[AltiumRect, ...]
    prefix: str
    comment: str
    description: str = ""
    footprint: tuple[str, str] | None = None
    graphics: tuple[AltiumGraphic, ...] = ()

    @property
    def drawn(self) -> bool:
        """Whether the symbol is drawn from its own graphics instead of its rectangles."""
        return bool(self.graphics)

    def graphics_of(self, part: int) -> tuple[AltiumGraphic, ...]:
        """The graphics of part ``part``, in order."""
        return tuple(g for g in self.graphics if g.part == part)

    def pins_of(self, part: int) -> tuple[AltiumPin, ...]:
        """The pins drawn on part ``part`` of a placed component: its own and, on part 1, Part Zero's."""
        return tuple(p for p in self.pins if p.part == part or (p.part == 0 and part == 1))

    def rectangle(self, part: int) -> AltiumRect:
        return next(r for r in self.rectangles if r.part == part)

    @property
    def top_left(self) -> tuple[int, int]:
        """Part 1's top-left corner: the designator sits above it."""
        rect = self.rectangle(1)
        return rect.x0, rect.y1


def pin_order(pins: list[AltiumPin]) -> tuple[AltiumPin, ...]:
    """Pins by part, Part Zero first, then by designator in natural order."""
    return tuple(sorted(pins, key=lambda p: (p.part, natural_key(p.designator), p.designator)))


def from_generic(
    body: GenericSymbol, *, lib_ref: str, prefix: str, comment: str, footprint: tuple[str, str] | None
) -> AltiumSymbol:
    """c0032's generic body as a symbol of one part whose origin is the body's top-left corner."""
    pins: list[AltiumPin] = []
    for pin in body.pins:
        y = -PIN_PITCH * (pin.row + 1)
        x, direction = (0, LEFT) if pin.side == "left" else (body.width, RIGHT)
        pins.append(
            AltiumPin(
                designator=pin.designator,
                name=pin.name,
                part=1,
                x=x,
                y=y,
                direction=direction,
                length=PIN_LENGTH,
                electrical=PASSIVE,
                name_shown=pin.name_shown,
            )
        )
    rect = AltiumRect(1, 0, -body.height, body.width, 0)
    return AltiumSymbol(lib_ref, 1, pin_order(pins), (rect,), prefix, comment, "", footprint)


# --- KiCad symbols ----------------------------------------------------------------------------------


def _mils(value: int, what: str) -> int:
    """A length in nanometres as mils on the 10-mil grid; ``ValueError`` naming ``what`` otherwise."""
    if value % NM_GRID:
        raise ValueError(f"{what}: {value} nm is not a multiple of {GRID} mil ({NM_GRID} nm)")
    return value // NM_PER_MIL


def overbar(name: str) -> str:
    """KiCad's ``~{AB}`` overbars as Altium's ``A\\B\\``; other text unchanged."""
    out: list[str] = []
    index = 0
    while index < len(name):
        if name.startswith("~{", index):
            end = name.find("}", index + 2)
            if end != -1:
                out.extend(ch + "\\" for ch in name[index + 2 : end])
                index = end + 1
                continue
        out.append(name[index])
        index += 1
    return "".join(out)


def _issue(code: str, severity: Severity, message: str, where: str) -> Issue:
    return Issue(code, severity, message, where=where)


def map_pin(symbol: SymbolDef, pin: SymbolPin, issues: list[Issue] | None = None) -> AltiumPin:
    """One KiCad pin as an Altium pin: direction from its angle, body end from its hot end and length,
    electrical type and edge codes from the tables (a lossy entry adds an ``altium.pin-lossy`` warning).
    ``ValueError`` names an off-grid pin."""
    where = f"{symbol.lib_id} pin {pin.number}"
    direction = DIRECTION_OF_ROTATION.get(pin.rotation)
    if direction is None:
        raise ValueError(f"{where}: angle {pin.rotation} µdeg is not 0, 90, 180 or 270 degrees")
    hx = _mils(pin.position.x, f"{where} x")
    hy = _mils(pin.position.y, f"{where} y")
    length = _mils(pin.length, f"{where} length")
    dx, dy = STEPS[direction]
    etype: PinType = pin.etype
    shape: PinShape = pin.shape
    if issues is not None and etype in LOSSY_TYPES:
        message = f"{where}: electrical type {etype} has no Altium equivalent and is written as "
        message += "power" if ELECTRICAL[etype] == POWER else "passive"
        issues.append(_issue("altium.pin-lossy", "warning", message, where))
    if issues is not None and shape in LOSSY_SHAPES:
        issues.append(
            _issue("altium.pin-lossy", "warning", f"{where}: shape {shape} is written as a plain line", where)
        )
    inner, outer = EDGE_CODES[shape]
    name = overbar(pin.name)
    return AltiumPin(
        designator=pin.number,
        name=name,
        part=pin.unit,
        x=hx - dx * length,
        y=hy - dy * length,
        direction=direction,
        length=length,
        electrical=ELECTRICAL[etype],
        name_shown=not symbol.pin_names_hidden and pin.name not in ("", "~"),
        number_shown=not symbol.pin_numbers_hidden,
        hidden=pin.hidden,
        inner_edge=inner,
        outer_edge=outer,
    )


def _grow(low: int, high: int) -> tuple[int, int]:
    """``low`` … ``high`` grown to at least ``MIN_BODY`` around its centre, rounded outwards to 10 mil."""
    if high - low < MIN_BODY:
        centre2 = low + high
        low2, high2 = centre2 - MIN_BODY, centre2 + MIN_BODY
        low, high = low2 // 2, -(-high2 // 2)
    return (low // GRID) * GRID, -(-high // GRID) * GRID


def body_rectangle(part: int, pins: tuple[AltiumPin, ...]) -> AltiumRect:
    """The bounding box of the body ends of ``pins``, at least 200 mil per side, on the 10-mil grid."""
    if not pins:
        return AltiumRect(part, *EMPTY_PART)
    x0, x1 = _grow(min(p.x for p in pins), max(p.x for p in pins))
    y0, y1 = _grow(min(p.y for p in pins), max(p.y for p in pins))
    return AltiumRect(part, x0, y0, x1, y1)


def map_graphic(graphic: SymbolGraphic, part: int = 1) -> AltiumGraphic:
    """One model graphic as an Altium graphic of ``part``, its coordinates unchanged. A circle becomes an
    ellipse of two equal radii: the distance from its centre to the point beside it on its rim.
    ``ValueError`` for a kind outside ``GRAPHIC_KINDS`` or a graphic with too few points."""
    points = [(point.x, point.y) for point in graphic.points]
    need = 3 if graphic.kind == "polygon" else 2
    if graphic.kind not in GRAPHIC_KINDS or len(points) < need:
        raise ValueError(
            f"a symbol graphic of kind {graphic.kind!r} with {len(points)} point(s) has no record"
        )
    if graphic.kind == "line":
        return AltiumGraphic("line", part, (points[0], points[1]))
    if graphic.kind == "rect":
        (ax, ay), (bx, by) = points[0], points[1]
        corners = ((min(ax, bx), min(ay, by)), (max(ax, bx), max(ay, by)))
        return AltiumGraphic("rectangle", part, corners, graphic.filled)
    if graphic.kind == "circle":
        (cx, cy), (rx, ry) = points[0], points[1]
        # the model puts the rim point beside the centre, on one axis, so this is the radius
        return AltiumGraphic("ellipse", part, (points[0],), graphic.filled, abs(rx - cx) + abs(ry - cy))
    return AltiumGraphic("polygon", part, tuple(points), graphic.filled)


def graphic_box(graphic: AltiumGraphic) -> tuple[int, int, int, int]:
    """The box ``(x0, y0, x1, y1)`` of what ``graphic`` draws, in nanometres."""
    xs = [x for x, _ in graphic.points]
    ys = [y for _, y in graphic.points]
    reach = graphic.radius
    return min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach


def drawn_rectangle(part: int, pins: Sequence[AltiumPin], graphics: Sequence[AltiumGraphic]) -> AltiumRect:
    """The box of the graphics of a part and of the body ends of its pins, in mils, rounded outwards to
    the 10-mil grid: what a drawn part covers, for the layout and for the place of its texts."""
    boxes = [graphic_box(g) for g in graphics]
    low = [(min(b[k] for b in boxes) // NM_GRID) * GRID for k in (0, 1)]
    high = [-(-max(b[k] for b in boxes) // NM_GRID) * GRID for k in (2, 3)]
    return AltiumRect(
        part,
        min([low[0], *(p.x for p in pins)]),
        min([low[1], *(p.y for p in pins)]),
        max([high[0], *(p.x for p in pins)]),
        max([high[1], *(p.y for p in pins)]),
    )


def from_symbol_def(
    symbol: SymbolDef,
    *,
    lib_ref: str,
    footprint: tuple[str, str] | None,
    issues: list[Issue] | None = None,
    unmodelled: Sequence[str] = (),
    bodies: SymbolBodies = DEFAULT_BODIES,
) -> AltiumSymbol:
    """A resolved symbol as an Altium symbol (design Decisions 6 and 7 of change c0034, Decision 1 of
    change c0086).

    Body style 1 and common pins are kept; other body styles and pin alternates are dropped. With
    ``bodies="generic"`` (the bytes of changes c0034 to c0083) every part is one synthesised
    rectangle, and the info says so. With ``bodies="graphics"`` (the default) the symbol's
    graphics are drawn when it has one unit and one body style, holds at least one graphic, every graphic
    is of a kind of ``GRAPHIC_KINDS`` and ``unmodelled`` is empty: ``SymbolGraphic`` names neither a unit
    nor a body style, so the graphics of a symbol of several cannot be given to a part. ``unmodelled``
    names the graphic kinds of the library symbol that the model does not hold (an arc, a Bezier curve, a
    text), which the caller knows. Any other symbol gets one synthesised rectangle per part. Graphics keep
    their coordinates: only pins need the 10-mil grid. One ``altium.symbol-simplified`` info per symbol
    says what was dropped or simplified; a symbol drawn from its graphics with every pin kept gives none.
    ``ValueError`` for an off-grid pin, naming it.
    """
    kept = [p for p in symbol.pins if p.body_style in (0, 1)]
    dropped = len(symbol.pins) - len(kept)
    alternates = sum(1 for p in kept if p.alternates)
    pins = pin_order([map_pin(symbol, p, issues) for p in kept])
    parts = symbol.unit_count
    notes: list[str] = []
    graphics: tuple[AltiumGraphic, ...] = ()
    other = sorted({g.kind for g in symbol.graphics if g.kind not in GRAPHIC_KINDS} | set(unmodelled))
    if bodies not in ("generic", "graphics"):
        raise ValueError(f"unknown symbol bodies {bodies!r}")
    if bodies == "generic":
        notes.append("its graphics became one rectangle per part")
    elif other:
        notes.append(f"its graphics of kind {', '.join(other)} have no record, so each part is a rectangle")
    elif not symbol.graphics:
        notes.append("it holds no graphics, so each part is a rectangle")
    elif parts > 1 or symbol.body_style_count > 1:
        notes.append(
            "the model does not say which unit or body style draws a graphic, so each part is a rectangle"
        )
    else:
        graphics = tuple(map_graphic(graphic) for graphic in symbol.graphics)
    if graphics:
        rectangles: tuple[AltiumRect, ...] = (drawn_rectangle(1, pins, graphics),)
    else:
        rectangles = tuple(
            body_rectangle(k, tuple(p for p in pins if p.part in (0, k))) for k in range(1, parts + 1)
        )
    if dropped:
        notes.append(f"{dropped} pin(s) of other body styles were dropped")
    if alternates:
        notes.append(f"the alternates of {alternates} pin(s) were dropped")
    if issues is not None and notes:
        issues.append(
            _issue("altium.symbol-simplified", "info", f"{symbol.lib_id}: {'; '.join(notes)}", lib_ref)
        )
    prefix = symbol.reference or DEFAULT_PREFIX
    return AltiumSymbol(
        lib_ref=lib_ref,
        parts=parts,
        pins=pins,
        rectangles=rectangles,
        prefix=prefix,
        comment=symbol.value or symbol.name,
        description=symbol.description,
        footprint=footprint,
        graphics=graphics,
    )


__all__ = [
    "EDGE_CODES",
    "ELECTRICAL",
    "DEFAULT_BODIES",
    "GRAPHIC_KINDS",
    "SymbolBodies",
    "LOSSY_SHAPES",
    "LOSSY_TYPES",
    "AltiumGraphic",
    "AltiumPin",
    "AltiumRect",
    "AltiumSymbol",
    "body_rectangle",
    "drawn_rectangle",
    "frac_units",
    "from_generic",
    "from_symbol_def",
    "graphic_box",
    "unit_and_frac",
    "map_graphic",
    "map_pin",
    "overbar",
    "pin_order",
]
