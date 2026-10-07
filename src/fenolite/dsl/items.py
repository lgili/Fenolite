# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board items of a script: rule areas, texts, graphics and dimensions (``docs/dsl.md``, "Rule areas"
and "Board drawings").

The functions here check the arguments of the ``Design`` calls and return frozen records; ``to_model``
turns the records into ``Keepout``, ``Text``, ``Graphic`` and ``Dimension`` entities. Points are kept as
board-relative nanometre pairs: ``BOARD_ORIGIN`` is added when the model is made.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from fenolite.core.units import Nm, Udeg
from fenolite.dsl.errors import DslError
from fenolite.dsl.part import FIELD_JUSTIFY
from fenolite.dsl.units import as_nm, as_udeg
from fenolite.model.board import DimensionDirection, DimensionKind, DimensionUnits, GraphicKind, LayerKind

AREA_NAME = re.compile(r"^[A-Za-z0-9_.+-]+$")
"""A rule-area name: no character a rules condition would have to escape, and no ``*``."""
DRAWING_KEY = re.compile(r"^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$")
"""The key of a drawing; the pattern of copper intent keys."""
FORBID: Mapping[str, str] = MappingProxyType(
    {"tracks": "no_tracks", "vias": "no_vias", "pads": "no_pads", "pours": "no_copper_pour"}
)
"""The values of ``rule_area(forbid=…)`` and the ``Keepout`` field each sets."""
DRAWING_LAYER_KINDS: tuple[LayerKind, ...] = ("silkscreen", "soldermask", "fabrication", "user")
"""The kinds of layer a text or a drawing may be on. Copper is refused: the copper check cannot see
glyphs, and KiCad reports a copper text across a track but not a copper line (``H-K-BOARD-TEXT``)."""
BOARD_LAYER_KINDS: Mapping[str, LayerKind] = MappingProxyType(
    {
        "F.Adhes": "mechanical",
        "B.Adhes": "mechanical",
        "F.Paste": "solderpaste",
        "B.Paste": "solderpaste",
        "F.SilkS": "silkscreen",
        "B.SilkS": "silkscreen",
        "F.Mask": "soldermask",
        "B.Mask": "soldermask",
        "Dwgs.User": "user",
        "Cmts.User": "user",
        "Eco1.User": "user",
        "Eco2.User": "user",
        "Edge.Cuts": "edge",
        "Margin": "mechanical",
        "F.CrtYd": "courtyard",
        "B.CrtYd": "courtyard",
        "F.Fab": "fabrication",
        "B.Fab": "fabrication",
    }
)
"""The layers of a created board that are not copper, with their kinds. The KiCad backend holds the table
(``layers.created_layers``); the DSL imports only the model, so a unit test keeps the two equal."""
TEXT_SIZE: Nm = 1_000_000
TEXT_THICKNESS: Nm = 150_000
"""The size and stroke of a text without one: the values the KiCad writer gives created footprint fields
(``pcb.TEXT_SIZE``, ``pcb.TEXT_THICKNESS``), repeated here because the DSL imports no backend."""
DIMENSION_UNITS: tuple[str, ...] = ("mm", "in")
DIMENSION_DIRECTIONS: tuple[str, ...] = ("horizontal", "vertical")
MAX_PRECISION = 4

Pair = tuple[Nm, Nm]


@dataclass(frozen=True)
class RuleArea:
    """One ``rule_area()`` call: the name, the outline as board-relative ``(x, y)`` nanometres, the copper
    layers and what the area forbids (empty for an area that only rules select)."""

    name: str
    outline: tuple[Pair, ...]
    layers: tuple[str, ...]
    forbid: tuple[str, ...]


@dataclass(frozen=True)
class TextSpec:
    """One ``text()`` call."""

    key: str
    text: str
    at: Pair
    layer: str
    size: Nm
    thickness: Nm
    rotation: Udeg
    justify: str | None


@dataclass(frozen=True)
class GraphicSpec:
    """One ``line()``, ``rect()``, ``circle()``, ``arc()`` or ``polygon()`` call; ``points`` are in the
    order of the call."""

    key: str
    kind: GraphicKind
    points: tuple[Pair, ...]
    layer: str
    width: Nm
    fill: bool


@dataclass(frozen=True)
class DimensionSpec:
    """One ``dimension()`` call; ``None`` for ``size``, ``thickness`` and ``width`` means the backend's
    default."""

    key: str
    kind: DimensionKind
    start: Pair
    end: Pair
    offset: Nm
    layer: str
    direction: DimensionDirection | None
    units: DimensionUnits
    precision: int
    size: Nm | None
    thickness: Nm | None
    width: Nm | None


Drawing = TextSpec | GraphicSpec | DimensionSpec


def point(value: object, what: str) -> Pair:
    """An ``(x, y)`` pair of lengths as nanometres."""
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise DslError(f"{what} must be an (x, y) pair of lengths, not {value!r}")
    xy = cast("Sequence[object]", value)
    if len(xy) != 2:
        raise DslError(f"{what} must be an (x, y) pair of lengths, not {value!r}")
    return as_nm(xy[0], name=f"{what}.x"), as_nm(xy[1], name=f"{what}.y")


def points(value: object, what: str, least: int) -> tuple[Pair, ...]:
    """At least ``least`` points."""
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise DslError(f"{what} must hold at least {least} (x, y) points")
    pairs = cast("Sequence[object]", value)
    if len(pairs) < least:
        raise DslError(f"{what} must hold at least {least} (x, y) points")
    return tuple(point(pair, f"{what}[{index}]") for index, pair in enumerate(pairs))


def rule_area(
    name: object,
    outline: object,
    layers: object,
    forbid: object,
    *,
    copper: tuple[str, ...],
    taken: Sequence[str],
) -> RuleArea:
    """The record of one ``rule_area()`` call; ``copper`` are the board's copper layers and ``taken`` the
    names already declared."""
    if not isinstance(name, str) or not AREA_NAME.fullmatch(name):
        raise DslError(f"rule_area(): name {name!r} must match {AREA_NAME.pattern}")
    what = f"rule area {name}"
    for other in taken:
        if other.casefold() == name.casefold():
            raise DslError(
                f"rule_area(): name {name!r} is already used"
                + ("" if other == name else f" as {other!r} (KiCad compares area names with letter case)")
            )
    found = points(outline, f"{what}: outline", 3)
    if layers is None:
        on = copper
    else:
        if isinstance(layers, str) or not isinstance(layers, Sequence) or not layers:
            raise DslError(f"{what}: layers must be None or a non-empty sequence of copper layer names")
        chosen: list[str] = []
        for layer in cast("Sequence[object]", layers):
            if not isinstance(layer, str) or layer not in copper:
                raise DslError(
                    f"{what}: layers: {layer!r} is not a copper layer of this board ({', '.join(copper)})"
                )
            if layer in chosen:
                raise DslError(f"{what}: layers: {layer!r} is listed twice")
            chosen.append(layer)
        on = tuple(chosen)
    if isinstance(forbid, str) or not isinstance(forbid, Sequence):
        raise DslError(f"{what}: forbid must be a tuple of {', '.join(FORBID)}, not {forbid!r}")
    kinds: list[str] = []
    for kind in cast("Sequence[object]", forbid):
        if not isinstance(kind, str) or kind not in FORBID:
            raise DslError(f"{what}: forbid: {kind!r} is not one of {', '.join(FORBID)}")
        if kind in kinds:
            raise DslError(f"{what}: forbid: {kind!r} is listed twice")
        kinds.append(kind)
    return RuleArea(name, found, on, tuple(kinds))


def drawing_key(key: object, taken: Mapping[str, object]) -> str:
    if not isinstance(key, str) or not DRAWING_KEY.fullmatch(key):
        raise DslError(f"drawing key {key!r} must match {DRAWING_KEY.pattern}")
    if key in taken:
        raise DslError(f"drawing key {key!r} is already used")
    return key


def drawing_layer(layer: object, what: str) -> str:
    """A layer a drawing may be on: one of the board whose kind is in ``DRAWING_LAYER_KINDS``."""
    kind = BOARD_LAYER_KINDS.get(layer) if isinstance(layer, str) else None
    if kind not in DRAWING_LAYER_KINDS:
        allowed = ", ".join(n for n, k in BOARD_LAYER_KINDS.items() if k in DRAWING_LAYER_KINDS)
        raise DslError(f"{what}: layer {layer!r} takes no drawing; the layers are {allowed}")
    return cast("str", layer)


def _positive(value: object, what: str, default: Nm | None) -> Nm | None:
    if value is None:
        return default
    length = as_nm(value, name=what)
    if length <= 0:
        raise DslError(f"{what} must be above 0")
    return length


def text(
    key: str, text: object, at: object, layer: object, size: object, thickness: object, rot: object,
    justify: object,
) -> TextSpec:  # fmt: skip
    what = f"text {key}"
    if not isinstance(text, str) or not text or not text.isprintable():
        raise DslError(f"{what}: text must be a non-empty printable string on one line, not {text!r}")
    position = point(at, f"{what}: at")
    on = drawing_layer(layer, what)
    height = _positive(size, f"{what}: size", TEXT_SIZE)
    stroke = _positive(thickness, f"{what}: thickness", TEXT_THICKNESS)
    assert height is not None and stroke is not None
    if justify is not None:
        if not isinstance(justify, str) or " ".join(justify.split()) not in FIELD_JUSTIFY:
            raise DslError(f"{what}: justify is 'left' or 'right', then 'top' or 'bottom', not {justify!r}")
        justify = " ".join(justify.split())
    return TextSpec(key, text, position, on, height, stroke, as_udeg(rot, name=f"{what}: rot"), justify)


def _width(value: object, what: str, *, stroked: bool) -> Nm:
    width = as_nm(value, name=f"{what}: width")
    if width < 0 or (stroked and width == 0):
        raise DslError(f"{what}: width must be " + ("above 0" if stroked else "at least 0"))
    return width


def _fill(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise DslError(f"{what}: fill must be a bool, not {value!r}")
    return value


def line(key: str, start: object, end: object, layer: object, width: object) -> GraphicSpec:
    what = f"line {key}"
    a, b = point(start, f"{what}: start"), point(end, f"{what}: end")
    if a == b:
        raise DslError(f"{what}: start and end are the same point")
    return GraphicSpec(
        key, "line", (a, b), drawing_layer(layer, what), _width(width, what, stroked=True), False
    )


def rect(key: str, start: object, end: object, layer: object, width: object, fill: object) -> GraphicSpec:
    what = f"rect {key}"
    a, b = point(start, f"{what}: start"), point(end, f"{what}: end")
    if a[0] == b[0] or a[1] == b[1]:
        raise DslError(f"{what}: start and end must differ in x and in y")
    filled = _fill(fill, what)
    return GraphicSpec(
        key, "rect", (a, b), drawing_layer(layer, what), _width(width, what, stroked=not filled), filled
    )


def circle(key: str, center: object, edge: object, layer: object, width: object, fill: object) -> GraphicSpec:
    what = f"circle {key}"
    a, b = point(center, f"{what}: center"), point(edge, f"{what}: edge")
    if a == b:
        raise DslError(f"{what}: edge must differ from center")
    filled = _fill(fill, what)
    return GraphicSpec(
        key, "circle", (a, b), drawing_layer(layer, what), _width(width, what, stroked=not filled), filled
    )


def arc(key: str, start: object, mid: object, end: object, layer: object, width: object) -> GraphicSpec:
    what = f"arc {key}"
    a, m, b = point(start, f"{what}: start"), point(mid, f"{what}: mid"), point(end, f"{what}: end")
    if (m[0] - a[0]) * (b[1] - a[1]) == (m[1] - a[1]) * (b[0] - a[0]):
        raise DslError(f"{what}: the points start, mid and end must be distinct and not on one line")
    return GraphicSpec(
        key, "arc", (a, m, b), drawing_layer(layer, what), _width(width, what, stroked=True), False
    )


def polygon(key: str, pts: object, layer: object, width: object, fill: object) -> GraphicSpec:
    what = f"polygon {key}"
    found = points(pts, f"{what}: points", 3)
    filled = _fill(fill, what)
    return GraphicSpec(
        key, "polygon", found, drawing_layer(layer, what), _width(width, what, stroked=not filled), filled
    )


def dimension(
    key: str, start: object, end: object, offset: object, layer: object, direction: object, units: object,
    precision: object, size: object, thickness: object, width: object,
) -> DimensionSpec:  # fmt: skip
    what = f"dimension {key}"
    a, b = point(start, f"{what}: start"), point(end, f"{what}: end")
    if a == b:
        raise DslError(f"{what}: start and end are the same point")
    height = as_nm(offset, name=f"{what}: offset")
    on = drawing_layer(layer, what)
    if direction is not None and direction not in DIMENSION_DIRECTIONS:
        raise DslError(f"{what}: direction must be None, 'horizontal' or 'vertical', not {direction!r}")
    if (direction == "horizontal" and a[0] == b[0]) or (direction == "vertical" and a[1] == b[1]):
        raise DslError(f"{what}: direction {direction!r} measures a difference of 0 between the points")
    if units not in DIMENSION_UNITS:
        raise DslError(f"{what}: units must be 'mm' or 'in', not {units!r}")
    if isinstance(precision, bool) or not isinstance(precision, int) or not 0 <= precision <= MAX_PRECISION:
        raise DslError(f"{what}: precision must be an int from 0 to {MAX_PRECISION}, not {precision!r}")
    return DimensionSpec(
        key,
        "aligned" if direction is None else "orthogonal",
        a,
        b,
        height,
        on,
        cast("DimensionDirection | None", direction),
        cast("DimensionUnits", units),
        precision,
        _positive(size, f"{what}: size", None),
        _positive(thickness, f"{what}: thickness", None),
        _positive(width, f"{what}: width", None),
    )


__all__ = [
    "AREA_NAME",
    "BOARD_LAYER_KINDS",
    "DIMENSION_DIRECTIONS",
    "DIMENSION_UNITS",
    "DRAWING_KEY",
    "DRAWING_LAYER_KINDS",
    "FORBID",
    "MAX_PRECISION",
    "TEXT_SIZE",
    "TEXT_THICKNESS",
    "DimensionSpec",
    "Drawing",
    "GraphicSpec",
    "RuleArea",
    "TextSpec",
]
