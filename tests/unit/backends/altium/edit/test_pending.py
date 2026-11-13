# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pending bytes of an edit session (change c0501, requirement "Pending bytes of a session"), on the Part
J kit board."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from tests.unit.backends.altium.edit.conftest import OPEN, mm

PROBE = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")


def _tracks(data: bytes) -> list[tuple[object, ...]]:
    design = AltiumBackend().board_from_bytes(data, file="edit.PcbDoc").content
    board = getattr(design, "board", None)
    assert board is not None
    return sorted((t.start, t.end, t.layer, t.width, t.net_id) for t in board.tracks)


def test_read_the_pending_edit(board: Path, tmp_path: Path) -> None:
    """Scenario "Read the pending edit"."""
    before = board.read_bytes()
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    session.clone(PROBE, start=(mm(10), mm(8)), end=(mm(20), mm(8)))
    first, issues = session.pending()
    second, _ = session.pending()
    assert first is not None and first == second and not issues
    assert board.read_bytes() == before and len(session.queued) == 1
    assert len(read_pcbdoc(first).tracks) == len(read_pcbdoc(before).tracks) + 1
    out = tmp_path / "out.PcbDoc"
    assert session.commit(out, backup=False).written
    assert _tracks(out.read_bytes()) == _tracks(first)


def test_a_refused_queue_gives_no_bytes(board: Path) -> None:
    session = edit.open(board, gates={})
    assert isinstance(session, edit.Session)
    data, issues = session.clone(PROBE).pending()
    assert data is None and [i.code for i in issues] == ["altium.edit.gate"]
