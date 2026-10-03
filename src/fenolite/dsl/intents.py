# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper intents of the DSL: tracks, vias and stitches declared by pad references and board points
(``docs/dsl.md``, "Copper"; capability design-dsl, "Copper intents in the DSL").

A script cannot know where a pad ends up: the build decides each placement after the script ran, and a
footprint moved in KiCad keeps its place. So the script records what to join, as plain data, and the build
resolves it after placement (``fenolite.backends.kicad.copper``). Nothing here is a model object.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net, Part
from fenolite.dsl.units import as_nm

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

KEY = re.compile(r"^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$")
"""A copper key: it names the intent stably, and every uuid of its copper derives from it."""


@dataclass(frozen=True, slots=True)
class PadRef:
    """The pads of a part with one number, as a script names them; ``index`` picks one of several."""

    part: Part
    number: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class PadEnd:
    """A pad end as the build reads it: the component path, the pad number and the optional index."""

    component: str
    number: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class ViaStep:
    """A through via inside a track path at ``at`` (board frame), after which the track runs on ``layer``."""

    at: Point
    layer: str
    diameter: Nm | None = None
    drill: Nm | None = None


@dataclass(frozen=True, slots=True)
class TrackIntent:
    key: str
    path: tuple[PadEnd | Point | ViaStep, ...]
    layer: str = "F.Cu"
    width: Nm | None = None
    net: str | None = None


@dataclass(frozen=True, slots=True)
class ViaIntent:
    key: str
    at: Point
    net: str
    diameter: Nm | None = None
    drill: Nm | None = None


@dataclass(frozen=True, slots=True)
class StitchIntent:
    key: str
    net: str
    pitch: Nm
    along: tuple[Point, ...] = ()
    region: tuple[Point, ...] = ()
    origin: Point = Point(0, 0)
    diameter: Nm | None = None
    drill: Nm | None = None
    clearance: Nm | None = None
    margin: Nm = 0


CopperIntent = TrackIntent | ViaIntent | StitchIntent


# --- what a script records ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Track:
    key: str
    path: tuple[PadRef | Point | ViaStep, ...]
    layer: str
    width: Nm | None
    net: Net | None


@dataclass(frozen=True, slots=True)
class _Via:
    key: str
    at: Point
    net: Net
    diameter: Nm | None
    drill: Nm | None


@dataclass(frozen=True, slots=True)
class _Stitch:
    key: str
    net: Net
    pitch: Nm
    along: tuple[Point, ...]
    region: tuple[Point, ...]
    origin: Point
    diameter: Nm | None
    drill: Nm | None
    clearance: Nm | None
    margin: Nm


Recorded = _Track | _Via | _Stitch


def _origin() -> Point:
    from fenolite.dsl.convert import BOARD_ORIGIN

    return BOARD_ORIGIN


def _point(value: object, what: str) -> Point:
    """An ``(x, y)`` pair of lengths in the frame of ``place()``, as a board-frame point."""
    pair = cast("Sequence[object]", value) if isinstance(value, (tuple, list)) else ()
    if len(pair) != 2:
        raise DslError(f"{what}: a point is an (x, y) pair of lengths, not {value!r}")
    origin = _origin()
    return Point(origin.x + as_nm(pair[0], name=f"{what}.x"), origin.y + as_nm(pair[1], name=f"{what}.y"))


def _size(value: object, what: str) -> Nm | None:
    if value is None:
        return None
    size = as_nm(value, name=what)
    if size <= 0:
        raise DslError(f"{what} must be positive")
    return size


def _layer(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise DslError(f"{what} must be a copper layer name such as 'F.Cu', not {value!r}")
    return value


def _net(value: object, what: str, *, required: bool) -> Net | None:
    if value is None and not required:
        return None
    if not isinstance(value, Net):
        raise DslError(f"{what}: net must be a Net, not {value!r}")
    return value


def check_key(design: Design, key: object) -> str:
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise DslError(f"copper key {key!r} must match {KEY.pattern}")
    if key in design.copper_intents:
        raise DslError(f"copper key {key!r} is already used")
    return key


def pad_ref(part: Part, number: object, index: object) -> PadRef:
    if isinstance(number, bool) or not isinstance(number, (str, int)) or str(number) == "":
        raise DslError(f"part {part.ref}: a pad number is a non-empty str or an int, not {number!r}")
    if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
        raise DslError(f"part {part.ref}: a pad index is a non-negative int or None, not {index!r}")
    return PadRef(part, str(number), index)


def via_step(x: object, y: object, *, to: str, diameter: object = None, drill: object = None) -> ViaStep:
    """A through via at ``(x, y)`` in the frame of ``place()``; the track continues on the layer ``to``."""
    return ViaStep(
        _point((x, y), "via_step"), _layer(to, "via_step: to"), _size(diameter, "via_step: diameter"),
        _size(drill, "via_step: drill"),
    )  # fmt: skip


def _same_place(a: PadRef | Point | ViaStep, b: PadRef | Point | ViaStep) -> bool:
    if isinstance(a, PadRef) or isinstance(b, PadRef):
        return a == b
    at_a = a.at if isinstance(a, ViaStep) else a
    at_b = b.at if isinstance(b, ViaStep) else b
    return at_a == at_b


def record_track(
    design: Design, key: object, path: Sequence[object], layer: object, width: object, net: object
) -> None:
    name = check_key(design, key)
    what = f"track {name}"
    if len(path) < 2:
        raise DslError(f"{what}: a path needs at least two elements")
    elements: list[PadRef | Point | ViaStep] = []
    for index, element in enumerate(path):
        if isinstance(element, (PadRef, ViaStep)):
            elements.append(element)
        elif isinstance(element, (tuple, list)):
            elements.append(_point(cast(object, element), f"{what}: path[{index}]"))
        else:
            raise DslError(
                f"{what}: path[{index}] must be part.pad(…), via_step(…) or an (x, y) pair, not {element!r}"
            )
    if isinstance(elements[0], ViaStep):
        raise DslError(f"{what}: a path cannot start with a via step")
    for index, (a, b) in enumerate(zip(elements, elements[1:], strict=False)):
        if _same_place(a, b):
            raise DslError(f"{what}: path[{index}] and path[{index + 1}] are at the same point")
    design.copper_intents[name] = _Track(
        name,
        tuple(elements),
        _layer(layer, f"{what}: layer"),
        _size(width, f"{what}: width"),
        _net(net, what, required=False),
    )


def record_via(
    design: Design, key: object, x: object, y: object, net: object, diameter: object, drill: object
) -> None:
    name = check_key(design, key)
    what = f"via {name}"
    chosen = _net(net, what, required=True)
    assert chosen is not None
    design.copper_intents[name] = _Via(
        name,
        _point((x, y), what),
        chosen,
        _size(diameter, f"{what}: diameter"),
        _size(drill, f"{what}: drill"),
    )


def record_stitch(
    design: Design,
    key: object,
    *,
    net: object,
    pitch: object,
    along: Sequence[object],
    region: Sequence[object],
    origin: object,
    diameter: object,
    drill: object,
    clearance: object,
    margin: object,
) -> None:
    name = check_key(design, key)
    what = f"stitch {name}"
    chosen = _net(net, what, required=True)
    assert chosen is not None
    step = _size(pitch, f"{what}: pitch")
    if step is None:
        raise DslError(f"{what}: pitch is required")
    line = tuple(_point(p, f"{what}: along[{i}]") for i, p in enumerate(along))
    ring = tuple(_point(p, f"{what}: region[{i}]") for i, p in enumerate(region))
    if bool(line) == bool(ring):
        raise DslError(f"{what}: give exactly one of along and region")
    if line and len(line) < 2:
        raise DslError(f"{what}: along needs at least two points")
    if ring and len(ring) < 3:
        raise DslError(f"{what}: region needs at least three points")
    gap = 0 if margin is None else as_nm(margin, name=f"{what}: margin")
    if gap < 0:
        raise DslError(f"{what}: margin must not be negative")
    free = None if clearance is None else as_nm(clearance, name=f"{what}: clearance")
    if free is not None and free < 0:
        raise DslError(f"{what}: clearance must not be negative")
    design.copper_intents[name] = _Stitch(
        name,
        chosen,
        step,
        line,
        ring,
        _origin() if origin is None else _point(origin, f"{what}: origin"),
        _size(diameter, f"{what}: diameter"),
        _size(drill, f"{what}: drill"),
        free,
        gap,
    )


def _net_name(design: Design, net: Net, key: str) -> str:
    if design.nets.get(net.name) is not net:
        raise DslError(f"copper {key}: net {net.name} is not in the design")
    return net.name


def _end(design: Design, element: PadRef | Point | ViaStep, key: str) -> PadEnd | Point | ViaStep:
    if not isinstance(element, PadRef):
        return element
    part = element.part
    if design.parts.get(part.path) is not part:
        raise DslError(f"copper {key}: part {part.ref} is not in the design")
    return PadEnd(part.path, element.number, element.index)


def copper(design: Design) -> tuple[CopperIntent, ...]:
    """The copper intents of ``design`` as plain data, in key order: pad references become component
    paths, nets their names, and every point is in the written board frame."""
    found: list[CopperIntent] = []
    for key in sorted(design.copper_intents):
        item = design.copper_intents[key]
        if isinstance(item, _Track):
            net = None if item.net is None else _net_name(design, item.net, key)
            path = tuple(_end(design, element, key) for element in item.path)
            found.append(TrackIntent(key, path, item.layer, item.width, net))
        elif isinstance(item, _Via):
            found.append(ViaIntent(key, item.at, _net_name(design, item.net, key), item.diameter, item.drill))
        else:
            found.append(
                StitchIntent(
                    key,
                    _net_name(design, item.net, key),
                    item.pitch,
                    item.along,
                    item.region,
                    item.origin,
                    item.diameter,
                    item.drill,
                    item.clearance,
                    item.margin,
                )
            )
    return tuple(found)


__all__ = [
    "KEY",
    "CopperIntent",
    "PadEnd",
    "PadRef",
    "Recorded",
    "StitchIntent",
    "TrackIntent",
    "ViaIntent",
    "ViaStep",
    "copper",
    "via_step",
]
