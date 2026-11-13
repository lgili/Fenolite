# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board shape drawn on a mechanical layer and its comparison (change c0497, D6), on the authored
``drawn`` board (``board_ops``). The gates are opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import drawing
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import cutout_region
from tests.unit.backends.altium.edit.board_ops import MECHANICAL_1
from tests.unit.backends.altium.edit.conftest import OPEN, mm


def _session(path: Path) -> edit.Session:
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def test_redrawn_after_a_notch(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    notch = [(mm(18), mm(-1)), (mm(22), mm(-1)), (mm(22), mm(3)), (mm(18), mm(3))]
    session = _session(path).add_board_cutout(notch, notch=True)
    session.draw_board_shape("Mechanical 1", width=mm(0.1), old_count=10)
    receipt = session.commit(path.with_name("out.PcbDoc"), backup=False)
    assert receipt.written, receipt.issues
    state = State.of(path.with_name("out.PcbDoc").read_bytes())
    edges = drawing.board_shape(state)
    assert len(edges) == 13 and sum(e.centre is not None for e in edges) == 1
    assert drawing.compare(state, MECHANICAL_1) == []
    assert session.redrawn == {"Mechanical 1": 10}


def test_old_count_and_layer(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("drawn")
    receipt = (
        _session(path)
        .draw_board_shape("Mechanical 1", width=mm(0.1), old_count=6)
        .commit(path.with_name("out.PcbDoc"), backup=False)
    )
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"] and "holds 10" in receipt.issues[
        0
    ].message
    receipt = (
        _session(path)
        .draw_board_shape("Top Layer", width=mm(0.1), old_count=0)
        .commit(path.with_name("out.PcbDoc"), backup=False)
    )
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]


def test_compare_finds_an_undrawn_cutout(board_ops: dict[str, bytes]) -> None:
    state = State.of(board_ops["drawn"])
    from fenolite.backends.altium.edit.ops import View

    view = View(state)
    ring = [view.units((mm(x), mm(y))) for x, y in ((10, 10), (12, 10), (12, 12), (10, 12))]
    state.append("Regions6", cutout_region(ring))
    found = drawing.compare(state, MECHANICAL_1)
    assert [i.code for i in found] == ["altium.board-drawing.mismatch"] * 4
    assert all("board cut-out" in i.message and i.where.startswith("Mechanical 1 at (1") for i in found)
    found = drawing.check_pcbdoc(state.data())
    assert len(found) == 4
    assert [i.code for i in drawing.check_pcbdoc(board_ops["vias"])] == ["altium.board-drawing.none"]
