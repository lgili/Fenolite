# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A chamfered pad on the bottom side (change c0277): the mirror about the pad's local X axis turns its top
corners into its bottom ones, so a bottom footprint of chamfered pads is brought back and placed again."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.embed import flip_footprint_tree
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.errors import Issue

PAD = (
    '(footprint "X" (pad "1" smd roundrect (at 1 2) (size 1 1) (layers "F.Cu") (chamfer_ratio 0.25)'
    " (chamfer {})))"
)


@pytest.mark.parametrize(
    ("corners", "flipped"),
    [
        ("top_left", "bottom_left"),
        ("top_left top_right", "bottom_left bottom_right"),
        ("bottom_right", "top_right"),
        ("top_left top_right bottom_left bottom_right", "top_left top_right bottom_left bottom_right"),
    ],
)
def test_corners_mirrored(corners: str, flipped: str) -> None:
    issues: list[Issue] = []
    tree = flip_footprint_tree(parse(PAD.format(corners)), issues)
    assert issues == []
    pad = tree.find("pad")
    assert pad is not None
    assert dumps(pad.find("chamfer"), style="compact") == f"(chamfer {flipped})"  # type: ignore[arg-type]
    assert dumps(pad.find("layers"), style="compact") == '(layers "B.Cu")'  # type: ignore[arg-type]
    twice = flip_footprint_tree(tree, issues)
    assert dumps(twice.find("pad").find("chamfer"), style="compact") == f"(chamfer {corners})"  # type: ignore[union-attr,arg-type]
