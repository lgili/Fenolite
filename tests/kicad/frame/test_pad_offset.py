# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The offset of a pad's drill moves the pad's copper and not its hole (``H-G-FRAME-OFFSET``; capability
kicad-oracle, "Pad shape offset passes the oracle"; change c0068).

KiCad's verdict on each row of ``_offsetbench`` is pinned first, on its own, so the reproduction of the
v0.1 defect stays in the suite: a frame that moved the hole instead of the copper would report nothing on
``towards`` and ``turned`` and a false ``copper.clearance`` on ``away``.
"""

from __future__ import annotations

import _offsetbench as ob
import pytest
from _probes import major, run

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("row", ob.ROWS, ids=[row.name for row in ob.ROWS])
def test_kicad_moves_the_copper(row: ob.Row) -> None:
    """KiCad reports the pad against the track exactly when the MOVED copper is closer than 0.2 mm."""
    assert ob.kicad_verdict(row) == row.expected
    assert (row.moved < ob.CLEARANCE) == (row.expected == "clearance")


def test_three_rows_tell_the_two_readings_apart() -> None:
    """With the copper left in place (the hole moved instead) three of the four rows give the opposite
    verdict; ``short-of`` is clean under both readings and bounds the distance the copper moves."""
    apart = [row.name for row in ob.ROWS if (row.gap < ob.CLEARANCE) != (row.moved < ob.CLEARANCE)]
    assert apart == ["towards", "away", "turned"]


@pytest.mark.parametrize("row", ob.ROWS, ids=[row.name for row in ob.ROWS])
def test_check_copper_agrees_with_kicad(row: ob.Row) -> None:
    """Scenario "Offset rows agree on both majors"."""
    assert ob.fenolite_verdict(major(), row) == ob.kicad_verdict(row)


def test_the_hole_stays_at_the_pad_position() -> None:
    """The written board keeps each pad's ``at``; the frame puts the hole there."""
    bench = ob.offset_bench(major())
    pads = [pad for pad in board_pads(read_board(bench.files[ob.BOARD], file=ob.BOARD)) if pad.drill]
    assert len(pads) == len(ob.ROWS)
    assert all(pad.hole == (pad.position,) for pad in pads)


def test_probe_pad_offset() -> None:
    assert run("pcb-frame-pad-offset") == "equal"
