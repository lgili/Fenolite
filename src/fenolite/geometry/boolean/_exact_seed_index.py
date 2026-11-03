# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact closed-Y interval selection for formal infinitesimal seeds (c0332)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.geometry.boolean._exact_noding import Budget, ResourceLimit, Segment
from fenolite.geometry.errors import GeometryError


@dataclass(frozen=True, slots=True)
class _Node:
    center: Fraction
    low: tuple[int, ...]
    high: tuple[int, ...]
    left: _Node | None
    right: _Node | None


class ClosedYIndex:
    """One operation owns the index AND Budget; queries cannot supply a fresh counter."""

    def __init__(self, source: Sequence[Segment], budget: Budget) -> None:
        self._budget = budget
        self._nodes = 0
        bounds: list[tuple[int, int]] = []
        for segment in source:
            budget.visit(1)
            if any(type(c) is not int for p in (segment.a, segment.b) for c in p):
                raise GeometryError("exact winding index requires integer source coordinates")
            for value in (segment.a[1], segment.b[1]):
                budget.coordinate(Fraction(value))
            bounds.append((min(segment.a[1], segment.b[1]), max(segment.a[1], segment.b[1])))
        self._bounds = tuple(bounds)
        self._root = self._build(tuple(range(len(source))))
        budget.check()

    def _build(self, ids: tuple[int, ...]) -> _Node | None:
        if not ids:
            return None
        self._budget.visit(len(ids) + 1)  # partitioned source intervals and allocated node
        if self._nodes >= self._budget.limits.nodes:
            raise ResourceLimit("exact winding index tree-node budget exceeded")
        self._nodes += 1
        endpoints = sorted(value for i in ids for value in self._bounds[i])
        center = Fraction(endpoints[len(ids) - 1] + endpoints[len(ids)], 2)
        self._budget.coordinate(center)
        left: list[int] = []
        right: list[int] = []
        spanning: list[int] = []
        for i in ids:
            low, high = self._bounds[i]
            if high < center:
                left.append(i)
            elif low > center:
                right.append(i)
            else:
                spanning.append(i)
        # A gap may have no spanners; each strict child still owns at most half
        # the endpoints and is strictly smaller, including duplicate endpoints.
        if len(left) >= len(ids) or len(right) >= len(ids):
            raise GeometryError("exact winding interval partition did not shrink")
        return _Node(
            center,
            tuple(sorted(spanning, key=lambda i: (self._bounds[i][0], i))),
            tuple(sorted(spanning, key=lambda i: (-self._bounds[i][1], i))),
            self._build(tuple(left)),
            self._build(tuple(right)),
        )

    def query(self, y: object) -> tuple[int, ...]:
        if not isinstance(y, Fraction):
            raise GeometryError("exact winding index requires a rational seed coordinate")
        self._budget.coordinate(y)
        found: list[int] = []
        node = self._root
        while node is not None:
            self._budget.visit(1)
            if y == node.center:
                for i in node.low:
                    self._budget.visit(1)
                    found.append(i)
                break
            if y < node.center:
                for i in node.low:
                    self._budget.visit(1)
                    if self._bounds[i][0] > y:
                        break
                    found.append(i)
                node = node.left
            else:
                for i in node.high:
                    self._budget.visit(1)
                    if self._bounds[i][1] < y:
                        break
                    found.append(i)
                node = node.right
        found.sort()
        self._budget.check()
        return tuple(found)
