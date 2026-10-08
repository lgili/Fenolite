# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Room for the pin texts of a symbol (change c0134; capability fenolite-component-catalog, "Legible pin
texts").

``findings(symbol)`` estimates, for each unit of a symbol and at two text sizes, the box of every pin name
and pin number that the symbol shows, and lists what makes a text hard to read:

- ``REPEAT``: a shown name is the pin's own number again;
- ``UNCHECKED``: a shown text holds a character whose box was not compared with a drawing;
- ``OVERLAP``: the boxes of two shown texts overlap;
- ``OUTSIDE``: the box of a name that is drawn inside the body leaves the box of the body;
- ``STROKE``: a stroke of the body, or the stem of another pin, crosses the box of a name or of a number;
- ``MARK``: the mark of a pin's shape (an inversion bubble, a clock wedge, a low-level mark) crosses the
  box of a name or of a number, of that pin or of another.

The boxes are estimates in integer nanometres. Each size follows the text that one of Fenolite's writers
asks for and the place where its tool draws it:

- ``KICAD``: text 1.27 mm high, the size ``backends/kicad/sym.py`` writes and every authored library
  holds. A name starts at the symbol's name offset (0.508 mm when it has none) past the body end of its
  pin and runs on along the pin; a number is centred on the middle of its pin, from 0.36 mm clear of the
  pin line (above a horizontal pin, left of a vertical one). A character counts 1.15 text heights, and
  a line is 1.6 mm thick: the glyphs, their pen and their shift off the axis. An overbar adds 0.5 mm on
  the side the tops of the letters point to.
- ``ALTIUM``: the 10-point sheet font of ``backends/altium/schlib.py``, for which ``layout.TEXT_HEIGHT``
  keeps a line of 100 mil. The box is 90 mil thick, so names on rows 100 mil apart do not touch. A name
  starts 50 mil inside the body end of its pin and runs on along the pin; a number starts 80 mil outside
  it, 10 mil clear of the pin line. A character counts 100 mil, the height of the line: 1.43 times the
  70 mil that ``symbols.CHAR_WIDTH`` estimates. An overbar adds nothing.

How far each size is known (design of change c0134, "Estimate"):

- The KiCad size was compared with the glyph strokes that ``kicad-cli`` 10.0.6 draws (``sch export svg``
  of every catalog symbol and of the example library, each placed alone, 2026-10-07): every stroke of
  every pin text lies inside its box with half the pen of 0.15 mm to spare. A string draws at most 0.92
  heights per character, and one digit 1.05. That holds for the characters of ``CHECKED``, the ones the
  authored names and numbers are written with, and for no other: two names of four ``@`` and four ``%``
  whose boxes just meet are drawn into each other, and the descenders of lower-case letters leave the
  box on the side away from the letter tops (``kicad-cli`` 10.0.6, 2026-10-07). ``unchecked`` lists the
  shown texts of a symbol that hold another character; the test lets none pass.
- The marks of the pin shapes are the strokes ``kicad-cli`` 10.0.6 draws for each of the nine shapes at
  each of the four pin angles (``sym export svg``, 2026-10-07): a circle of 1.27 mm outside the body end,
  a wedge 1.27 mm deep and 1.27 mm wide inside it, and marks of 1.27 mm above a level pin or left of an
  upright one. ``pin_marks`` holds them; the pen of 0.15 mm is not counted.
- Nothing of the Altium size was measured in Altium. The two margins, the thickness and the width are
  assumptions, and the width is the larger of two estimates on purpose. The marks of the pin shapes
  are taken as KiCad draws them; what the Altium writer's inner and outer edge codes draw is not known.

A hidden pin draws nothing. A name ``""`` draws nothing; a name ``~`` is a tilde for KiCad 10 and is not
written as shown by the Altium writer. An overbar group ``~{AB}`` draws ``AB``. The model does not say
which unit draws a graphic, so the strokes of all units are taken together, and a unit is judged
against strokes that another unit may draw. Only body style 1 is measured: an alternate body style
passes unmeasured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolPin

Box = tuple[int, int, int, int]
"""``(x0, y0, x1, y1)`` in nanometres, in the symbol's frame (Y upwards)."""
Segment = tuple[tuple[int, int], tuple[int, int]]

MIL = 25_400
EPS = 50_000
"""Two boxes that share less than 0.05 mm do not overlap; a stroke that enters a box by less does not
cross it."""
DEFAULT_NAME_OFFSET = 508_000
"""The name offset ``write_symbol_library`` writes, and KiCad's own when a symbol states none."""
BODY_MARGIN = 1_270_000
"""``write_symbol_library`` draws a symbol without graphics as the box of its pins' ends plus this."""
STEPS = {0: (1, 0), 90_000_000: (0, 1), 180_000_000: (-1, 0), 270_000_000: (0, -1)}
"""A pin's angle → the step from its connection point towards its body end."""
_OVERBAR = re.compile(r"~\{([^}]*)\}")
CHECKED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-_~")
"""The characters whose KiCad-size box was compared with what ``kicad-cli`` draws."""
MARK = 1_270_000
"""The size of KiCad's pin shape marks: the diameter of the bubble, the depth and width of the wedge."""
Circle = tuple[int, int, int]
"""``(centre x, centre y, radius squared)``."""


@dataclass(frozen=True)
class TextSize:
    """Where and how large one tool draws pin texts: ``height`` is the nominal text height, ``thick`` the
    thickness of the box of a line, ``char`` the width of a character. ``name_offset`` ``None`` takes the
    symbol's own offset; ``number_start`` ``None`` centres a number on its pin, a value starts it that
    far outside the body end; ``lift`` is the gap between the pin line and a text beside it."""

    label: str
    height: int
    thick: int
    char: int
    name_offset: int | None
    number_start: int | None
    lift: int
    overbar: int
    tilde_drawn: bool


KICAD = TextSize(
    "KiCad size",
    height=1_270_000,
    thick=1_600_000,
    char=1_460_500,
    name_offset=None,
    number_start=None,
    lift=360_000,
    overbar=500_000,
    tilde_drawn=True,
)
ALTIUM = TextSize(
    "Altium size",
    height=100 * MIL,
    thick=90 * MIL,
    char=100 * MIL,
    name_offset=50 * MIL,
    number_start=80 * MIL,
    lift=10 * MIL,
    overbar=0,
    tilde_drawn=False,
)
SIZES = (KICAD, ALTIUM)


@dataclass(frozen=True)
class Shown:
    """One text a unit shows: ``kind`` is ``name`` or ``number``; ``pin`` is the number of its pin and
    ``at`` that pin's connection point; ``inside`` says that it is a name drawn inside the body, past the
    body end of its pin."""

    kind: str
    pin: str
    text: str
    box: Box
    at: tuple[int, int]
    inside: bool = False

    def __str__(self) -> str:
        return f"{self.kind} {self.text!r} of pin {self.pin}"


def drawn(name: str) -> str:
    """The characters a pin name draws."""
    return _OVERBAR.sub(r"\1", name)


def body_end(pin: SymbolPin) -> tuple[int, int]:
    dx, dy = STEPS[pin.rotation]
    return pin.position.x + dx * pin.length, pin.position.y + dy * pin.length


def _along(ax: int, ay: int, dx: int, dy: int, length: int, half: int) -> Box:
    """The box of a text line that starts at (``ax``, ``ay``) and runs ``length`` in the step's
    direction, ``half`` to each side."""
    bx, by = ax + dx * length, ay + dy * length
    if dx:
        return (min(ax, bx), ay - half, max(ax, bx), ay + half)
    return (ax - half, min(ay, by), ax + half, max(ay, by))


def _beside(mx: int, my: int, dx: int, width: int, near: int, far: int) -> Box:
    """A box ``width`` long centred on (``mx``, ``my``) along the pin, from ``near`` to ``far`` away from
    the pin line: upwards for a horizontal pin, leftwards for a vertical one (negative values the other
    way)."""
    low, high = min(near, far), max(near, far)
    if dx:
        return (mx - width // 2, my + low, mx + width // 2, my + high)
    return (mx - high, my - width // 2, mx - low, my + width // 2)


def shown_texts(symbol: SymbolDef, unit: int, size: TextSize) -> list[Shown]:
    """The names and numbers that unit ``unit`` of ``symbol`` shows in body style 1, with their boxes."""
    offset = size.name_offset
    if offset is None:
        offset = DEFAULT_NAME_OFFSET if symbol.pin_name_offset is None else symbol.pin_name_offset
    found: list[Shown] = []
    for pin in symbol.pins_of(unit, 1):
        if pin.hidden:
            continue
        dx, dy = STEPS[pin.rotation]
        at = (pin.position.x, pin.position.y)
        ix, iy = body_end(pin)
        mx, my = at[0] + dx * (pin.length // 2), at[1] + dy * (pin.length // 2)
        name = drawn(pin.name)
        name_shown = not symbol.pin_names_hidden and name != "" and (size.tilde_drawn or name != "~")
        number_shown = not symbol.pin_numbers_hidden and pin.number != ""
        outside = offset == 0 and name_shown  # KiCad: the name above the pin, the number below it
        if name_shown:
            width = len(name) * size.char
            if outside:
                box = _beside(mx, my, dx, width, size.lift, size.lift + size.thick)
            else:
                box = _along(ix + dx * offset, iy + dy * offset, dx, dy, width, size.thick // 2)
            if name != pin.name:  # an overbar: above a level name, left of an upright one
                bar = size.overbar
                box = (box[0], box[1], box[2], box[3] + bar) if dx else (box[0] - bar, *box[1:])
            found.append(Shown("name", pin.number, name, box, at, not outside))
        if number_shown:
            width = len(pin.number) * size.char
            if size.number_start is None:
                near, far = size.lift, size.lift + size.thick
                box = _beside(mx, my, dx, width, -near if outside else near, -far if outside else far)
            else:
                ax, ay = ix - dx * size.number_start, iy - dy * size.number_start
                run = _along(ax, ay, -dx, -dy, width, 0)
                if dx:
                    box = (run[0], iy + size.lift, run[2], iy + size.lift + size.thick)
                else:
                    box = (ix - size.lift - size.thick, run[1], ix - size.lift, run[3])
            found.append(Shown("number", pin.number, pin.number, box, at))
    return found


def pin_marks(pin: SymbolPin) -> tuple[list[Segment], list[Circle]]:
    """The strokes and circles KiCad draws at the body end of ``pin`` for its shape. ``along`` runs from
    the body end into the body; ``side`` is the side the marks of the low-level shapes lie on, which is
    the side of the pin's number: above a level pin, left of an upright one."""
    dx, dy = STEPS[pin.rotation]
    ix, iy = body_end(pin)
    sx, sy = (0, 1) if dx else (-1, 0)
    half = MARK // 2

    def at(along: int, side: int) -> tuple[int, int]:
        return ix + dx * along + sx * side, iy + dy * along + sy * side

    def path(*points: tuple[int, int]) -> list[Segment]:
        return [(at(*a), at(*b)) for a, b in zip(points, points[1:], strict=False)]

    bubble = [(*at(-half, 0), half * half)]
    wedge = path((0, -half), (MARK, 0), (0, half))
    low = path((-MARK, 0), (-MARK, MARK), (0, 0))
    shapes: dict[str, tuple[list[Segment], list[Circle]]] = {
        "line": ([], []),
        "inverted": ([], bubble),
        "clock": (wedge, []),
        "inverted_clock": (wedge, bubble),
        "input_low": (low, []),
        "clock_low": (wedge + low, []),
        "output_low": (path((0, MARK), (-MARK, 0)), []),
        "edge_clock_high": (path((0, -half), (-MARK, 0), (0, half)), []),
        "non_logic": (path((half, half), (-half, -half)) + path((half, -half), (-half, half)), []),
    }
    return shapes[pin.shape]


def _radius_squared(graphic: SymbolGraphic) -> int:
    centre, rim = graphic.points[0], graphic.points[1]
    return (rim.x - centre.x) ** 2 + (rim.y - centre.y) ** 2


def body_box(symbol: SymbolDef) -> Box | None:
    """The box of the symbol's graphics; for a symbol without any, the rectangle the KiCad writer draws
    around its pins; ``None`` for a symbol with neither."""
    xs: list[int] = []
    ys: list[int] = []
    for graphic in symbol.graphics:
        if graphic.kind == "circle":
            centre, radius = graphic.points[0], isqrt(_radius_squared(graphic))
            xs += [centre.x - radius, centre.x + radius]
            ys += [centre.y - radius, centre.y + radius]
        else:
            xs += [point.x for point in graphic.points]
            ys += [point.y for point in graphic.points]
    if xs:
        return (min(xs), min(ys), max(xs), max(ys))
    if not symbol.pins:
        return None
    px = [pin.position.x for pin in symbol.pins]
    py = [pin.position.y for pin in symbol.pins]
    return (min(px) - BODY_MARGIN, min(py) - BODY_MARGIN, max(px) + BODY_MARGIN, max(py) + BODY_MARGIN)


def segments(graphic: SymbolGraphic) -> list[Segment]:
    """The straight strokes of a graphic; a circle has none (``crossed_by_circle`` judges it)."""
    points = [(point.x, point.y) for point in graphic.points]
    if graphic.kind == "line":
        return [(points[0], points[1])]
    if graphic.kind == "rect":
        (ax, ay), (bx, by) = points[0], points[1]
        corners = [(ax, ay), (bx, ay), (bx, by), (ax, by)]
        return [(corners[k], corners[(k + 1) % 4]) for k in range(4)]
    if graphic.kind == "polygon":
        return [(points[k], points[(k + 1) % len(points)]) for k in range(len(points))]
    return []


def _inner(box: Box) -> Box | None:
    """``box`` shrunk by ``EPS`` on each side, or ``None`` when nothing is left."""
    x0, y0, x1, y1 = box[0] + EPS, box[1] + EPS, box[2] - EPS, box[3] - EPS
    return (x0, y0, x1, y1) if x0 < x1 and y0 < y1 else None


def crossed_by(segment: Segment, box: Box) -> bool:
    """Whether a stroke passes through ``box`` by more than ``EPS`` (exact, Liang-Barsky clipping)."""
    inner = _inner(box)
    if inner is None:
        return False
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    start, end = Fraction(0), Fraction(1)
    for step, room in ((-dx, x0 - inner[0]), (dx, inner[2] - x0), (-dy, y0 - inner[1]), (dy, inner[3] - y0)):
        if step == 0:
            if room < 0:
                return False
            continue
        at = Fraction(room, step)
        if step < 0:
            start = max(start, at)
        else:
            end = min(end, at)
        if start > end:
            return False
    return True


def crossed_by_circle(graphic: SymbolGraphic, box: Box) -> bool:
    """Whether the outline of a circle passes through ``box`` by more than ``EPS``: the box is neither
    wholly inside the circle nor wholly outside it."""
    centre = graphic.points[0]
    return _ring_crosses((centre.x, centre.y, _radius_squared(graphic)), box)


def _ring_crosses(circle: Circle, box: Box) -> bool:
    inner = _inner(box)
    if inner is None:
        return False
    cx, cy, radius2 = circle
    nearest_x = min(max(cx, inner[0]), inner[2])
    nearest_y = min(max(cy, inner[1]), inner[3])
    nearest = (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2
    farthest = max((x - cx) ** 2 + (y - cy) ** 2 for x in inner[0::2] for y in inner[1::2])
    return nearest <= radius2 <= farthest


def _overlap(a: Box, b: Box) -> tuple[int, int] | None:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return (width, height) if width > EPS and height > EPS else None


def _mm(value: int) -> str:
    return f"{value // 1000 / 1000:.3f} mm"


def judge(symbol: SymbolDef, unit: int, size: TextSize) -> list[str]:
    """What makes a shown pin text of unit ``unit`` hard to read at ``size``."""
    texts = shown_texts(symbol, unit, size)
    body = body_box(symbol)
    found: list[str] = []
    for index, first in enumerate(texts):
        for second in texts[index + 1 :]:
            hit = _overlap(first.box, second.box)
            if hit:
                found.append(f"OVERLAP {first} and {second} by {_mm(hit[0])} x {_mm(hit[1])}")
    visible = [pin for pin in symbol.pins_of(unit, 1) if not pin.hidden]
    marks = [(pin, *pin_marks(pin)) for pin in visible if pin.shape != "line"]
    for text in texts:
        if (
            text.kind == "name"
            and text.inside
            and body is not None
            and not (
                body[0] - EPS <= text.box[0]
                and body[1] - EPS <= text.box[1]
                and text.box[2] <= body[2] + EPS
                and text.box[3] <= body[3] + EPS
            )
        ):
            found.append(f"OUTSIDE {text} leaves the body")
        strokes = sum(crossed_by(seg, text.box) for graphic in symbol.graphics for seg in segments(graphic))
        strokes += sum(crossed_by_circle(g, text.box) for g in symbol.graphics if g.kind == "circle")
        stems = sum(
            crossed_by(((pin.position.x, pin.position.y), body_end(pin)), text.box)
            for pin in visible
            if (pin.position.x, pin.position.y) != text.at
        )
        if strokes or stems:
            found.append(f"STROKE {text} lies over {strokes} body stroke(s) and {stems} pin stem(s)")
        for pin, lines, rings in marks:
            if any(crossed_by(seg, text.box) for seg in lines) or any(
                _ring_crosses(r, text.box) for r in rings
            ):
                found.append(f"MARK {text} lies over the {pin.shape} mark of pin {pin.number}")
    return found


def unchecked(symbol: SymbolDef, unit: int) -> list[str]:
    """The shown texts of unit ``unit`` with a character whose box nothing was compared with."""
    found: list[str] = []
    for text in shown_texts(symbol, unit, KICAD):
        other = "".join(sorted(set(text.text) - CHECKED))
        if other:
            found.append(f"UNCHECKED {text} holds {other!r}, outside the compared characters")
    return found


def repeats(symbol: SymbolDef, unit: int) -> list[str]:
    """The shown names of unit ``unit`` that only repeat the shown number of their own pin."""
    if symbol.pin_names_hidden or symbol.pin_numbers_hidden:
        return []
    return [
        f"REPEAT name {drawn(pin.name)!r} of pin {pin.number} only repeats its number"
        for pin in symbol.pins_of(unit, 1)
        if not pin.hidden and pin.number != "" and drawn(pin.name) == pin.number
    ]


def findings(symbol: SymbolDef) -> list[str]:
    """Every finding of ``symbol``: per unit, the repeated names and the texts with a character that was
    not compared, then what ``judge`` finds at each size."""
    found: list[str] = []
    for unit in range(1, symbol.unit_count + 1):
        found += [f"unit {unit}: {text}" for text in (*repeats(symbol, unit), *unchecked(symbol, unit))]
        for size in SIZES:
            found += [f"unit {unit}, {size.label}: {text}" for text in judge(symbol, unit, size)]
    return found
