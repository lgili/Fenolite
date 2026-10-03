# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Units, framing and primitive records shared by the Altium PCB library and PCB document (change c0035,
capability altium-pcb-writer, "PCB units and record framing", "PCB layer map", "Footprint pad records" and
"Footprint line and arc records").

Written from ``docs/formats/altium/pcb-records.md`` only. Lengths are signed 32-bit integers in
1/10 000 mil (2.54 nm): ``to_units`` rounds ``nm · 50 / 127`` half away from zero. Angles are doubles in
degrees, counter-clockwise with Y up, computed with ``decimal`` and converted to a double once, so the
bytes do not depend on the platform's C library. Every record is its type byte, then subrecords of a 32-bit
length and their bytes.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from types import MappingProxyType

from fenolite.backends.altium.ascii import Field, text_problem
from fenolite.backends.altium.binary import frame_record
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level

UNITS_PER_MIL = 10_000
"""One binary unit is 1/10 000 mil, exactly 2.54 nm."""
_INT32 = (-(2**31), 2**31 - 1)
MAX_PAYLOAD = 0xFFFFFF
"""The longest property block: its length lies in the low 24 bits of the length word."""
NO_INDEX = 0xFFFF
"""A net, polygon or component index that names nothing."""
FLAGS = (0x0C, 0x00)
"""The two flag bytes of every primitive: unlocked (bit 2) and bit 3, as the MIT writer writes."""
TRACK = 4
ARC = 1
PAD = 2
TEXT = 5
TRACK_SIZE = 36
ARC_SIZE = 47
MULTI_LAYER = 74
"""The layer of every through-hole pad."""

LAYER_MAP: Mapping[str, int] = MappingProxyType(
    {
        "F.Cu": 1,
        "B.Cu": 32,
        "F.SilkS": 33,
        "B.SilkS": 34,
        "F.Fab": 69,
        "B.Fab": 70,
        "F.CrtYd": 71,
        "B.CrtYd": 72,
    }
)
"""Fenolite layer → Altium layer id; the mechanical choices (13 to 16) are Fenolite's."""
FLIP_PAIRS: Mapping[int, int] = MappingProxyType(
    {1: 32, 32: 1, 33: 34, 34: 33, 69: 70, 70: 69, 71: 72, 72: 71, MULTI_LAYER: MULTI_LAYER}
)
"""Each mapped id and its other-side id; Multi-Layer is its own pair."""


def _layer_names() -> dict[int, str]:
    names = {1: "Top Layer", 32: "Bottom Layer"}
    names.update({i: f"Mid-Layer {i - 1}" for i in range(2, 32)})
    names.update(
        {
            33: "Top Overlay",
            34: "Bottom Overlay",
            35: "Top Paste",
            36: "Bottom Paste",
            37: "Top Solder",
            38: "Bottom Solder",
        }
    )
    names.update({i: f"Internal Plane {i - 38}" for i in range(39, 55)})
    names.update({55: "Drill Guide", 56: "Keep-Out Layer"})
    names.update({i: f"Mechanical {i - 56}" for i in range(57, 73)})
    names.update({73: "Drill Drawing", 74: "Multi-Layer"})
    return dict(sorted(names.items()))


LAYER_NAMES: Mapping[int, str] = MappingProxyType(_layer_names())
"""Altium layer id → its name, ids 1 to 74."""

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PCB-DOC-BOTTOM",
        "H-A-PCB-DOC-LINK",
        "H-A-PCB-DOC-NETS",
        "H-A-PCB-DOC-OPEN",
        "H-A-PCB-DOC-VIEWER",
        "H-A-PCB-ECO",
        "H-A-PCB-GRAPHICS",
        "H-A-PCB-KICAD-DOC",
        "H-A-PCB-KICAD-LIB",
        "H-A-PCB-LIB-NAME",
        "H-A-PCB-LIB-OPEN",
        "H-A-PCB-PAD",
        "H-A-PCB-PRJ",
    ),
)
"""The PCB records are inferred from public sources; the kicad-cli oracles check only what KiCad reads."""

_DIGITS = 40
EMPTY_PROPERTY_BLOCK = struct.pack("<I", 1) + b"\0"
"""A property block without fields: the length word and the NUL alone."""


def _round_away(value: Fraction | Decimal) -> int:
    """``value`` rounded to an integer, halves away from zero."""
    exact = Fraction(value)
    whole, rest = divmod(abs(exact.numerator), exact.denominator)
    if 2 * rest >= exact.denominator:
        whole += 1
    return -whole if exact < 0 else whole


def to_units(nm: int | Fraction | Decimal) -> int:
    """A length in nanometres as binary units (``nm · 50 / 127``), rounded half away from zero, as an int32;
    ``ValueError`` outside the int32 range."""
    units = _round_away(Fraction(nm) * 50 / 127)
    if not _INT32[0] <= units <= _INT32[1]:
        raise ValueError(f"{nm} nm gives {units} units, outside the signed 32-bit range")
    return units


def mil_text(units: int) -> str:
    """Units as mil text: at most four decimals, trailing zeros and point removed, then ``mil``."""
    whole, rest = divmod(abs(units), UNITS_PER_MIL)
    fraction = f"{rest:04d}".rstrip("0")
    sign = "-" if units < 0 else ""
    return f"{sign}{whole}{'.' + fraction if fraction else ''}mil"


def string_block(text: str) -> bytes:
    """A 32-bit length, one length byte and the 7-bit ASCII ``text``; ``ValueError`` when ``text`` cannot be
    written or is longer than 255 bytes."""
    problem = text_problem(text)
    if problem is not None:
        raise ValueError(f"the text {text!r} {problem}")
    data = text.encode("ascii")
    if len(data) > 255:
        raise ValueError(f"the text {text[:20]!r}… holds {len(data)} bytes, more than 255")
    return struct.pack("<IB", len(data) + 1, len(data)) + data


def short_string(text: str) -> bytes:
    """One length byte and the 7-bit ASCII ``text`` (the content of a pad-name or text subrecord)."""
    return string_block(text)[4:]


def property_block(fields: Sequence[Field]) -> bytes:
    """One property block: c0033's ``binary.frame_record``."""
    return frame_record(fields)


def text_block(text: str) -> bytes:
    """A property block from its text (``|KEY=VALUE…``, which may hold CR between lines): the 32-bit
    length, the 7-bit ASCII text and the NUL; ``ValueError`` past the 24 bits of the length."""
    payload = text.encode("ascii") + b"\0"
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"a property block of {len(payload)} bytes is over {MAX_PAYLOAD} bytes")
    return struct.pack("<I", len(payload)) + payload


def subrecord(data: bytes) -> bytes:
    """A 32-bit length and ``data``."""
    return struct.pack("<I", len(data)) + data


def prefix(layer: int, *, net: int = NO_INDEX, component: int = NO_INDEX) -> bytes:
    """The common 13 bytes: layer, the two flag bytes, net, polygon (none), component and ``FF FF FF FF``."""
    if not 0 < layer < 256:
        raise ValueError(f"layer id {layer} is not one byte")
    return struct.pack("<BBBHHH", layer, *FLAGS, net, NO_INDEX, component) + b"\xff" * 4


def _decimal(value: int | Fraction) -> Decimal:
    exact = Fraction(value)
    return Decimal(exact.numerator) / Decimal(exact.denominator)


def _atan_series(x: Decimal) -> Decimal:
    """``atan(x)`` for ``|x| ≤ 0.2`` by its Taylor series, to the context's precision."""
    total, power, n = Decimal(0), x, 0
    square = x * x
    epsilon = Decimal(10) ** -(_DIGITS + 5)
    while True:
        term = power / (2 * n + 1)
        if abs(term) < epsilon:
            return total
        total += -term if n % 2 else term
        power *= square
        n += 1


def _pi() -> Decimal:
    """Machin's formula: ``16·atan(1/5) − 4·atan(1/239)``."""
    return 16 * _atan_series(Decimal(1) / 5) - 4 * _atan_series(Decimal(1) / 239)


def _atan(x: Decimal) -> Decimal:
    if x < 0:
        return -_atan(-x)
    if x > 1:
        return _pi() / 2 - _atan(1 / x)
    halvings = 0
    while x > Decimal("0.2"):
        x = x / (1 + (1 + x * x).sqrt())
        halvings += 1
    return _atan_series(x) * (2**halvings)


def angle_degrees(dx: int | Fraction, dy: int | Fraction) -> float:
    """The direction of the vector ``(dx, dy)`` (Y up) in degrees in ``[0, 360)``, computed with ``decimal``
    and converted to a double once."""
    if dx == 0 and dy == 0:
        raise ValueError("a zero vector has no direction")
    with localcontext(Context(prec=_DIGITS + 10, rounding=ROUND_HALF_EVEN)):
        x, y = _decimal(dx), _decimal(dy)
        pi = _pi()
        if x == 0:
            angle = pi / 2 if y > 0 else 3 * pi / 2
        else:
            angle = _atan(y / x)
            if x < 0:
                angle += pi
            elif y < 0:
                angle += 2 * pi
        degrees = angle * 180 / pi
        if degrees >= 360:
            degrees -= 360
        with localcontext(Context(prec=_DIGITS, rounding=ROUND_HALF_EVEN)):
            degrees = +degrees
    return float(degrees)


def degrees_of(udeg: int) -> float:
    """Microdegrees as a double in degrees (exact through ``decimal``)."""
    return float(Decimal(udeg) / Decimal(1_000_000))


@dataclass(frozen=True, slots=True)
class ArcGeometry:
    """An arc in binary units: centre, radius, start and end angle (degrees, counter-clockwise)."""

    cx: int
    cy: int
    radius: int
    start: float
    end: float


def arc_from_points(start: Point, mid: Point, end: Point) -> ArcGeometry:
    """The arc through three points given in nanometres in the Y-up frame: the exact centre rounded once,
    the radius, and angles running counter-clockwise from start to end (start and end swap when the points
    turn clockwise); ``ValueError`` for collinear or repeated points."""
    bx, by = mid.x - start.x, mid.y - start.y
    cx, cy = end.x - start.x, end.y - start.y
    orient = bx * cy - by * cx
    if orient == 0:
        raise ValueError(f"the arc points {start}, {mid} and {end} are collinear")
    b2, c2 = bx * bx + by * by, cx * cx + cy * cy
    ux = Fraction(cy * b2 - by * c2, 2 * orient)
    uy = Fraction(bx * c2 - cx * b2, 2 * orient)
    centre_x, centre_y = start.x + ux, start.y + uy
    with localcontext(Context(prec=_DIGITS, rounding=ROUND_HALF_EVEN)):
        radius_nm = _decimal(ux * ux + uy * uy).sqrt()
    first, last = (start, end) if orient > 0 else (end, start)
    return ArcGeometry(
        cx=to_units(centre_x),
        cy=to_units(centre_y),
        radius=to_units(radius_nm),
        start=angle_degrees(first.x - centre_x, first.y - centre_y),
        end=angle_degrees(last.x - centre_x, last.y - centre_y),
    )


def circle_geometry(centre: Point, on_circle: Point) -> ArcGeometry:
    """A full circle (0 to 360 degrees) through ``on_circle``, both points in nanometres."""
    dx, dy = on_circle.x - centre.x, on_circle.y - centre.y
    if dx == 0 and dy == 0:
        raise ValueError(f"the circle at {centre} has no radius")
    with localcontext(Context(prec=_DIGITS, rounding=ROUND_HALF_EVEN)):
        radius_nm = Decimal(dx * dx + dy * dy).sqrt()
    return ArcGeometry(to_units(centre.x), to_units(centre.y), to_units(radius_nm), 0.0, 360.0)


def track_record(
    layer: int,
    a: tuple[int, int],
    b: tuple[int, int],
    width: int,
    *,
    net: int = NO_INDEX,
    component: int = NO_INDEX,
) -> bytes:
    """A track (type 4): one subrecord of 36 bytes; points and width in binary units."""
    body = prefix(layer, net=net, component=component) + struct.pack("<5iHB", *a, *b, width, 0, 0)
    assert len(body) == TRACK_SIZE
    return bytes((TRACK,)) + subrecord(body)


def arc_record(
    layer: int, arc: ArcGeometry, width: int, *, net: int = NO_INDEX, component: int = NO_INDEX
) -> bytes:
    """An arc (type 1): one subrecord of 47 bytes."""
    body = prefix(layer, net=net, component=component) + struct.pack(
        "<3iddiH", arc.cx, arc.cy, arc.radius, arc.start, arc.end, width, 0
    )
    assert len(body) == ARC_SIZE
    return bytes((ARC,)) + subrecord(body)


PAD_SHAPES: Mapping[str, int] = MappingProxyType({"circle": 1, "oval": 1, "rect": 2, "roundrect": 1})
"""Fenolite pad shape → Altium main shape: an oval is round with unequal sizes; a rounded rectangle is round
with alternate shape 9 in subrecord 6."""
ROUNDED_ALTERNATE = 9
PAD_GEOMETRY_SIZE = 114
PAD_LAYERS_SIZE = 596
_INNER = 29
_STACK = 32
_V1_DEFAULTS = (0, 0, 100_000, 4, 100_000, 200_000, 200_000)
"""The values AltiumSharp version 1 writes at pad offsets 63 to 85 (``pcb-records.md``)."""
SOLDER_FROM_RULES = 1
PAD_SUBRECORD_3 = b"\x04|&|0"
"""What version 1 writes in pad subrecord 3: one length byte and ``|&|0``."""


def corner_percent(ratio: Fraction | Decimal) -> int:
    """KiCad's corner ratio as Altium's corner percentage ``round(200 · ratio)``, clamped to 0 … 100."""
    return max(0, min(100, _round_away(Fraction(ratio) * 200)))


def pad_record(
    *,
    name: str,
    layer: int,
    x: int,
    y: int,
    size: tuple[int, int],
    shape: int,
    rotation: float,
    hole: int = 0,
    plated: bool = False,
    corner: int | None = None,
    net: int = NO_INDEX,
    component: int = NO_INDEX,
) -> bytes:
    """A pad (type 2): six subrecords. Lengths in binary units, ``rotation`` in degrees; ``corner`` is the
    corner percentage of a rounded rectangle, which adds the 596-byte subrecord 6."""
    w, h = size
    geometry = prefix(layer, net=net, component=component)
    geometry += struct.pack("<2i6ii3Bd3B", x, y, w, h, w, h, w, h, hole, shape, shape, shape, rotation,
                            1 if plated else 0, 0, 0)  # fmt: skip
    geometry += struct.pack("<Biihiii", *_V1_DEFAULTS)
    geometry += struct.pack("<2i", 0, 0) + bytes(7) + struct.pack("<2B", 0, SOLDER_FROM_RULES) + bytes(3)
    geometry += struct.pack("<iHh", 0, 0, 0)
    assert len(geometry) == PAD_GEOMETRY_SIZE
    layers = b""
    if corner is not None:
        if not 0 <= corner <= 100:
            raise ValueError(f"corner percentage {corner} is outside 0 … 100")
        layers = struct.pack(f"<{_INNER}i", *[w] * _INNER) + struct.pack(f"<{_INNER}i", *[h] * _INNER)
        layers += bytes([shape] * _INNER) + bytes(2) + struct.pack("<id", 0, 0.0)
        layers += bytes(8 * _STACK) + b"\x01" + bytes([ROUNDED_ALTERNATE] * _STACK) + bytes([corner] * _STACK)
        assert len(layers) == PAD_LAYERS_SIZE
    parts = (short_string(name), b"\0", PAD_SUBRECORD_3, b"\0", geometry, layers)
    return bytes((PAD,)) + b"".join(subrecord(part) for part in parts)


__all__ = [
    "ARC",
    "ARC_SIZE",
    "EMPTY_PROPERTY_BLOCK",
    "EVIDENCE",
    "FLIP_PAIRS",
    "LAYER_MAP",
    "LAYER_NAMES",
    "MULTI_LAYER",
    "NO_INDEX",
    "PAD",
    "PAD_GEOMETRY_SIZE",
    "PAD_LAYERS_SIZE",
    "PAD_SHAPES",
    "ROUNDED_ALTERNATE",
    "TEXT",
    "TRACK",
    "TRACK_SIZE",
    "ArcGeometry",
    "angle_degrees",
    "arc_from_points",
    "arc_record",
    "circle_geometry",
    "corner_percent",
    "degrees_of",
    "mil_text",
    "pad_record",
    "prefix",
    "property_block",
    "short_string",
    "string_block",
    "subrecord",
    "text_block",
    "to_units",
    "track_record",
]
