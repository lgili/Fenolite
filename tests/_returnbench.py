# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The return-path bench of change c0202: an authored two-layer board, every value round and invented.

``GND`` is filled on ``B.Cu`` in two halves, x 2–28 mm and x 32–58 mm, y 2–38 mm: a gap of 4 mm. On ``F.Cu``:
``SIG1`` runs from x 10 to 50 mm at y 10 mm and crosses the gap; ``SIG2`` runs from x 40 to 59.5 mm at y 20 mm
and leaves the plane 1.5 mm before its end; ``SIG3`` runs from x 10 to 20 mm at y 30 mm over the plane.
``SIG4`` has a via at (15, 35) mm and ``GND`` a via 1 mm from it."""

from __future__ import annotations

import dataclasses

from _groundties import _box, _p, _track, _via, _zone
from _ties import MM, TieBoard

from fenolite.model.board import ZoneFill
from fenolite.model.design import Design

GAP = 4 * MM
EDGE = 3 * MM // 2


def bench() -> Design:
    board_builder = TieBoard()
    gnd = board_builder.net("GND")
    sig = [board_builder.net(f"SIG{i}") for i in range(1, 5)]
    design = board_builder.build()
    board = design.board
    assert board is not None
    left = _zone(1, gnd, _box(2, 2, 28, 38))
    plane = dataclasses.replace(
        left,
        layers=("B.Cu",),
        outline=_box(2, 2, 58, 38),
        fills=(ZoneFill("B.Cu", _box(2, 2, 28, 38)), ZoneFill("B.Cu", _box(32, 2, 58, 38))),
    )
    tracks = (
        _track(1, sig[0], _p(10, 10), _p(50, 10)),
        _track(2, sig[1], _p(40, 20), _p(59.5, 20)),
        _track(3, sig[2], _p(10, 30), _p(20, 30)),
    )
    vias = (_via(1, sig[3], _p(15, 35)), _via(2, gnd, _p(16, 35)))
    return dataclasses.replace(
        design, board=dataclasses.replace(board, tracks=tracks, vias=vias, zones=(plane,))
    )


__all__ = ["EDGE", "GAP", "bench"]
