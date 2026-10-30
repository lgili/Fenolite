# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``teardrops`` child of a pad or via (``docs/formats/kicad/board.md``, "Teardrop settings"; change
c0277): written from ``Teardrop`` in the order the demo boards hold, read back by the import only."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import teardrops as td
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.model.board import Teardrop

DEMO = (
    "(teardrops (best_length_ratio 0.5) (max_length 1) (best_width_ratio 1) (max_width 2) (curved_edges no) "
    "(filter_ratio 0.9) (enabled yes) (allow_two_segments yes) (prefer_zone_connections yes))"
)
FULL = Teardrop(
    max_length=1_000_000, max_width=2_000_000, length_ratio=500_000, width_ratio=1_000_000, curved=False,
    filter_ratio=900_000, two_segments=True, prefer_zones=True,
)  # fmt: skip


def test_demo_settings_round_trip() -> None:
    node = parse(DEMO)
    assert td.project(node) == FULL
    assert dumps(td.emit(FULL), style="compact") == dumps(node, style="compact")


def test_unset_fields_are_left_out() -> None:
    assert dumps(td.emit(Teardrop()), style="compact") == "(teardrops (enabled yes))"
    assert dumps(td.emit(Teardrop(enabled=False, max_width=250_000)), style="compact") == (
        "(teardrops (max_width 0.25) (enabled no))"
    )
    assert td.project(parse("(teardrops (max_length 1))")) == Teardrop(max_length=1_000_000)


@pytest.mark.parametrize(
    "text",
    [
        "(teardrops (enabled maybe))",
        "(teardrops (max_length -1))",
        "(teardrops (max_length 1 2))",
        "(teardrops (curve_points 5))",
        "(teardrops (enabled yes) (enabled no))",
        "(teardrops yes)",
        "(tenting (front yes))",
    ],
)
def test_children_the_model_cannot_hold(text: str) -> None:
    assert td.project(parse(text)) is None


def test_children_in_writer_order() -> None:
    assert [head for head, _, _ in td.CHILDREN] == [
        "best_length_ratio", "max_length", "best_width_ratio", "max_width", "curved_edges", "filter_ratio",
        "enabled", "allow_two_segments", "prefer_zone_connections",
    ]  # fmt: skip
