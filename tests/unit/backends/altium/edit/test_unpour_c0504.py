# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A stale pour dropped and reported (change c0504, D1): ``Session.unpour`` and ``altium.edit.pour-stale``."""

from __future__ import annotations

import struct
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.ops import View
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from tests.unit.backends.altium.edit.conftest import OPEN, mm
from tests.unit.backends.altium.edit.test_session import PROBE

BOTTOM = 32
GND, VIN = edit.Polygon("GND"), edit.Polygon("VIN")
MOVED = edit.Track((mm(10), mm(12)), (mm(20), mm(12)), "GND")
"""A free bottom track inside the box of the poured polygon ``GND`` (bottom, the whole board)."""


def plant(data: bytes) -> bytes:
    """The kit board ``data`` with a poured piece of ``GND`` (bottom) and of ``VIN`` (top), and ``MOVED``;
    also the source of Part J case J40 (``test_part_j_c0497.py``)."""
    state = State.of(data)
    view = View(state)
    a, b = view.units(PROBE.start), view.units(PROBE.end)
    probe = next(
        r for r in state.get("Tracks6") if struct.unpack_from("<4i", rec.split(r)[1][0], 13) == (*a, *b)
    )

    def at(raw: bytes, start: tuple[int, int], end: tuple[int, int]) -> bytes:
        return rec.patch(raw, 13, "<4i", *view.units(start), *view.units(end))

    state.append("Tracks6", at(rec.set_prefix(probe, layer=BOTTOM), MOVED.start, MOVED.end))
    piece = rec.set_prefix(probe, layer=BOTTOM, net=rec.NO_INDEX, polygon=0)
    state.append("Tracks6", at(piece, (mm(30), mm(14)), (mm(32), mm(14))))
    piece = rec.set_prefix(probe, net=rec.NO_INDEX, polygon=1)
    state.append("Tracks6", at(piece, (mm(3), mm(23)), (mm(4), mm(23))))
    return state.data()


def _plant(board: Path) -> bytes:
    data = plant(board.read_bytes())
    board.write_bytes(data)
    return data


def _pieces(data: bytes) -> dict[int, int]:
    doc = read_pcbdoc(data)
    out: dict[int, int] = {}
    for track in doc.tracks:
        polygon = getattr(track, "prefix", None) and track.prefix.polygon  # type: ignore[union-attr]
        if polygon is not None:
            out[polygon] = out.get(polygon, 0) + 1
    return out


def _session(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def test_the_ground_pour_is_dropped_after_a_move(board: Path, tmp_path: Path) -> None:
    """Scenario "The ground pour dropped after a move"."""
    before = _plant(board)
    assert _pieces(before) == {0: 1, 1: 1}
    out = tmp_path / "unpoured.PcbDoc"
    receipt = _session(board).move(MOVED, 0, mm(1)).unpour(GND).commit(out, backup=False)
    assert receipt.written, receipt.issues
    assert "altium.edit.pour-stale" not in {i.code for i in receipt.issues}
    data = out.read_bytes()
    assert _pieces(data) == {1: 1}
    assert State.of(data).get("Polygons6") == State.of(before).get("Polygons6")


def test_a_move_through_a_poured_polygon_is_stale(board: Path, tmp_path: Path) -> None:
    """Scenario "A move through a poured polygon": one warning, naming ``GND`` and ``Session.unpour``."""
    _plant(board)
    receipt = _session(board).move(MOVED, 0, mm(1)).commit(tmp_path / "moved.PcbDoc", backup=False)
    assert receipt.written and receipt.exit_code == 0, receipt.issues
    [stale] = [i for i in receipt.issues if i.code == "altium.edit.pour-stale"]
    assert (
        stale.severity == "warning"
        and "GND" in stale.message
        and "Session.unpour(Polygon('GND'))" in stale.hint
    )


def test_a_polygon_without_a_pour_is_refused(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).unpour(VIN).commit(tmp_path / "never.PcbDoc")
    [issue] = receipt.issues
    assert not receipt.written and issue.code == "altium.edit.assertion" and "no pour" in issue.message


def test_unpour_is_gated_on_the_shape_rows() -> None:
    assert edit.ROWS["unpour"] == ("H-A-EDIT-SHAPE", "H-A-EDIT-KIT") and not edit.GATES["unpour"]
