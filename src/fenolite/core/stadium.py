# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ring of a milled slot: a stadium of four vertices and two half-circle arcs (change c0167; capability
design-model, "Board slots").

``stadium(center, length, width, rotation)`` takes the overall ``length`` (both round ends included), the
``width`` (positive and even, so its half is exact; ``length > width``) and the ``rotation`` of the length's
axis in microdegrees, in the sense of ``Transform.placement`` (taken modulo 180°). With ``u`` the unit axis
``(cos θ, −sin θ)`` (Y down), ``n = (−u_y, u_x)``, ``h = (length − width) / 2`` and ``r = width / 2``, the
vertices are ``center − h·u − r·n``, ``center + h·u − r·n``, ``center + h·u + r·n`` and
``center − h·u + r·n``: edge 0 a line, edge 1 the arc through ``center + (length / 2)·u``, edge 2 a line and
edge 3 the arc through ``center − (length / 2)·u``, the order of ``dsl.shape.slot``. Each coordinate is
rounded half to even once from the fixed-point cosine of ``core.trig``; at a multiple of 90° the ring is
exact. The DSL, the backends and the checks all take the ring from here.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.core.trig import HALF_TURN, ONE, cos_sin_fixed
from fenolite.core.units import round_half_even_div

ARC_EDGES = (1, 3)
"""The edges of a stadium that are arcs; ``Stadium.mids`` holds their mids in this order."""


@dataclass(frozen=True, slots=True)
class Stadium:
    """The four vertices of a slot's ring and the mids of its two arcs (edges 1 and 3)."""

    points: tuple[Point, Point, Point, Point]
    mids: tuple[Point, Point]

    def arcs(self) -> tuple[tuple[int, Point], ...]:
        """``(edge, mid)`` of each arc, in edge order."""
        return tuple(zip(ARC_EDGES, self.mids, strict=True))


def check_size(length: int, width: int) -> str | None:
    """Why ``length`` × ``width`` is not a slot, or ``None``: the width must be a positive, even number of
    nanometres and the length must exceed it (a slot as long as wide is a circle)."""
    if type(length) is not int or type(width) is not int:
        return "the length and the width must be integer nanometres"
    if width <= 0:
        return f"the width must be positive, not {width} nm"
    if width % 2:
        return f"the width must be an even number of nanometres, so its half is exact; got {width} nm"
    if length <= width:
        return f"the length ({length} nm) must exceed the width ({width} nm); a round hole is a circle"
    return None


def stadium(center: Point, length: int, width: int, rotation: int) -> Stadium:
    """The ring of the slot of ``length`` × ``width`` about ``center``, its axis turned by ``rotation``
    microdegrees. ``ValueError`` when ``check_size`` refuses the size."""
    problem = check_size(length, width)
    if problem is not None:
        raise ValueError(problem)
    if type(rotation) is not int:
        raise TypeError(f"rotation must be an int, got {rotation!r}")
    c, s = cos_sin_fixed(rotation % HALF_TURN)
    span, scale = length - width, 2 * ONE

    def at(a: int, b: int) -> Point:
        # center + a·h·u + b·r·n in units of 1 / (2·ONE): u = (C, −S) / ONE and n = (S, C) / ONE
        x = a * span * c + b * width * s
        y = -a * span * s + b * width * c
        return Point(center.x + round_half_even_div(x, scale), center.y + round_half_even_div(y, scale))

    def tip(a: int) -> Point:
        return Point(
            center.x + round_half_even_div(a * length * c, scale),
            center.y + round_half_even_div(-a * length * s, scale),
        )

    return Stadium((at(-1, -1), at(1, -1), at(1, 1), at(-1, 1)), (tip(1), tip(-1)))


__all__ = ["ARC_EDGES", "Stadium", "check_size", "stadium"]
