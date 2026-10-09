# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed paths for the board outline and its cut-outs: ``rect``, ``circle`` and ``slot`` (``docs/dsl.md``,
"Board"; capability design-dsl, "Outline shapes in the DSL"; change c0102).

A path is a sequence whose first element is an ``(x, y)`` pair of lengths in the frame of ``place()`` and
whose other elements are such pairs and ``arc_to(mid, end)`` steps. It closes with a straight edge to its
first point unless its last element ends there. The helpers return such paths, which a script may also
write by hand; ``closed_ring`` reads one for ``board(outline=…)`` and ``cutout()``.

A point that is not an integer number of nanometres (the mid of a rounded corner, a tangent point of a
slot at an angle) is rounded half to even once, with ``math.isqrt``: no float is used. The arc then runs
through three integer points, as KiCad stores it. Rings that cross or touch are judged by the build, not
here: the DSL computes no geometry beyond these points.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from fenolite.core.coords import Point
from fenolite.dsl.errors import DslError
from fenolite.dsl.intents import ArcStep, arc_to
from fenolite.dsl.units import Length, as_nm

PathElement = tuple[Length, Length] | ArcStep
Path = tuple[PathElement, ...]


@dataclass(frozen=True, slots=True)
class RingSpec:
    """One closed ring as a script gave it: its vertices in the written frame (``BOARD_ORIGIN`` added) and,
    for each edge that is an arc, ``(edge index, mid)``; edge i joins vertex i to vertex i + 1 (mod n)."""

    points: tuple[Point, ...]
    arcs: tuple[tuple[int, Point], ...] = ()


def round_root(p: int, q: int) -> int:
    """``sqrt(p / q)`` rounded half to even, for ``p >= 0`` and ``q > 0``, with integer arithmetic."""
    if p < 0 or q <= 0:
        raise ValueError("round_root takes p >= 0 and q > 0")
    # the largest k with (2k - 1)^2 * q <= 4p is floor(sqrt(p / q) + 1/2)
    k = (math.isqrt(4 * p // q) + 1) // 2
    if k > 0 and (2 * k - 1) ** 2 * q == 4 * p and k % 2 == 1:
        k -= 1  # exactly halfway between k - 1 and k: the even one
    return k


def _scaled(a: int, b: int, length2: int) -> int:
    """``a * b / sqrt(length2)`` rounded half to even (the sign is that of ``a * b``)."""
    value = a * b
    rounded = round_root(value * value, length2)
    return rounded if value >= 0 else -rounded


def _positive(value: object, name: str) -> int:
    size = as_nm(value, name=name)
    if size <= 0:
        raise DslError(f"{name} must be positive")
    return size


def _even(value: object, name: str) -> int:
    size = _positive(value, name)
    if size % 2:
        raise DslError(f"{name} must be an even number of nanometres, so its half is exact; got {size} nm")
    return size


def _xy(x: int, y: int) -> tuple[Length, Length]:
    return (Length(x), Length(y))


def rect(x: object, y: object, width: object, height: object, *, radius: object = None) -> Path:
    """The rectangle with the corners ``(x, y)`` and ``(x + width, y + height)``, starting at the left end
    of its top edge and running along the top edge first. With ``radius``, each corner is a quarter arc of
    that radius; its mid is the corner's centre moved by ``radius / √2`` on both axes towards the corner,
    each coordinate rounded half to even. A straight edge of length 0 is left out."""
    x0, y0 = as_nm(x, name="shape.rect(): x"), as_nm(y, name="shape.rect(): y")
    w, h = _positive(width, "shape.rect(): width"), _positive(height, "shape.rect(): height")
    x1, y1 = x0 + w, y0 + h
    if radius is None:
        return (_xy(x0, y0), _xy(x1, y0), _xy(x1, y1), _xy(x0, y1))
    r = _positive(radius, "shape.rect(): radius")
    if 2 * r > min(w, h):
        raise DslError("shape.rect(): radius must be at most half the width and half the height")
    d = round_root(r * r, 2)  # radius / sqrt(2)
    first = (x0 + r, y0)
    path: list[PathElement] = [_xy(*first)]
    at = first

    def line(px: int, py: int) -> None:
        nonlocal at
        if (px, py) != at:
            path.append(_xy(px, py))
            at = (px, py)

    def corner(cx: int, cy: int, sx: int, sy: int, ex: int, ey: int) -> None:
        nonlocal at
        path.append(arc_to(_xy(cx + sx * d, cy + sy * d), _xy(ex, ey)))
        at = (ex, ey)

    line(x1 - r, y0)
    corner(x1 - r, y0 + r, 1, -1, x1, y0 + r)
    line(x1, y1 - r)
    corner(x1 - r, y1 - r, 1, 1, x1 - r, y1)
    line(x0 + r, y1)
    corner(x0 + r, y1 - r, -1, 1, x0, y1 - r)
    line(x0, y0 + r)
    corner(x0 + r, y0 + r, -1, -1, x0 + r, y0)
    return tuple(path)


def circle(x: object, y: object, diameter: object) -> Path:
    """The circle of ``diameter`` centred on ``(x, y)``: the two vertices ``(x + r, y)`` and ``(x − r, y)``
    joined by the arcs through ``(x, y − r)`` and ``(x, y + r)``. ``diameter`` is a positive, even number
    of nanometres, so the circle is exact."""
    cx, cy = as_nm(x, name="shape.circle(): x"), as_nm(y, name="shape.circle(): y")
    r = _even(diameter, "shape.circle(): diameter") // 2
    return (
        _xy(cx + r, cy),
        arc_to(_xy(cx, cy - r), _xy(cx - r, cy)),
        arc_to(_xy(cx, cy + r), _xy(cx + r, cy)),
    )


def _pair(value: object, name: str) -> tuple[int, int]:
    pair = cast("Sequence[object]", value) if isinstance(value, (tuple, list)) else ()
    if len(pair) != 2:
        raise DslError(f"{name}: a point is an (x, y) pair of lengths, not {value!r}")
    return as_nm(pair[0], name=f"{name}.x"), as_nm(pair[1], name=f"{name}.y")


def slot(start: object, end: object, width: object) -> Path:
    """The stadium whose round ends are centred on ``start`` and ``end``, ``width`` wide: its overall
    length is ``|end − start| + width``. With ``u`` the unit vector from ``start`` to ``end``,
    ``n = (−u_y, u_x)`` and ``h = width / 2``, its vertices are ``start − h·n``, ``end − h·n``,
    ``end + h·n`` and ``start + h·n``, joined by a line, the arc through ``end + h·u``, a line and the arc
    through ``start − h·u``. ``width`` is a positive, even number of nanometres; each coordinate is
    rounded half to even once, so a horizontal or vertical slot is exact."""
    sx, sy = _pair(start, "shape.slot(): start")
    ex, ey = _pair(end, "shape.slot(): end")
    half = _even(width, "shape.slot(): width") // 2
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    if length2 == 0:
        raise DslError("shape.slot(): start and end are the same point")
    ux, uy = _scaled(half, dx, length2), _scaled(half, dy, length2)  # h·u
    nx, ny = -uy, ux  # h·n
    return (
        _xy(sx - nx, sy - ny),
        _xy(ex - nx, ey - ny),
        arc_to(_xy(ex + ux, ey + uy), _xy(ex + nx, ey + ny)),
        _xy(sx + nx, sy + ny),
        arc_to(_xy(sx - ux, sy - uy), _xy(sx - nx, sy - ny)),
    )


def _collinear(a: Point, m: Point, b: Point) -> bool:
    return (m.x - a.x) * (b.y - a.y) - (m.y - a.y) * (b.x - a.x) == 0


def closed_ring(path: object, what: str) -> RingSpec:
    """Read one closed path for ``what`` (the call that takes it), or raise ``DslError`` naming the call
    and the index of the element at fault.

    The vertices are the first point and the end point of every other element; each element after the
    first is the edge from the vertex before it to its end. When the last element ends at the first point
    it closes the ring, and that point is not a second vertex; otherwise a straight edge closes it.
    """
    from fenolite.dsl.convert import BOARD_ORIGIN

    def _point(value: object, name: str) -> Point:
        px, py = _pair(value, name)
        return Point(BOARD_ORIGIN.x + px, BOARD_ORIGIN.y + py)

    if isinstance(path, str) or not isinstance(path, Sequence):
        raise DslError(f"{what}: a path is a sequence of (x, y) pairs and arc_to() steps, not {path!r}")
    elements = cast("Sequence[object]", path)
    if not elements:
        raise DslError(f"{what}: the path is empty")
    if isinstance(elements[0], ArcStep) or not isinstance(elements[0], (tuple, list)):
        raise DslError(f"{what}: element 0 must be an (x, y) pair of lengths, not {elements[0]!r}")
    first = _point(cast(object, elements[0]), f"{what}: element 0")
    points: list[Point] = [first]
    arcs: list[tuple[int, Point]] = []
    last = len(elements) - 1
    for index, element in enumerate(elements[1:], start=1):
        here = points[-1]
        if isinstance(element, ArcStep):
            end, mid = element.end, element.mid
            if not isinstance(end, Point) or not isinstance(mid, Point):
                raise DslError(
                    f"{what}: element {index}: the arc step of a ring takes (x, y) pairs of lengths, "
                    "not an anchor in a part's frame"
                )
            if end == here:
                raise DslError(f"{what}: element {index}: the arc step ends on the vertex it starts from")
            if mid in (here, end) or _collinear(here, mid, end):
                raise DslError(
                    f"{what}: element {index}: the arc step has its mid on the line through its two ends"
                )
            arcs.append((len(points) - 1, mid))
        elif isinstance(element, (tuple, list)):
            end = _point(cast(object, element), f"{what}: element {index}")
            if end == here:
                raise DslError(f"{what}: element {index} repeats the vertex before it")
        else:
            raise DslError(
                f"{what}: element {index} must be an (x, y) pair of lengths or an arc_to() step, "
                f"not {element!r}"
            )
        if index == last and end == first:
            break  # the last element closes the ring; its end is not a second vertex
        points.append(end)
    if len(points) < 2 or (len(points) == 2 and not arcs):
        raise DslError(
            f"{what}: a ring needs three vertices, or two joined by an arc; the path gives {len(points)}"
        )
    return RingSpec(tuple(points), tuple(arcs))


def ring_box(ring: RingSpec) -> tuple[int, int, int, int]:
    """The smallest box that holds the vertices of ``ring`` and the mid points of its arcs: what a zone
    declared without an outline takes of the board ring."""
    found = (*ring.points, *(mid for _, mid in ring.arcs))
    return (
        min(p.x for p in found),
        min(p.y for p in found),
        max(p.x for p in found),
        max(p.y for p in found),
    )


__all__ = [
    "Path",
    "PathElement",
    "RingSpec",
    "circle",
    "closed_ring",
    "rect",
    "ring_box",
    "round_root",
    "slot",
]
