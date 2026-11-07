# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A rotated footprint keeps its ``point`` children without an angle (c0279 task 4.6).

KiCad 10.0.6 refuses to load a board holding ``(point (at x y θ))``; the footprint below is authored for
this test."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.embed import placed_tree
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sexpr import Node
from fenolite.core.coords import Point
from fenolite.model.board import Side
from fenolite.model.circuit import Component

FOOTPRINT = """(footprint "Marked"
\t(version 20241229)
\t(generator "pcbnew")
\t(layer "F.Cu")
\t(property "Reference" "REF**" (at 0 -2 0) (layer "F.SilkS") (uuid "00000000-0000-4000-8000-000000000011")
\t\t(effects (font (size 1 1) (thickness 0.15))))
\t(property "Value" "Marked" (at 0 2 0) (layer "F.Fab") (uuid "00000000-0000-4000-8000-000000000012")
\t\t(effects (font (size 1 1) (thickness 0.15))))
\t(point (at 1.5 -0.5) (size 2) (layer "F.Fab") (uuid "00000000-0000-4000-8000-000000000013"))
\t(pad "1" smd rect (at -1 0) (size 1 1) (layers "F.Cu" "F.Mask")
\t\t(uuid "00000000-0000-4000-8000-000000000014"))
)
"""
PART = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", value="X")


def _child(tree: Node, head: str) -> Node:
    (found,) = [c for c in tree.children if isinstance(c, Node) and c.name == head]
    return found


@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("rotation", [0, 90_000_000, 270_000_000])
def test_rotated_point_keeps_no_angle(rotation: int, side: Side) -> None:
    defn = read_footprint(FOOTPRINT, library="Authored")
    tree = placed_tree(
        defn, component=PART, at=Point(10_000_000, 5_000_000), rotation=rotation, side=side, key="U1"
    )
    point = _child(tree, "point").find("at")
    assert point is not None
    assert [a.text for a in point.atoms()] == ["1.5", "-0.5" if side == "top" else "0.5"]
    pad = _child(tree, "pad").find("at")
    assert pad is not None
    if rotation:
        assert len(pad.atoms()) == 3  # a pad still takes the absolute angle
