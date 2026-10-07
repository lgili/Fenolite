# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Units, framing and primitive records shared by the Altium PCB library and PCB document (change c0035,
capability altium-pcb-writer, "PCB units and record framing", "PCB layer map", "Footprint pad records" and
"Footprint line and arc records"; change c0038, "Copper layer map" and "Via records"; change c0085, "Layer
stacks of any even count", "Blind and buried via records", "Board graphics and keep-out records" and
"Non-plated holes and slots"; change c0121, "Extruded component body records").

Written from ``docs/formats/altium/pcb-records.md``, ``pcb-copper.md`` and, for a component body,
``pcb-bodies.md`` ("Written form of an extruded body") only. Lengths are signed 32-bit
integers in 1/10 000 mil (2.54 nm): ``to_units`` rounds ``nm · 50 / 127`` half away from zero. Angles are
doubles in degrees, counter-clockwise with Y up, computed with ``decimal`` and converted to a double once,
so the bytes do not depend on the platform's C library. Every record is its type byte, then subrecords of a
32-bit length and their bytes.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from types import MappingProxyType
from typing import Literal

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
UNLOCKED_BIT = 0x04
"""Bit 2 of the first flag byte: set on an unlocked primitive, clear on a locked one."""
LOCKED_FLAGS = (FLAGS[0] & ~UNLOCKED_BIT, FLAGS[1])
"""The flag bytes of a locked free track, arc or via: ``08 00`` (``H-A-PCB-CU-LOCK``)."""
LOCK_WRITTEN: frozenset[str] = frozenset({"track", "arc", "via"})
"""The record kinds whose lock is written: those with a row "The locked flag of a free <kind>" in
``docs/formats/altium/pcb-copper.md`` (change c0108, "Locked copper records"). A kind enters this set only
after its row is on the page; a locked item of a kind outside it is written unlocked and the build says so."""
TRACK = 4
ARC = 1
PAD = 2
TEXT = 5
VIA = 3
REGION = 11
BODY = 12
TRACK_SIZE = 36
ARC_SIZE = 47
VIA_SIZE = 321
"""The via subrecord in the form Altium saves (``pcb-copper.md``, "Via")."""
MULTI_LAYER = 74
"""The layer of every through-hole pad."""

LAYER_MAP: Mapping[str, int] = MappingProxyType(
    {
        "F.Cu": 1,
        "In1.Cu": 2,
        "In2.Cu": 3,
        "B.Cu": 32,
        "F.SilkS": 33,
        "B.SilkS": 34,
        "F.Fab": 69,
        "B.Fab": 70,
        "F.CrtYd": 71,
        "B.CrtYd": 72,
    }
)
"""Fenolite layer → Altium layer id; the mechanical choices (13 to 16) are Fenolite's. An inner copper
layer is here as a signal layer (Mid-Layer 1 and 2); a plane has no entry (``copper_stack``)."""
COPPER_LAYER_TEXT: Mapping[str, str] = MappingProxyType(
    {"F.Cu": "TOP", "In1.Cu": "MID1", "In2.Cu": "MID2", "B.Cu": "BOTTOM"}
)
"""Signal copper layer → its ``LAYER`` text in a property record (a polygon pour)."""
COPPER_STACKS: tuple[tuple[str, ...], ...] = (("F.Cu", "B.Cu"), ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
"""The copper stacks a script's layer count gives (2 and 4), top to bottom; a model may name any stack
that ``copper_stack`` takes."""
FIRST_PLANE = 39
"""Internal Plane 1; planes are numbered from the top of the stack."""
TOP_LAYER, BOTTOM_LAYER = 1, 32
MAX_COPPER, MAX_SIGNAL, MAX_PLANES = 32, 16, 16
"""The stacks written (change c0085): an even number of copper layers up to 32, of which at most 16 are
signal layers and at most 16 internal planes."""
KEEPOUT_LAYER = 56
BOARD_LAYER_MAP: Mapping[str, int] = MappingProxyType(
    {
        "F.SilkS": 33,
        "B.SilkS": 34,
        "F.Paste": 35,
        "B.Paste": 36,
        "F.Mask": 37,
        "B.Mask": 38,
        "F.Fab": 69,
        "B.Fab": 70,
        "F.CrtYd": 71,
        "B.CrtYd": 72,
    }
)
"""Non-copper Fenolite layer → Altium layer id for the free texts and graphics of a board (change c0085):
the non-copper rows of ``LAYER_MAP`` and the paste and solder-mask layers."""
BOTTOM_SIDE: frozenset[int] = frozenset({32, 34, 36, 38, 70, 72})
"""The ids of ``BOARD_LAYER_MAP`` and of the copper that lie on the bottom side: a text there is mirrored."""
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


def stack_problem(count: int, planes: int) -> str | None:
    """Why a stack of ``count`` copper layers with ``planes`` internal planes is not written, or ``None``."""
    if count < 2 or count % 2:
        return f"a stack of {count} copper layers is not written: the count must be even and at least 2"
    if count > MAX_COPPER:
        return f"a stack of {count} copper layers is not written: at most {MAX_COPPER} are"
    if count - planes > MAX_SIGNAL:
        return f"a stack of {count - planes} signal layers is not written: at most {MAX_SIGNAL} are"
    if planes > MAX_PLANES:
        return f"a stack of {planes} internal planes is not written: at most {MAX_PLANES} are"
    return None


def copper_stack(names: Sequence[str], planes: Sequence[str] = ()) -> tuple[int, ...]:
    """The Altium ids of a board's copper layers from top to bottom (``pcb-copper.md``, "Fenolite's
    choices", "Layers"). ``names`` are the model's copper layers in stack order, distinct; ``planes`` names
    the inner layers that are internal planes. The first layer is the top layer (1) and the last the
    bottom layer (32); the k-th inner layer is Mid-Layer k (id k + 1) as a signal layer, whatever the other
    inner layers are, and the planes are numbered from the top (39, 40, …). ``ValueError`` names a stack
    that ``stack_problem`` refuses, a repeated layer or a plane that is not an inner layer."""
    layers = tuple(names)
    wanted = tuple(planes)
    if len(set(layers)) != len(layers):
        raise ValueError(f"the copper layers {layers!r} repeat a layer")
    inner = layers[1:-1]
    if len(set(wanted)) != len(wanted) or any(name not in inner for name in wanted):
        raise ValueError(f"the planes {wanted!r} are not distinct inner layers of {layers!r}")
    problem = stack_problem(len(layers), len(wanted))
    if problem is not None:
        raise ValueError(problem)
    ids: list[int] = [TOP_LAYER]
    plane = FIRST_PLANE
    for position, name in enumerate(inner, start=1):
        if name in wanted:
            ids.append(plane)
            plane += 1
        else:
            ids.append(position + 1)
    ids.append(BOTTOM_LAYER)
    return tuple(ids)


def layer_text(layer: int) -> str:
    """The ``LAYER`` text of a copper layer id in a property record: ``TOP``, ``MID<n>``, ``BOTTOM`` or
    ``PLANE<n>`` (``pcb-copper.md``, "Polygon pour"); ``ValueError`` for another id."""
    if layer == TOP_LAYER:
        return "TOP"
    if layer == BOTTOM_LAYER:
        return "BOTTOM"
    if TOP_LAYER < layer < BOTTOM_LAYER:
        return f"MID{layer - 1}"
    if FIRST_PLANE <= layer < FIRST_PLANE + MAX_PLANES:
        return f"PLANE{layer - FIRST_PLANE + 1}"
    raise ValueError(f"layer {layer} is not a copper layer")


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
"""The PCB records are inferred from public sources; the kicad-cli oracles check only what KiCad reads.
The rows of a component body (change c0121, ``body_record``) are named by the writers that use it:
``pcbdoc.EVIDENCE`` and ``pcblib.EVIDENCE``."""

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


def prefix(layer: int, *, net: int = NO_INDEX, component: int = NO_INDEX, locked: bool = False) -> bytes:
    """The common 13 bytes: layer, the two flag bytes, net, polygon (none), component and ``FF FF FF FF``.
    ``locked`` clears bit 2 of the first flag byte."""
    if not 0 < layer < 256:
        raise ValueError(f"layer id {layer} is not one byte")
    flags = LOCKED_FLAGS if locked else FLAGS
    return struct.pack("<BBBHHH", layer, *flags, net, NO_INDEX, component) + b"\xff" * 4


def lock_written(kind: str, locked: bool) -> bool:
    """Whether a ``locked`` item of the record kind ``kind`` is written locked: its kind is in
    ``LOCK_WRITTEN``."""
    return locked and kind in LOCK_WRITTEN


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
    locked: bool = False,
) -> bytes:
    """A track (type 4): one subrecord of 36 bytes; points and width in binary units. ``locked`` writes the
    locked flag when ``track`` is in ``LOCK_WRITTEN``."""
    held = lock_written("track", locked)
    body = prefix(layer, net=net, component=component, locked=held) + struct.pack(
        "<5iHB", *a, *b, width, 0, 0
    )
    assert len(body) == TRACK_SIZE
    return bytes((TRACK,)) + subrecord(body)


def arc_record(
    layer: int,
    arc: ArcGeometry,
    width: int,
    *,
    net: int = NO_INDEX,
    component: int = NO_INDEX,
    locked: bool = False,
) -> bytes:
    """An arc (type 1): one subrecord of 47 bytes. ``locked`` writes the locked flag when ``arc`` is in
    ``LOCK_WRITTEN``."""
    body = prefix(layer, net=net, component=component, locked=lock_written("arc", locked)) + struct.pack(
        "<3iddiH", arc.cx, arc.cy, arc.radius, arc.start, arc.end, width, 0
    )
    assert len(body) == ARC_SIZE
    return bytes((ARC,)) + subrecord(body)


VIA_START, VIA_END = 1, 32
"""A through via runs from the top layer to the bottom layer on any layer count."""
_MIL = UNITS_PER_MIL
_VIA_LAYERS = 32


def via_record(
    x: int,
    y: int,
    diameter: int,
    hole: int,
    *,
    net: int = NO_INDEX,
    start: int = VIA_START,
    end: int = VIA_END,
    locked: bool = False,
) -> bytes:
    """A via (type 3): one subrecord of 321 bytes, the form Altium saves, with the fixed values of
    ``pcb-copper.md`` ("Via") and zero in every other byte; position and sizes in binary units. ``start``
    and ``end`` are the ids of the two copper layers it spans (a through via: 1 and 32). ``locked`` writes
    the locked flag when ``via`` is in ``LOCK_WRITTEN``."""
    for layer in (start, end):
        layer_text(layer)
    body = bytearray(VIA_SIZE)
    body[0:13] = prefix(MULTI_LAYER, net=net, locked=lock_written("via", locked))
    struct.pack_into("<4i2B", body, 13, x, y, diameter, hole, start, end)
    struct.pack_into("<ihi", body, 32, 10 * _MIL, 4, 10 * _MIL)  # air gap, conductors, conductor width
    struct.pack_into("<2i", body, 42, 20 * _MIL, 20 * _MIL)
    struct.pack_into("<i", body, 54, 4 * _MIL)  # solder-mask expansion
    struct.pack_into(f"<{_VIA_LAYERS}i", body, 75, *[diameter] * _VIA_LAYERS)
    struct.pack_into("<Hi", body, 203, 15, 259)
    struct.pack_into("<i", body, 242, 4 * _MIL)  # back solder-mask expansion
    body[254] = 0x2A
    struct.pack_into("<2i", body, 291, 0x7FFFFFFF, 0x7FFFFFFF)  # hole tolerances
    struct.pack_into("<i", body, 304, 30)  # polygon-connect entry size; the count at 300 is 0
    body[308] = 9
    body[320] = 1
    return bytes((VIA,)) + subrecord(bytes(body))


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
    named = short_string(name) if name else b"\0"  # a hole of the board has no name (change c0085)
    parts = (named, b"\0", PAD_SUBRECORD_3, b"\0", geometry, layers)
    return bytes((PAD,)) + b"".join(subrecord(part) for part in parts)


def hole_record(x: int, y: int, drill: int, *, plated: bool = False) -> bytes:
    """A hole of the board that belongs to no footprint (``pcb-records.md``, "Free pads as holes"): a free
    round pad on Multi-Layer without a name, a net or a component, whose size is its hole size, so it has
    no copper ring; ``plated`` sets the plated byte. Lengths in binary units."""
    if drill <= 0:
        raise ValueError(f"a hole needs a positive drill, not {drill} units")
    return pad_record(
        name="", layer=MULTI_LAYER, x=x, y=y, size=(drill, drill), shape=1, rotation=0.0, hole=drill,
        plated=plated,
    )  # fmt: skip


KEEPOUT_FLAG = 2
"""The second flag byte of a keep-out primitive (``pcb-records.md``, "Regions and keep-outs")."""
KEEPOUT_KEY = "KEEPOUTRESTRICTIONS"
"""The key of a keep-out region's restrictions value, as a saved document holds it."""
KEEPOUT_KEY_KICAD = "KEEPOUTRESTRIC"
"""The key from which KiCad's importer reads the same value. No saved document holds it: it is written
after the keys of a saved region, with the value of ``KEEPOUT_KEY``, so that KiCad's import carries the
restrictions (the maintainer's decision of 2026-10-06; ``pcb-records.md``, "Regions and keep-outs")."""
REGION_ARC_RESOLUTION = "0.5mil"
V7_LAYERS: Mapping[int, str] = MappingProxyType(
    {
        33: "TOPOVERLAY",
        34: "BOTTOMOVERLAY",
        35: "TOPPASTE",
        36: "BOTTOMPASTE",
        37: "TOPSOLDER",
        38: "BOTTOMSOLDER",
        KEEPOUT_LAYER: "KEEPOUT",
        **{56 + n: f"MECHANICAL{n}" for n in range(1, 17)},
    }
)
"""``V7_LAYER`` of a region on a layer that is not copper."""


def v7_layer(layer: int) -> str:
    """The ``V7_LAYER`` text of a region on ``layer``: the copper text of ``layer_text``, or the name of
    ``V7_LAYERS``; ``ValueError`` for a layer without one."""
    if layer in V7_LAYERS:
        return V7_LAYERS[layer]
    return layer_text(layer)


def region_record(
    layer: int,
    vertices: Sequence[tuple[int, int]],
    *,
    shape_based: bool = False,
    keepout: int | None = None,
) -> bytes:
    """A region (type 11) without a net, a polygon or a component (``pcb-records.md``, "Regions and
    keep-outs"): the prefix, five zero bytes, the property text and the outline. ``vertices`` are in binary
    units, without a closing vertex, at least three. The plain form (``Regions6``) holds each vertex as two
    doubles; the shape-based form (``ShapeBasedRegions6``) holds each as 37 bytes, none round, and repeats
    the first vertex after the last. ``keepout`` makes the region a keep-out with that restriction value
    (0 … 31): the second flag byte is 2 and the text ends with ``KEEPOUTRESTRICTIONS`` and, for KiCad's
    importer, ``KEEPOUTRESTRIC``, both holding the value."""
    if len(vertices) < 3:
        raise ValueError("a region needs at least three vertices")
    if keepout is not None and not 0 <= keepout <= 0x1F:
        raise ValueError(f"the keep-out restrictions {keepout} are outside 0 … 31")
    fields: list[Field] = [
        ("V7_LAYER", v7_layer(layer)),
        ("NAME", " "),
        ("KIND", "0"),
        ("SUBPOLYINDEX", "-1"),
        ("UNIONINDEX", "0"),
        ("ARCRESOLUTION", REGION_ARC_RESOLUTION),
        ("ISSHAPEBASED", "FALSE"),
        ("CAVITYHEIGHT", "0mil"),
    ]
    if keepout is not None:
        fields += [(KEEPOUT_KEY, str(keepout)), (KEEPOUT_KEY_KICAD, str(keepout))]
    text = "|".join(f"{key}={value}" for key, value in fields).encode("ascii") + b"\0"
    head = bytearray(prefix(layer))
    if keepout is not None:
        head[2] = KEEPOUT_FLAG
    body = bytes(head) + bytes(5) + struct.pack("<I", len(text)) + text + struct.pack("<I", len(vertices))
    if shape_based:
        for x, y in (*vertices, vertices[0]):
            body += struct.pack("<B5i2d", 0, x, y, 0, 0, 0, 0.0, 0.0)
    else:
        for x, y in vertices:
            body += struct.pack("<2d", float(x), float(y))
    return bytes((REGION,)) + subrecord(body)


# --- component bodies (change c0121) -------------------------------------------------------------------

BODY_KEYS: tuple[str, ...] = (
    "V7_LAYER", "NAME", "KIND", "SUBPOLYINDEX", "UNIONINDEX", "ARCRESOLUTION", "ISSHAPEBASED",
    "CAVITYHEIGHT", "STANDOFFHEIGHT", "OVERALLHEIGHT", "BODYPROJECTION", "ARCRESOLUTION", "BODYCOLOR3D",
    "BODYOPACITY3D", "IDENTIFIER", "TEXTURE", "TEXTURECENTERX", "TEXTURECENTERY", "TEXTURESIZEX",
    "TEXTURESIZEY", "TEXTUREROTATION", "MODELID", "MODEL.CHECKSUM", "MODEL.EMBED", "MODEL.NAME",
    "MODEL.2D.X", "MODEL.2D.Y", "MODEL.2D.ROTATION", "MODEL.3D.ROTX", "MODEL.3D.ROTY", "MODEL.3D.ROTZ",
    "MODEL.3D.DZ", "MODEL.MODELTYPE", "MODEL.EXTRUDED.MINZ", "MODEL.EXTRUDED.MAXZ",
)  # fmt: skip
"""The keys of a written extruded body, in order (``pcb-bodies.md``, "Written form of an extruded body":
one row per key; ``ARCRESOLUTION`` is written twice, as saved records hold it). A unit test compares this
tuple with the rows of the page in both directions: a key without a row is not written."""
BODY_SHORT_KEYS = 21
"""The keys of the short form: the first 21, ending at ``TEXTUREROTATION`` (``H-A-PCBX-BODY-SHORT``)."""
BODY_COLOR = "12632256"
"""``BODYCOLOR3D``: Fenolite's choice among the values that saved records hold (836 of 1272)."""
BODY_TEXTURE_ROTATION = " 0.00000000000000E+0000"
"""``TEXTUREROTATION``: the saved form of a real with the value 0, Fenolite's choice (115 of 1272)."""
BODY_CHECKSUM = "0"
"""``MODEL.CHECKSUM``: a stand-in. No source gives the rule of the saved value (``H-A-PCBX-BODY-OPEN``)."""
BODY_ID_SALT = "fenolite.altium.bodymodel:"
BODY_LAYERS = range(57, 73)
"""The layer ids a body is written on: Mechanical 1 to 16."""
BODY_TOP_LAYER, BODY_BOTTOM_LAYER = 69, 70
"""Mechanical 13 and 14: where a body without a mechanical layer of its own is written, by its side."""
BodyForm = Literal["saved", "short"]
_MECHANICAL = re.compile(r"Mech\.(\d+)")


def body_model_id(body_id: str) -> str:
    """The ``MODELID`` of a written body: a GUID text in braces made of the first 16 bytes of the SHA-256
    of ``fenolite.altium.bodymodel:<body_id>``, so that it depends on ``body_id`` alone and a build is
    repeatable. It is a stand-in: a saved body holds a GUID whose origin no source states
    (``pcb-bodies.md``, the row of ``MODELID``; ``H-A-PCBX-BODY-OPEN``)."""
    digest = hashlib.sha256((BODY_ID_SALT + body_id).encode("utf-8")).hexdigest().upper()
    return "{" + "-".join((digest[:8], digest[8:12], digest[12:16], digest[16:20], digest[20:32])) + "}"


def body_layer(name: str, *, bottom: bool) -> int:
    """The layer id a body on the model layer ``name`` is written on (``pcb-bodies.md``, "Layer rule"): the
    id of a mechanical layer 1 to 16 when ``name`` is one of ``BOARD_LAYER_MAP`` or the import's
    ``Mech.<n>``; else Mechanical 13 for a top footprint and Mechanical 14 for a bottom one."""
    found = BOARD_LAYER_MAP.get(name)
    if found is None:
        match = _MECHANICAL.fullmatch(name)
        found = 56 + int(match.group(1)) if match is not None else None
    if found is not None and found in BODY_LAYERS:
        return found
    return BODY_BOTTOM_LAYER if bottom else BODY_TOP_LAYER


def _half_towards_zero(twice: int) -> int:
    half = abs(twice) // 2
    return half if twice >= 0 else -half


def body_record(
    layer: int,
    vertices: Sequence[tuple[int, int]],
    *,
    component: int,
    standoff: int,
    overall: int,
    bottom: bool,
    identifier: str = "",
    model_id: str = "",
    shape_based: bool = False,
    form: BodyForm = "saved",
) -> bytes:
    """One extruded component body (type 12; ``pcb-bodies.md``, "Written form of an extruded body"): the
    common prefix with ``layer`` and the ``component`` index (``NO_INDEX`` for none), five zero bytes, the
    property text and the outline. ``vertices`` are binary units, at least three, without a closing vertex.
    The plain form (``ComponentBodies6`` and a library) holds each vertex as two doubles; the shape-based
    form (``ShapeBasedComponentBodies6``) holds each as 37 bytes, none round, and repeats the first vertex.

    ``standoff`` and ``overall`` are the two heights in units; ``bottom`` gives ``BODYPROJECTION`` 1.
    ``form="saved"`` writes the 35 keys of ``BODY_KEYS`` with ``MODELID`` ``model_id`` and
    ``MODEL.CHECKSUM`` 0, the two stand-ins; ``form="short"`` writes the first 21 keys, for step X8 of the
    author report only. ``ValueError`` for fewer than three vertices, a layer that is no Mechanical 1 to
    16, a component index outside 16 bits, an overall height that is not above the standoff, a negative
    standoff, an empty ``model_id`` in the saved form, or an unknown form."""
    if form not in ("saved", "short"):
        raise ValueError(f"unknown body form {form!r}: saved, short")
    if len(vertices) < 3:
        raise ValueError("a component body needs at least three vertices")
    if layer not in BODY_LAYERS:
        raise ValueError(f"layer {layer} is not a mechanical layer 1 to 16 (ids 57 to 72)")
    if not 0 <= component <= NO_INDEX:
        raise ValueError(f"the component index {component} is not 16 bits")
    if standoff < 0:
        raise ValueError("no saved extruded body holds a negative standoff; none is written")
    if overall <= standoff:
        raise ValueError("the overall height of a component body must be above its standoff")
    if form == "saved" and not model_id:
        raise ValueError("the saved form of a component body needs a model id")
    xs, ys = [x for x, _ in vertices], [y for _, y in vertices]
    values: dict[str, str] = {
        "V7_LAYER": V7_LAYERS[layer],
        "NAME": " ",
        "KIND": "0",
        "SUBPOLYINDEX": "-1",
        "UNIONINDEX": "0",
        "ARCRESOLUTION": REGION_ARC_RESOLUTION,
        "ISSHAPEBASED": "FALSE",
        "CAVITYHEIGHT": "0mil",
        "STANDOFFHEIGHT": mil_text(standoff),
        "OVERALLHEIGHT": mil_text(overall),
        "BODYPROJECTION": "1" if bottom else "0",
        "BODYCOLOR3D": BODY_COLOR,
        "BODYOPACITY3D": "1.000",
        "IDENTIFIER": ",".join(str(ord(character)) for character in identifier),
        "TEXTURE": "",
        "TEXTURECENTERX": "0mil",
        "TEXTURECENTERY": "0mil",
        "TEXTURESIZEX": "0mil",
        "TEXTURESIZEY": "0mil",
        "TEXTUREROTATION": BODY_TEXTURE_ROTATION,
        "MODELID": model_id,
        "MODEL.CHECKSUM": BODY_CHECKSUM,
        "MODEL.EMBED": "FALSE",
        "MODEL.NAME": "",
        "MODEL.2D.X": mil_text(_half_towards_zero(min(xs) + max(xs))),
        "MODEL.2D.Y": mil_text(_half_towards_zero(min(ys) + max(ys))),
        "MODEL.2D.ROTATION": "0.000",
        "MODEL.3D.ROTX": "0.000",
        "MODEL.3D.ROTY": "0.000",
        "MODEL.3D.ROTZ": "0.000",
        "MODEL.3D.DZ": "0mil",
        "MODEL.MODELTYPE": "0",
        "MODEL.EXTRUDED.MINZ": mil_text(standoff),
        "MODEL.EXTRUDED.MAXZ": mil_text(overall),
    }
    keys = BODY_KEYS if form == "saved" else BODY_KEYS[:BODY_SHORT_KEYS]
    text = "|".join(f"{key}={values[key]}" for key in keys).encode("ascii") + b"\0"
    body = prefix(layer, component=component) + bytes(5) + struct.pack("<I", len(text)) + text
    body += struct.pack("<I", len(vertices))
    if shape_based:
        for x, y in (*vertices, vertices[0]):
            body += struct.pack("<B5i2d", 0, x, y, 0, 0, 0, 0.0, 0.0)
    else:
        for x, y in vertices:
            body += struct.pack("<2d", float(x), float(y))
    return bytes((BODY,)) + subrecord(body)


__all__ = [
    "ARC",
    "ARC_SIZE",
    "BODY",
    "BODY_BOTTOM_LAYER",
    "BODY_CHECKSUM",
    "BODY_COLOR",
    "BODY_KEYS",
    "BODY_LAYERS",
    "BODY_SHORT_KEYS",
    "BODY_TEXTURE_ROTATION",
    "BODY_TOP_LAYER",
    "BodyForm",
    "body_layer",
    "body_model_id",
    "body_record",
    "BOARD_LAYER_MAP",
    "BOTTOM_LAYER",
    "BOTTOM_SIDE",
    "KEEPOUT_FLAG",
    "KEEPOUT_LAYER",
    "MAX_COPPER",
    "MAX_PLANES",
    "MAX_SIGNAL",
    "REGION",
    "TOP_LAYER",
    "V7_LAYERS",
    "hole_record",
    "layer_text",
    "region_record",
    "stack_problem",
    "v7_layer",
    "COPPER_LAYER_TEXT",
    "COPPER_STACKS",
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
    "VIA",
    "VIA_SIZE",
    "ArcGeometry",
    "angle_degrees",
    "arc_from_points",
    "arc_record",
    "circle_geometry",
    "copper_stack",
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
    "via_record",
]
