# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``clipper`` backend: boolean operations and offsets of integer polygons through ``pyclipper`` of the
``geo`` extra (change c0167 for the union; change c0215 for the other operations; capability
geometry-boolean-backends, "Clipper backend").

``pyclipper`` (MIT, embedding Clipper 6.4.2 under the Boost licence, S-0016) is imported only through
``_extra.load_extra``, when the backend is made; without it ``ClipperBackend()`` raises
``BackendUnavailable``. Every operation reads its operands with the non-zero fill rule on the integer rings
as they are: integer in, integer out. A vertex of a boolean result is an input vertex or the intersection
of two input edges rounded to the nanometre (Clipper's own rounding). An offset with round joins places the
vertices of each arc on the arc, so its chords lie at most ``tol`` inside it (Clipper's arc tolerance).
Every result is in normal form (``normalize_polygons``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from fenolite.geometry.boolean._extra import load_extra
from fenolite.geometry.boolean.base import COORD_LIMIT, Join, Operand, as_polygons, check_domain
from fenolite.geometry.errors import OUT_OF_RANGE, GeometryError
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.shapes import DEFAULT_TOL
from fenolite.geometry.vector import Point


def _ring(contour: Any) -> tuple[Point, ...]:
    return tuple(Point(int(x), int(y)) for x, y in contour)


def _polygons(tree: Any) -> tuple[Polygon, ...]:
    """The polygons of a Clipper ``PolyTree``: each outer ring with its holes; an island inside a hole is a
    polygon of its own. Rings of fewer than three vertices are left out."""
    result: list[Polygon] = []
    pending: list[Any] = list(tree.Childs)
    while pending:
        node = pending.pop(0)
        if node.IsHole:  # pragma: no cover - the children of the root are outer rings
            continue
        holes = [child for child in node.Childs if child.IsHole]
        outer = _ring(node.Contour)
        if len(outer) >= 3:
            try:
                result.append(Polygon(outer, tuple(_ring(h.Contour) for h in holes if len(h.Contour) >= 3)))
            except GeometryError:
                pass  # a ring that Clipper's rounding left without area
        for hole in holes:
            pending.extend(hole.Childs)  # islands inside a hole are polygons of their own
    return normalize_polygons(result)


class ClipperBackend:
    name = "clipper"
    operations = frozenset({"union", "intersection", "difference", "xor", "offset"})

    def __init__(self) -> None:
        self._clipper: Any = cast(Any, load_extra("pyclipper"))

    def _execute(self, kind: str, subject: Sequence[Polygon], clip: Sequence[Polygon]) -> tuple[Polygon, ...]:
        pc = self._clipper
        engine = pc.Pyclipper()
        for poly in subject:
            for ring in poly.rings():
                engine.AddPath([(p.x, p.y) for p in ring], pc.PT_SUBJECT, True)
        for poly in clip:
            for ring in poly.rings():
                engine.AddPath([(p.x, p.y) for p in ring], pc.PT_CLIP, True)
        tree = engine.Execute2(getattr(pc, kind), pc.PFT_NONZERO, pc.PFT_NONZERO)
        return _polygons(tree)

    def union(self, polys: Operand) -> tuple[Polygon, ...]:
        found = as_polygons(polys, "polys")
        check_domain(found)
        if not found:
            return ()
        return self._execute("CT_UNION", found, ())

    def intersection(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        first, second = as_polygons(a, "a"), as_polygons(b, "b")
        check_domain((*first, *second))
        if not first or not second:
            return ()
        return self._execute("CT_INTERSECTION", first, second)

    def difference(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        first, second = as_polygons(a, "a"), as_polygons(b, "b")
        check_domain((*first, *second))
        if not first:
            return ()
        if not second:
            return self._execute("CT_UNION", first, ())
        return self._execute("CT_DIFFERENCE", first, second)

    def xor(self, a: Operand, b: Operand) -> tuple[Polygon, ...]:
        first, second = as_polygons(a, "a"), as_polygons(b, "b")
        check_domain((*first, *second))
        if not first and not second:
            return ()
        return self._execute("CT_XOR", first, second)

    def _offsetter(self, join: Join, tol: int, miter_limit: int) -> tuple[Any, Any]:
        pc = self._clipper
        if tol < 1:
            raise ValueError(f"the arc tolerance of an offset is at least 1 nm, got {tol}")
        joins = {"round": pc.JT_ROUND, "miter": pc.JT_MITER, "square": pc.JT_SQUARE}
        return pc.PyclipperOffset(miter_limit, tol), joins[join]

    def offset(
        self,
        polys: Operand,
        delta: int,
        *,
        join: Join = "round",
        tol: int = DEFAULT_TOL,
        miter_limit: int = 2,
    ) -> tuple[Polygon, ...]:
        """The polygons grown by ``delta`` (shrunk when negative), each ring offset by Clipper with ``join``
        at its convex corners; ``tol`` is the largest distance between an arc of a round join and its
        chords."""
        found = as_polygons(polys, "polys")
        check_domain(found, margin=abs(delta) + tol)
        if not found:
            return ()
        offsetter, kind = self._offsetter(join, tol, miter_limit)
        for poly in found:
            for ring in poly.rings():
                offsetter.AddPath([(p.x, p.y) for p in ring], kind, self._clipper.ET_CLOSEDPOLYGON)
        return _polygons(offsetter.Execute2(delta))

    def stroke(
        self, paths: Sequence[Sequence[Point]], delta: int, *, tol: int = DEFAULT_TOL
    ) -> tuple[Polygon, ...]:
        """The points within ``delta`` of the open polylines ``paths``, with round ends and round joins: a
        path of one point is a disc. ``tol`` is as for ``offset``."""
        if delta < 1:
            raise ValueError(f"a stroke needs a half-width of at least 1 nm, got {delta}")
        rings = [tuple(path) for path in paths if path]
        limit = COORD_LIMIT - delta - tol
        for ring in rings:
            for p in ring:
                if abs(p.x) > limit or abs(p.y) > limit:
                    raise GeometryError(
                        f"coordinate ({p.x}, {p.y}) outside ±{COORD_LIMIT} nm once grown by {delta + tol} nm",
                        code=OUT_OF_RANGE,
                        points=(p,),
                    )
        if not rings:
            return ()
        offsetter, kind = self._offsetter("round", tol, 2)
        for ring in rings:
            offsetter.AddPath([(p.x, p.y) for p in ring], kind, self._clipper.ET_OPENROUND)
        return _polygons(offsetter.Execute2(delta))


__all__ = ["ClipperBackend"]
