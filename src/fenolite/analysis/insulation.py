# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The distance through the laminate between copper of two nets on two layers (capability
board-analyses, "Insulation between layers"; ``docs/analyses.md``, "Insulation between layers";
``H-G-AN-INSUL``).

For copper on a layer ``U`` above a layer ``L`` the distance is ``√(g² + h²)``: ``g`` the smallest gap of
the shapes in plan view, measured as the gaps on one layer are, and ``h`` the depth of the top face of
``L`` less the depth of the bottom face of ``U``. Copper on a layer between the two is not considered.

The depths come from the stack-up of the board and from nowhere else: Fenolite assumes no thickness.
``layer_depths`` reads them through ``Stackup.depth``, the one definition of a depth (change c0101); on a
model without that method it returns ``None`` and every caller reports the stack-up as a missing input.
``insulation_between`` takes the depths as an argument.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fenolite.analysis.copper import CopperShape, copper_layers
from fenolite.analysis.report import Measure
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import (
    BBox,
    ceil_sqrt,
    floor_sqrt,
    thick_bbox,
    thick_gap_floor,
    thick_touch,
    thick_witness,
)
from fenolite.model.board import Board, Stackup

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-INSUL",))
"""``INFERRED``: no tool measures a distance between layers (``H-K-AN-LAYERS``)."""
Depths = Mapping[str, tuple[Nm, Nm]]
"""Per copper layer, the depths of its top face and of its bottom face below the top of the stack-up."""


def _box_gap(a: BBox, b: BBox) -> int:
    """A lower bound of the distance of two boxes: the larger of their separations along the axes."""
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0)
    return max(dx, dy)


def plan_gap(first: Sequence[CopperShape], second: Sequence[CopperShape], layer: str) -> Measure | None:
    """The smallest gap in plan view between the shapes of two nets, as an interval with its witness:
    ``low`` is ``thick_gap_floor`` less the bands of the two items, ``high`` that floor plus 1 plus the
    bands. ``layer`` names the measure."""
    best: tuple[int, int, CopperShape, CopperShape] | None = None  # low, gap, a, b
    boxes_b = [thick_bbox(item.shape) for item in second]
    for one in first:
        box_a = thick_bbox(one.shape)
        for other, box_b in zip(second, boxes_b, strict=True):
            bands = one.band + other.band
            if best is not None and _box_gap(box_a, box_b) - bands > best[0]:
                continue
            gap = 0 if thick_touch(one.shape, other.shape) else thick_gap_floor(one.shape, other.shape)
            low = max(0, gap - bands)
            if best is None or (low, gap) < (best[0], best[1]):
                best = (low, gap, one, other)
    if best is None:
        return None
    low, gap, one, other = best
    touching = gap == 0 and thick_touch(one.shape, other.shape)
    high = 0 if touching else gap + 1 + one.band + other.band
    return Measure(low, high, layer, (thick_witness(one.shape, other.shape),), (one.where, other.where))


def layer_depths(board: Board) -> Depths | None:
    """The depths of the two faces of each copper layer that has an entry in the stack-up, by
    ``Stackup.depth``; ``None`` without a stack-up, or on a model whose stack-up has no ``depth``."""
    stackup = board.stackup
    depth = getattr(stackup, "depth", None)
    if stackup is None or depth is None:
        return None
    found: dict[str, tuple[Nm, Nm]] = {}
    for layer in copper_layers(board):
        try:
            top, bottom = depth(layer)
        except KeyError:
            continue
        found[layer] = (top, bottom)
    return found


def _sheets(stackup: Stackup | None, upper: str, lower: str) -> int | None:
    """The count of dielectric entries strictly between the first entries of the two names."""
    if stackup is None:
        return None
    names = [entry.name for entry in stackup.layers]
    if upper not in names or lower not in names:
        return None
    first, second = sorted((names.index(upper), names.index(lower)))
    return sum(1 for entry in stackup.layers[first + 1 : second] if entry.kind == "dielectric")


def insulation_between(
    shapes_a: Sequence[CopperShape],
    shapes_b: Sequence[CopperShape],
    *,
    depths: Depths,
    stackup: Stackup | None,
) -> tuple[Measure | None, int | None]:
    """The shortest distance through the laminate between the shapes of two nets on two different
    copper layers, and the count of dielectric entries between those two layers. ``(None, None)`` when no
    two layers with a depth carry copper of one net each."""
    by_layer_a: dict[str, list[CopperShape]] = {}
    by_layer_b: dict[str, list[CopperShape]] = {}
    for found, shapes in ((by_layer_a, shapes_a), (by_layer_b, shapes_b)):
        for shape in shapes:
            if shape.layer in depths:
                found.setdefault(shape.layer, []).append(shape)
    order = sorted(depths, key=lambda name: depths[name])
    best: tuple[int, Measure, str, str] | None = None
    for i, upper in enumerate(order):
        for lower in order[i + 1 :]:
            height = depths[lower][0] - depths[upper][1]
            if height < 0:
                continue
            for first, second in ((by_layer_a, by_layer_b), (by_layer_b, by_layer_a)):
                if upper not in first or lower not in second:
                    continue
                gap = plan_gap(first[upper], second[lower], f"{upper}/{lower}")
                if gap is None or gap.high is None:
                    continue
                low = floor_sqrt(gap.low * gap.low + height * height)
                if best is not None and low >= best[0]:
                    continue
                high = ceil_sqrt(gap.high * gap.high + height * height)
                items = gap.items if first is by_layer_a else (gap.items[1], gap.items[0])
                best = (low, Measure(low, high, gap.layer, gap.points, items), upper, lower)
    if best is None:
        return None, None
    return best[1], _sheets(stackup, best[2], best[3])


__all__ = ["EVIDENCE", "Depths", "insulation_between", "layer_depths", "plan_gap"]
