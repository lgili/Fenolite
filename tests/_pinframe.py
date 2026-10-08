# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored sheet that places one asymmetric symbol in each of the twelve frames (four rotations, no
mirror and the two mirrors) with a global label on each pin (change c0137).

The symbol ``Probe:Frame`` is written here for Fenolite: three pins whose positions no mirror and no
rotation of the symbol maps onto each other, so a label set at the point of the wrong frame either misses
its pin or lands on another pin of the same unit. ``frame_sheet`` sets the labels where a function of
the caller puts them (``schlayout.pin_point`` by default); the unit tests read the sheet back and the oracle
test asks ``kicad-cli`` which net each pin is on.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.core.coords import Point

NS = uuid.UUID("00000000-0000-4000-8000-0000000c0137")
FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"
PINS: tuple[tuple[str, Point, int], ...] = (
    ("1", Point(-7_620_000, 2_540_000), 0),
    ("2", Point(-7_620_000, -5_080_000), 0),
    ("3", Point(7_620_000, 0), 180),
)
"""Number, library position (Y up) and angle of each pin of ``Probe:Frame``."""
FRAMES: tuple[tuple[int, str], ...] = tuple((r, m) for m in ("", "x", "y") for r in (0, 90, 180, 270))
"""The twelve frames, in the order of the references ``U1`` to ``U12``."""
PITCH = 30_480_000
PlacePin = Callable[[Point, Point, int, str], Point]


def mm(nm: int) -> str:
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    return f"{sign}{whole}" + (f".{frac:06d}".rstrip("0") if frac else "")


def uid(*parts: object) -> str:
    return str(uuid.uuid5(NS, ":".join(str(p) for p in parts)))


def quoted(text: str) -> str:
    return dumps(Atom.string(text)).strip()


def symbol() -> str:
    rows = " ".join(
        f"(pin passive line (at {mm(at.x)} {mm(at.y)} {angle}) (length 2.54) "
        f"(name {quoted('P' + number)} {FONT}) (number {quoted(number)} {FONT}))"
        for number, at, angle in PINS
    )
    body = (
        "(rectangle (start -5.08 5.08) (end 5.08 -7.62) (stroke (width 0) (type default)) (fill (type none)))"
    )
    return (
        '(symbol "Probe:Frame" (exclude_from_sim no) (in_bom yes) (on_board yes) '
        f'(property "Reference" "U" (at 0 7.62 0) {FONT}) (property "Value" "Frame" (at 0 -10.16 0) {FONT}) '
        f'(symbol "Frame_0_1" {body}) (symbol "Frame_1_1" {rows}))'
    )


def origin(index: int) -> Point:
    """The origin of the instance of frame ``index``: four columns, three rows, on the 1.27 mm grid."""
    column, row = index % 4, index // 4
    return Point(50_800_000 + column * PITCH, 50_800_000 + row * PITCH)


def ref(index: int) -> str:
    return f"U{index + 1}"


def net(index: int, number: str) -> str:
    """The label text of pin ``number`` of the instance of frame ``index``."""
    return f"{ref(index)}_P{number}"


def frame_sheet(target: int, place: PlacePin = schlayout.pin_point, name: str = "frames") -> str:
    """The twelve instances on one A3 sheet of the format of KiCad ``target``, with the label of each pin
    at ``place(origin, pin, rotation, mirror)``."""
    root = uid(name, "root")
    out = [
        f"(kicad_sch (version {FORMAT_VERSIONS[FileKind.SCHEMATIC][target]}) "
        f'(generator "fenolite-tests") (generator_version "{target}.0") (uuid "{root}") (paper "A3")',
        f"(lib_symbols {symbol()})",
    ]
    for index, (rotation, mirror) in enumerate(FRAMES):
        at = origin(index)
        for number, pin, _angle in PINS:
            point = place(at, pin, rotation, mirror)
            key = uid(name, "label", index, number)
            out.append(
                f"(global_label {quoted(net(index, number))} (shape passive) "
                f"(at {mm(point.x)} {mm(point.y)} 0) "
                f'(effects (font (size 1.27 1.27)) (justify left)) (uuid "{key}"))'
            )
    for index, (rotation, mirror) in enumerate(FRAMES):
        at, reference = origin(index), ref(index)
        x, y = mm(at.x), mm(at.y)
        flip = f" (mirror {mirror})" if mirror else ""
        pins = " ".join(f'(pin {quoted(n)} (uuid "{uid(name, reference, "pin", n)}"))' for n, _, _ in PINS)
        out.append(
            f'(symbol (lib_id "Probe:Frame") (at {x} {y} {rotation}){flip} (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid "{uid(name, reference)}") '
            f'(property "Reference" {quoted(reference)} (at {x} {y} 0) {HIDDEN}) '
            f'(property "Value" "Frame" (at {x} {y} 0) {HIDDEN}) '
            f'(property "Footprint" "" (at {x} {y} 0) {HIDDEN}) '
            f'(property "Datasheet" "" (at {x} {y} 0) {HIDDEN}) '
            f'{pins} (instances (project "{name}" (path "/{root}" '
            f"(reference {quoted(reference)}) (unit 1)))))"
        )
    out.append('(sheet_instances (path "/" (page "1"))))')
    return dumps(parse("\n".join(out)))


def mirror_first(origin: Point, pin: Point, rotation: int, mirror: str) -> Point:
    """The order ``schlayout.pin_point`` had before change c0137: the mirror, then the rotation. Used only as
    the control of the oracle test, which must tell the two orders apart."""
    x = -pin.x if mirror == "y" else pin.x
    y = -pin.y if mirror == "x" else pin.y
    px, py = schlayout.turned(x, y, rotation, "")
    return Point(origin.x + px, origin.y - py)


def expected() -> dict[tuple[str, str], str]:
    """(reference, pin number) → the label text the pin must be on."""
    return {(ref(i), n): net(i, n) for i in range(len(FRAMES)) for n, _, _ in PINS}


def distinguishing() -> list[int]:
    """The frames whose pins the two orders put on different points: the mirrored ones at 90 and 270."""
    return [
        index
        for index, (rotation, mirror) in enumerate(FRAMES)
        if any(
            schlayout.pin_point(origin(index), pin, rotation, mirror)
            != mirror_first(origin(index), pin, rotation, mirror)
            for _, pin, _ in PINS
        )
    ]


__all__ = [
    "FRAMES",
    "PINS",
    "distinguishing",
    "expected",
    "frame_sheet",
    "mirror_first",
    "net",
    "origin",
    "ref",
    "symbol",
]
