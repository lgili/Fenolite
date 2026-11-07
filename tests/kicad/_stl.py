# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the KiCad model-pose oracles of change c0423 share: the vertices of a ``kicad-cli pcb export stl``
file, and turns written out independently of ``fenolite.convert.models`` so that the oracle checks the
product against an independent prediction."""

from __future__ import annotations

import math
import struct
from collections.abc import Iterable, Sequence

Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
FLIP: Matrix = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))
"""A half turn about X: KiCad's and Altium's flip of a bottom-side part."""


def vertices(data: bytes) -> list[Vector]:
    """The distinct vertices of an STL file, ASCII (9.0) or binary (10.0), in mm, keyed to 0.1 µm."""
    points: list[Vector] = []
    if data[:5] == b"solid" and b"facet" in data[:400]:
        for line in data.decode("ascii").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                points.append((float(parts[1]), float(parts[2]), float(parts[3])))
    else:
        (count,) = struct.unpack_from("<I", data, 80)
        for index in range(count):
            for corner in range(3):
                x, y, z = struct.unpack_from("<3f", data, 84 + index * 50 + 12 + 12 * corner)
                points.append((x, y, z))
    unique: dict[tuple[int, int, int], Vector] = {}
    for point in points:
        unique.setdefault((round(point[0] * 1e4), round(point[1] * 1e4), round(point[2] * 1e4)), point)
    return list(unique.values())


def without_corners(points: Iterable[Vector], corners: Iterable[tuple[float, float]]) -> list[Vector]:
    """``points`` less those on a board corner (the board body that 9.0.9 exports with every model)."""
    keys = {(round(x, 3), round(y, 3)) for x, y in corners}
    return [p for p in points if (round(p[0], 3), round(p[1], 3)) not in keys]


def turn(axis: int, degrees: float) -> Matrix:
    """The turn about ``axis`` (0 x, 1 y, 2 z) by ``degrees``, counter-clockwise seen from the axis."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    if axis == 0:
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == 1:
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def times(a: Matrix, b: Matrix) -> Matrix:
    rows = [tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)]
    return (rows[0], rows[1], rows[2])  # type: ignore[return-value]


def apply(m: Matrix, p: Sequence[float]) -> Vector:
    x, y, z = (sum(m[i][k] * p[k] for k in range(3)) for i in range(3))
    return (x, y, z)


def plus(a: Sequence[float], b: Sequence[float]) -> Vector:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def worst(expected: Sequence[Vector], found: Sequence[Vector]) -> float:
    """The largest distance from a point of either set to the nearest of the other; infinite when the
    counts differ."""
    if len(expected) != len(found) or not expected:
        return math.inf
    one = max(min(math.dist(p, q) for q in found) for p in expected)
    two = max(min(math.dist(p, q) for q in expected) for p in found)
    return max(one, two)


__all__ = [
    "FLIP",
    "IDENTITY",
    "Matrix",
    "Vector",
    "apply",
    "plus",
    "times",
    "turn",
    "vertices",
    "without_corners",
    "worst",
]
