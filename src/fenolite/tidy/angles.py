# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kinds of turns and joints of tracks, judged exactly on integer vectors (capability copper-tidy, "Turn
costs" and "Style report"; ``docs/copper.md``, "Copper tidy").

A turn is the change of direction from ``u`` (the way in) to ``v`` (the way out). Its kind is ``straight``
(no change), ``45`` (a 45° turn: an inner angle of 135°), ``90``, ``acute`` (a turn above 90°: an inner
angle below 90°, a U-turn included) or ``other`` (a turn below 90° that is not 45°)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.coords import Point

TURN_WEIGHTS: Mapping[str, int] = MappingProxyType({"straight": 0, "45": 1, "other": 2, "90": 3, "acute": 4})
"""The weight of a turn of each kind. A new shape never holds an ``acute`` one; a run as found may."""


def vector(a: Point, b: Point) -> tuple[int, int]:
    """The vector from ``a`` to ``b``."""
    return (b.x - a.x, b.y - a.y)


def turn_kind(u: tuple[int, int], v: tuple[int, int]) -> str:
    """The kind of the turn from direction ``u`` to direction ``v`` (both non-zero)."""
    dot = u[0] * v[0] + u[1] * v[1]
    cross = u[0] * v[1] - u[1] * v[0]
    if dot < 0:
        return "acute"
    if dot == 0:
        return "90"
    if cross == 0:
        return "straight"
    return "45" if abs(cross) == dot else "other"


def joint_kind(a: tuple[int, int], b: tuple[int, int]) -> str:
    """The kind of the joint of two tracks that leave one point along ``a`` and ``b``: the turn from the
    way in along the first (``-a``) to the way out along the second."""
    return turn_kind((-a[0], -a[1]), b)


__all__ = ["TURN_WEIGHTS", "joint_kind", "turn_kind", "vector"]
