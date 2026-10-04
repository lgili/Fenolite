# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Gerber subset that the ``zone-fat9`` probe reads (``docs/formats/kicad/gerber.md``, S-0125).

A test helper only: Fenolite writes no Gerber file and no module of ``src`` reads one. It follows the
coordinate format and unit statements, region statements and the move and draw operations inside them,
and refuses everything it would have to guess.
"""

from __future__ import annotations

import re

FORMAT = "FSLAX46Y46"
"""Leading zeros omitted, absolute coordinates, 4 integer and 6 decimal digits: with millimetres, one
coordinate unit is one nanometre."""
UNIT = "MOMM"
_OPERATION = re.compile(
    r"(?:G0?([123]))?(?:X([+-]?\d+))?(?:Y([+-]?\d+))?(?:I[+-]?\d+)?(?:J[+-]?\d+)?D0?([123])"
)
Extent = tuple[int, int, int, int]


def region_extents(text: str) -> list[Extent]:
    """``(x0, y0, x1, y1)`` in nanometres of every region (``G36`` … ``G37``) of a Gerber text, in file
    order, in the plot's own axes. A text with another coordinate format or unit, or with an arc inside a
    region, raises ``ValueError``."""
    commands = [c.strip().strip("%") for c in text.replace("\n", "").replace("\r", "").split("*")]
    if FORMAT not in commands or UNIT not in commands:
        raise ValueError(f"the helper reads only %{FORMAT}*% plots in millimetres (%{UNIT}*%)")
    extents: list[Extent] = []
    points: list[tuple[int, int]] | None = None
    x = y = 0
    linear = True
    for command in commands:
        if command in ("G01", "G1"):
            linear = True
        elif command in ("G02", "G2", "G03", "G3"):
            linear = False
        elif command == "G36":
            points = []
        elif command == "G37":
            if not points:
                raise ValueError("a region without a point")
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            extents.append((min(xs), min(ys), max(xs), max(ys)))
            points = None
        else:
            match = _OPERATION.fullmatch(command)
            if match is None:
                continue
            mode, new_x, new_y, operation = match.groups()
            if mode is not None:
                linear = mode == "1"
            x = int(new_x) if new_x is not None else x  # coordinates are modal
            y = int(new_y) if new_y is not None else y
            if points is None:
                continue
            if operation == "3":
                raise ValueError("a flash inside a region")
            if operation == "1" and not linear:
                raise ValueError("an arc inside a region is not read")
            points.append((x, y))
    if points is not None:
        raise ValueError("a region is not closed by G37")
    return extents


__all__ = ["FORMAT", "UNIT", "Extent", "region_extents"]
