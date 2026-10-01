# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stdlib fallback backend: the intersection of two convex hole-free polygons, nothing else.

Every other operation or input raises ``BackendUnavailable`` (install the ``geo`` extra) instead of
returning an approximate result.
"""

from __future__ import annotations

from fenolite.geometry.boolean.base import Join, Operand, as_polygons, check_domain
from fenolite.geometry.errors import BackendUnavailable, backend_unavailable
from fenolite.geometry.polygon import Polygon, clip_convex, normalize_polygons
from fenolite.geometry.shapes import DEFAULT_TOL


def _single_convex(operand: Operand, name: str) -> Polygon:
    polys = as_polygons(operand, name)
    if len(polys) != 1 or not polys[0].is_convex():
        raise backend_unavailable(
            f"the fallback intersects single convex hole-free polygons only; operand {name} is not one",
            where=name,
        )
    return polys[0]


class FallbackBackend:
    name = "fallback"
    operations = frozenset({"intersection"})

    def intersection(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        first, second = as_polygons(a, "a"), as_polygons(b, "b")
        check_domain(first + second)
        result = clip_convex(_single_convex(first, "a"), _single_convex(second, "b"))
        return () if result is None else normalize_polygons((result,))

    def _unavailable(self, operation: str, *operands: Operand) -> BackendUnavailable:
        for operand in operands:
            check_domain(as_polygons(operand))
        return backend_unavailable(f"operation {operation!r} needs the geo extra", where=operation)

    def union(self, polys: Operand) -> tuple[Polygon, ...]:
        raise self._unavailable("union", polys)

    def difference(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        raise self._unavailable("difference", a, b)

    def xor(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        raise self._unavailable("xor", a, b)

    def offset(
        self,
        polys: Operand,
        delta: int,
        *,
        join: Join = "round",
        tol: int = DEFAULT_TOL,
        miter_limit: int = 2,
    ) -> tuple[Polygon, ...]:
        check_domain(as_polygons(polys), margin=abs(delta) + tol)
        raise backend_unavailable("operation 'offset' needs the geo extra", where="offset")


__all__ = ["FallbackBackend"]
