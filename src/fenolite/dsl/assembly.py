# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Assembly and test features of a script: the library name of their generated parts and the outline of
the clear area around a fiducial or a tooling hole (capability design-dsl, "Fiducials in the DSL";
change c0118).

This module holds what needs no other change: the generated footprints and symbols, and the calls
``Design.fiducial``, ``Design.test_point`` and ``Design.tooling_hole``, are built on the generated
definitions and the keep-out call of changes c0102 and c0103 and come with them.
"""

from __future__ import annotations

import math

from fenolite.core.coords import Point
from fenolite.core.units import Nm

ASSEMBLY_LIBRARY = "Fenolite_Assembly"
"""The library of the generated fiducial, test-point and tooling-hole footprints and symbols."""


def clear_outline(x: Nm, y: Nm, diameter: Nm) -> tuple[Point, ...]:
    """The octagon that stands for the clear area of ``diameter`` around ``(x, y)``: a keep-out outline
    holds points only.

    Its apothem is ``a = ⌈diameter / 2⌉`` and its corner offset ``b = ⌈√(2a²)⌉ − a``, with vertices
    ``(x ± b, y ± a)`` and ``(x ± a, y ± b)`` in drawing order. It contains the circle of ``diameter``:
    every edge is at least ``diameter / 2`` from the centre. Its corners reach about 8.2 % further out
    than the circle, and its area is about 5.5 % larger. Integers only (``math.isqrt``).
    """
    if type(diameter) is not int or diameter <= 0:
        raise ValueError(
            f"the diameter of a clear area is a positive integer of nanometres, got {diameter!r}"
        )
    a = -(-diameter // 2)
    root = math.isqrt(2 * a * a)
    b = root + (root * root < 2 * a * a) - a
    return (
        Point(x + b, y - a), Point(x + a, y - b), Point(x + a, y + b), Point(x + b, y + a),
        Point(x - b, y + a), Point(x - a, y + b), Point(x - a, y - b), Point(x - b, y - a),
    )  # fmt: skip


__all__ = ["ASSEMBLY_LIBRARY", "clear_outline"]
