# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``clipper`` backend: the union of integer polygons through ``pyclipper`` of the ``geo`` extra
(change c0167; capability geometry-boolean-backends, "Clipper union backend").

``pyclipper`` (MIT, embedding Clipper 6.4.2 under the Boost licence, S-0016) is imported only through
``_extra.load_extra``, when the backend is made; without it ``ClipperBackend()`` raises
``BackendUnavailable``. The union runs ``CT_UNION`` with the non-zero fill rule on the integer rings as
they are: integer in, integer out. A vertex of the result is an input vertex or the intersection of two
input edges rounded to the nanometre (Clipper's own rounding). The result is in normal form
(``normalize_polygons``); the other operations raise ``BackendUnavailable``.
"""

from __future__ import annotations

from typing import Any, cast

from fenolite.geometry.boolean._extra import load_extra
from fenolite.geometry.boolean.base import Join, Operand, as_polygons, check_domain
from fenolite.geometry.errors import BackendUnavailable, backend_unavailable
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.shapes import DEFAULT_TOL
from fenolite.geometry.vector import Point


def _ring(contour: Any) -> tuple[Point, ...]:
    return tuple(Point(int(x), int(y)) for x, y in contour)


class ClipperBackend:
    name = "clipper"
    operations = frozenset({"union"})

    def __init__(self) -> None:
        self._clipper: Any = cast(Any, load_extra("pyclipper"))

    def union(self, polys: Operand) -> tuple[Polygon, ...]:
        found = as_polygons(polys, "polys")
        check_domain(found)
        if not found:
            return ()
        pc = self._clipper
        engine = pc.Pyclipper()
        for poly in found:
            for ring in poly.rings():
                engine.AddPath([(p.x, p.y) for p in ring], pc.PT_SUBJECT, True)
        tree = engine.Execute2(pc.CT_UNION, pc.PFT_NONZERO, pc.PFT_NONZERO)
        result: list[Polygon] = []
        pending: list[Any] = list(tree.Childs)
        while pending:
            node = pending.pop(0)
            if node.IsHole:  # pragma: no cover - the children of the root are outer rings
                continue
            holes = [child for child in node.Childs if child.IsHole]
            outer = _ring(node.Contour)
            if len(outer) >= 3:
                result.append(Polygon(outer, tuple(_ring(h.Contour) for h in holes if len(h.Contour) >= 3)))
            for hole in holes:
                pending.extend(hole.Childs)  # islands inside a hole are polygons of their own
        return normalize_polygons(result)

    def _unavailable(self, operation: str, *operands: Operand) -> BackendUnavailable:
        for operand in operands:
            check_domain(as_polygons(operand))
        return backend_unavailable(f"the clipper backend does not give {operation!r}", where=operation)

    def intersection(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        raise self._unavailable("intersection", a, b)

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
        raise backend_unavailable("the clipper backend does not give 'offset'", where="offset")


__all__ = ["ClipperBackend"]
