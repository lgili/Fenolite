# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer vectors: ``Point`` and ``Size`` come from ``fenolite.core.coords``; ``Vec`` is a displacement.

The kernel adds free functions instead of operators so that ``core`` stays unchanged. Every function
here is exact: inputs and results are integer nanometres (products are integer nm²).
"""

from __future__ import annotations

from fenolite.core.coords import Point, Size

Vec = Point
"""A displacement in nanometres (same class as ``Point``)."""


def require_point(p: Point, name: str) -> None:
    """Raise ``TypeError`` naming ``name`` unless ``p`` is a ``Point`` with ``int`` coordinates."""
    if not isinstance(p, Point) or type(p.x) is not int or type(p.y) is not int:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{name} must be a Point with int nanometre coordinates, got {p!r}")


def require_int(value: int, name: str) -> None:
    """Raise ``TypeError`` naming ``name`` unless ``value`` is an ``int`` (``bool`` is refused)."""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int, got {type(value).__name__} {value!r}")


def add(p: Point, v: Vec) -> Point:
    require_point(p, "p")
    require_point(v, "v")
    return Point(p.x + v.x, p.y + v.y)


def sub(a: Point, b: Point) -> Vec:
    require_point(a, "a")
    require_point(b, "b")
    return Point(a.x - b.x, a.y - b.y)


def neg(v: Vec) -> Vec:
    require_point(v, "v")
    return Point(-v.x, -v.y)


def dot(a: Vec, b: Vec) -> int:
    require_point(a, "a")
    require_point(b, "b")
    return a.x * b.x + a.y * b.y


def cross(a: Vec, b: Vec) -> int:
    """``a.x·b.y − a.y·b.x``; positive when ``b`` is a positive turn from ``a`` (see ``orient2d``)."""
    require_point(a, "a")
    require_point(b, "b")
    return a.x * b.y - a.y * b.x


def norm2(v: Vec) -> int:
    require_point(v, "v")
    return v.x * v.x + v.y * v.y


__all__ = [
    "Point",
    "Size",
    "Vec",
    "add",
    "cross",
    "dot",
    "neg",
    "norm2",
    "require_int",
    "require_point",
    "sub",
]
