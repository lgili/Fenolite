# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable mechanical keys and one origin translation (c0096)."""

from fenolite.core.coords import Point
from fenolite.dsl import BOARD_ORIGIN, Design, to_model
from fenolite.dsl.convert import key_id


def test_order_independent_mechanical_ids() -> None:
    def build(keys: tuple[str, ...]):
        d = Design("m")
        d.board("10mm", "10mm")
        for key in keys:
            d.hole(key, "1mm", "2mm", "0.5mm")
        return to_model(d)

    first, second = build(("a", "b")), build(("b", "a"))
    assert first == second and first.board is not None
    assert first.board.holes[0].id == key_id("hole", "a")
    assert first.board.holes[0].position == Point(BOARD_ORIGIN.x + 1_000_000, BOARD_ORIGIN.y + 2_000_000)
