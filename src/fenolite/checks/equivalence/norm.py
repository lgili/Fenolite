# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tolerance and normalisation rules of a design comparison, in integer arithmetic only (capability
design-equivalence, "Tolerances and normalisation").

Lengths are compared per coordinate, never as a distance. Angles are compared on the circle of their
period. A pad's rotation is compared modulo the symmetry of its shape, and an equal-sized oval has the
shape of a circle. Nothing here removes a rotation or
a mirror of a whole board.
"""

from __future__ import annotations

from collections.abc import Iterable
from statistics import median_low

from fenolite.checks.equivalence.model import Tolerances
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, Pad

TURN = 360_000_000
HALF_TURN = 180_000_000
QUARTER_TURN = 90_000_000
TURNED_SHAPES = frozenset({"rect", "oval", "roundrect"})
"""Shapes that a half turn maps onto themselves, and a quarter turn onto the same shape with its two sizes
swapped."""
SPAN_ORDER = ("top", "inner", "bottom")


def normalise(angle: int) -> int:
    """``angle`` in ``[0, 360_000_000)``."""
    return angle % TURN


def angle_distance(a: int, b: int, period: int = TURN) -> int:
    """The distance of two angles on the circle of ``period`` microdegrees."""
    d = (a - b) % period
    return min(d, period - d)


def angles_equal(a: int, b: int, tolerances: Tolerances, period: int = TURN) -> bool:
    return angle_distance(a, b, period) <= tolerances.angle_udeg


def lengths_equal(a: int, b: int, tolerances: Tolerances) -> bool:
    return abs(a - b) <= tolerances.length_nm


def points_equal(a: Point, b: Point, tolerances: Tolerances) -> bool:
    """Both coordinates within the length tolerance; no Euclidean distance is taken."""
    return lengths_equal(a.x, b.x, tolerances) and lengths_equal(a.y, b.y, tolerances)


def sizes_equal(a: Size, b: Size, tolerances: Tolerances) -> bool:
    return lengths_equal(a.w, b.w, tolerances) and lengths_equal(a.h, b.h, tolerances)


def footprint_name(lib_ref: str) -> str:
    """The part of ``lib_ref`` after its last ``:``: a library nickname belongs to a library table, not to
    the board."""
    return lib_ref.rpartition(":")[2]


def pad_symmetry(pad: Pad, tolerances: Tolerances) -> int | None:
    """The period of ``pad``'s rotation: ``None`` when the shape has no rotation (a circle, or an oval of
    two equal sizes), a half turn for ``rect``, ``oval`` and ``roundrect``, a full turn otherwise."""
    if pad.shape == "circle":
        return None
    if pad.shape == "oval" and lengths_equal(pad.size.w, pad.size.h, tolerances):
        return None
    return HALF_TURN if pad.shape in TURNED_SHAPES else TURN


def shape_class(pad: Pad, tolerances: Tolerances) -> str:
    """The shape a pad's copper has: ``circle`` for an ``oval`` whose two sizes are equal within the length
    tolerance (a disc, as KiCad draws it: ``H-K-EQ-OVAL``), else ``pad.shape``. ``pad-shape`` compares the
    classes; the sizes are still compared on their own."""
    if pad.shape == "oval" and lengths_equal(pad.size.w, pad.size.h, tolerances):
        return "circle"
    return pad.shape


def pads_equal_turned(a: Pad, b: Pad, tolerances: Tolerances) -> bool:
    """Whether ``b`` is ``a`` written the other way round: the two sizes swapped and the rotation a quarter
    turn apart, modulo a half turn. Only shapes with that symmetry qualify."""
    if a.shape not in TURNED_SHAPES or b.shape not in TURNED_SHAPES:
        return False
    swapped = Size(b.size.h, b.size.w)
    if not sizes_equal(a.size, swapped, tolerances):
        return False
    return angles_equal(a.rotation, b.rotation + QUARTER_TURN, tolerances, HALF_TURN)


def copper_span(pad: Pad, board: Board) -> frozenset[str] | None:
    """The subset of ``top``, ``inner`` and ``bottom`` that the pad's layers reach, by the ordinals of the
    board's copper layers; ``None`` (unknown) when the board declares one of the names not at all."""
    declared = {layer.name: layer for layer in board.layers}
    ordinals = [layer.ordinal for layer in board.layers if layer.kind == "copper"]
    span: set[str] = set()
    for name in pad.layers:
        layer = declared.get(name)
        if layer is None:
            return None
        if layer.kind != "copper":
            continue
        if layer.ordinal == min(ordinals):
            span.add("top")
        elif layer.ordinal == max(ordinals):
            span.add("bottom")
        else:
            span.add("inner")
    return frozenset(span)


def span_text(span: frozenset[str]) -> str:
    """A copper span as text, top first: ``top,inner,bottom``."""
    return ",".join(name for name in SPAN_ORDER if name in span)


def translation(pairs: Iterable[tuple[Point, Point]]) -> Point:
    """The lower median, per axis, of the position of side ``b`` minus that of side ``a``; ``(0, 0)`` for
    no pair. The median is a value of the data, so no rounding takes place."""
    found = list(pairs)
    if not found:
        return Point(0, 0)
    return Point(median_low(b.x - a.x for a, b in found), median_low(b.y - a.y for a, b in found))


__all__ = [
    "HALF_TURN",
    "QUARTER_TURN",
    "TURN",
    "angle_distance",
    "angles_equal",
    "copper_span",
    "footprint_name",
    "lengths_equal",
    "normalise",
    "pad_symmetry",
    "pads_equal_turned",
    "points_equal",
    "shape_class",
    "sizes_equal",
    "span_text",
    "translation",
]
