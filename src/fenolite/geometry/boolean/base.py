# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The protocol every boolean backend implements, and the coordinate domain they share.

Inputs are polygons read with the non-zero fill rule; every result is a ``tuple[Polygon, ...]`` equal
to its own ``normalize_polygons`` form, with only polygons of non-zero area (an intersection that
only touches along an edge or at a point is the empty tuple).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from fenolite.geometry.errors import OUT_OF_RANGE, GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.shapes import DEFAULT_TOL

Join = Literal["round", "miter", "square"]
COORD_LIMIT = 2**31 - 1
"""Largest absolute coordinate in nm: KiCad stores coordinates as 32-bit integers (S-0010)."""
OPERATIONS = frozenset({"union", "intersection", "difference", "xor", "offset"})

Operand = Polygon | Sequence[Polygon]
"""One polygon or a sequence of polygons (their union under the non-zero rule)."""


def as_polygons(operand: Operand, name: str = "operand") -> tuple[Polygon, ...]:
    if isinstance(operand, Polygon):
        return (operand,)
    polys = tuple(operand)
    for i, poly in enumerate(polys):
        if not isinstance(poly, Polygon):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"{name}[{i}] must be a Polygon, got {poly!r}")
    return polys


def check_domain(polys: Sequence[Polygon], margin: int = 0) -> None:
    """``geometry.out-of-range`` when a coordinate (grown by ``margin``) exceeds ``COORD_LIMIT``."""
    limit = COORD_LIMIT - abs(margin)
    for poly in polys:
        for ring in poly.rings():
            for p in ring:
                if abs(p.x) > limit or abs(p.y) > limit:
                    raise GeometryError(
                        f"coordinate ({p.x}, {p.y}) outside ±{COORD_LIMIT} nm"
                        + (f" once grown by {abs(margin)} nm" if margin else ""),
                        code=OUT_OF_RANGE,
                        points=(p,),
                    )


@runtime_checkable
class BooleanBackend(Protocol):
    name: str
    operations: frozenset[str]

    def union(self, polys: Operand) -> tuple[Polygon, ...]: ...

    def intersection(self, a: Operand, b: Operand) -> tuple[Polygon, ...]: ...

    def difference(self, a: Operand, b: Operand) -> tuple[Polygon, ...]: ...

    def xor(self, a: Operand, b: Operand) -> tuple[Polygon, ...]: ...

    def offset(
        self,
        polys: Operand,
        delta: int,
        *,
        join: Join = "round",
        tol: int = DEFAULT_TOL,
        miter_limit: int = 2,
    ) -> tuple[Polygon, ...]: ...


__all__ = ["COORD_LIMIT", "OPERATIONS", "BooleanBackend", "Join", "Operand", "as_polygons", "check_domain"]
