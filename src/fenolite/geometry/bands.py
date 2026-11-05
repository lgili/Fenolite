# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The area a stroke of a width covers: the band of a segment or of a three-point arc, round at both ends.

Change c0407: an Altium keep-out drawn as tracks and arcs keeps out a band of the track's width, as KiCad
10.0.6's ``pcb import`` writes it (one rule area per track, ``pcb-records.md``, "Regions and keep-outs").
Integers and ``Fraction`` only: each offset point is the exact point rounded to the nearest nanometre, and
each round edge is polygonised by ``CurvedRing`` within ``tol``.
"""

from __future__ import annotations

from fractions import Fraction
from math import isqrt

from fenolite.geometry.errors import GeometryError
from fenolite.geometry.rings import CurvedRing
from fenolite.geometry.shapes import DEFAULT_TOL, Arc
from fenolite.geometry.vector import Point


def _root(value: Fraction) -> int:
    """``√value`` rounded to the nearest integer, a tie going to even."""
    floor = isqrt(value.numerator // value.denominator)
    half = Fraction(2 * floor + 1, 2)
    if value > half * half or (value == half * half and floor % 2):
        return floor + 1
    return floor


def _offset(x: Fraction, y: Fraction, length2: Fraction, half: Fraction) -> tuple[int, int]:
    """``half · (x, y) / √length2``, each coordinate rounded to the nearest nanometre."""

    def one(v: Fraction) -> int:
        size = _root(half * half * v * v / length2)
        return size if v >= 0 else -size

    return one(x), one(y)


def _moved(p: Point, by: tuple[int, int], sign: int = 1) -> Point:
    return Point(p.x + sign * by[0], p.y + sign * by[1])


def segment_band(a: Point, b: Point, width: int, tol: int = DEFAULT_TOL) -> tuple[Point, ...]:
    """The ring of the band of width ``width`` along ``a``–``b``: two sides and a half circle at each end, in
    positive orientation. ``GeometryError`` for a width that is not above 0 or for ``a == b``."""
    if width <= 0:
        raise GeometryError(f"a band needs a width above 0, not {width}")
    if a == b:
        raise GeometryError("a band needs two distinct ends", points=(a,))
    half = Fraction(width, 2)
    dx, dy = Fraction(b.x - a.x), Fraction(b.y - a.y)
    length2 = dx * dx + dy * dy
    side = _offset(-dy, dx, length2, half)
    ahead = _offset(dx, dy, length2, half)
    points = (_moved(a, side), _moved(b, side), _moved(b, side, -1), _moved(a, side, -1))
    mids = (None, _moved(b, ahead), None, _moved(a, ahead, -1))
    return CurvedRing(points, mids).normalized().polygonize(tol)


def arc_band(start: Point, mid: Point, end: Point, width: int, tol: int = DEFAULT_TOL) -> tuple[Point, ...]:
    """The ring of the band of width ``width`` along the arc ``start``–``mid``–``end``: the arc moved out and
    in by half the width, joined by a half circle at each end, in positive orientation. A straight arc is
    the band of its chord. ``GeometryError`` for a width that is not above 0, a shape the arc refuses, or a
    radius not above half the width (the inner side would fold)."""
    if width <= 0:
        raise GeometryError(f"a band needs a width above 0, not {width}")
    arc = Arc(start, mid, end)
    if arc.centre is None or arc.radius2 is None:
        return segment_band(start, end, width, tol)
    half = Fraction(width, 2)
    if arc.radius2 <= half * half:
        raise GeometryError(
            f"an arc of radius at most half its width {width} nm has no band", points=(start, mid, end)
        )
    cx, cy = arc.centre
    radius2 = arc.radius2
    turn = arc.orientation

    def radial(p: Point) -> tuple[int, int]:
        return _offset(p.x - cx, p.y - cy, radius2, half)

    def ahead(p: Point) -> tuple[int, int]:
        # the direction of travel at p: the radius turned a quarter turn the way the arc runs
        return _offset(-turn * (p.y - cy), turn * (p.x - cx), radius2, half)

    points = (_moved(start, radial(start)), _moved(end, radial(end)), _moved(end, radial(end), -1),
              _moved(start, radial(start), -1))  # fmt: skip
    mids = (_moved(mid, radial(mid)), _moved(end, ahead(end)), _moved(mid, radial(mid), -1),
            _moved(start, ahead(start), -1))  # fmt: skip
    return CurvedRing(points, mids).normalized().polygonize(tol)
