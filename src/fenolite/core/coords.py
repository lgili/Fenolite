# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Coordinate value objects shared by ``model`` and ``geometry`` (integer nanometres)."""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.units import Nm


@dataclass(frozen=True, slots=True, order=True)
class Point:
    """A position in nanometres."""

    x: Nm
    y: Nm

    def offset(self, dx: Nm, dy: Nm) -> Point:
        return Point(self.x + dx, self.y + dy)


@dataclass(frozen=True, slots=True)
class Size:
    """A width and height in nanometres."""

    w: Nm
    h: Nm


__all__ = ["Point", "Size"]
