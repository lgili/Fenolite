# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The commit gates of an edit session: connectivity, unexpected changes, read-back (c0241, task 3.3)."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import connectivity
from fenolite.backends.altium.edit.session import verify
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from tests.unit.backends.altium.edit.conftest import OPEN, mm

PROBE = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")


def _session(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def test_the_kit_board_has_three_nets_and_no_short(board: Path) -> None:
    sign = connectivity.signature(read_pcbdoc(board.read_bytes()))
    assert sign.shorts == frozenset()
    assert {net for net, _ in sign.groups} == {"GND", "MID", "VIN"}


def test_an_undeclared_short_names_both_nets_and_writes_nothing(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "never.PcbDoc"
    receipt = _session(board).move(PROBE, mm(-8.8), mm(15)).commit(out)
    assert not receipt.written and receipt.exit_code == 5 and not out.exists()
    codes = {i.code for i in receipt.issues}
    assert codes == {"altium.edit.connectivity"}
    shorts = [i for i in receipt.issues if "touches" in i.message]
    assert shorts and "GND" in shorts[0].message and "VIN" in shorts[0].message
    assert "declare_connectivity('GND', 'VIN')" in shorts[0].hint


def test_a_declared_change_is_written(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "deleted.PcbDoc"
    refused = _session(board).delete(edit.Component("R2")).commit(tmp_path / "never.PcbDoc")
    assert {i.code for i in refused.issues} == {"altium.edit.connectivity"}
    declared = _session(board).delete(edit.Component("R2")).declare_connectivity("VIN", "GND")
    assert declared.commit(out, backup=False).written


def test_a_record_changed_beyond_the_operations_refuses(board: Path) -> None:
    original = board.read_bytes()
    state = State.of(original)
    tracks = state.get("Tracks6")
    state.replace("Tracks6", 0, tracks[0])  # nothing declared
    tracks[1] = tracks[0]
    state.touched.add(state.name("Tracks6"))
    data, issues = verify(original, state, declared_nets=set())
    assert data is None
    assert [i.code for i in issues if i.code == "altium.edit.unexpected-change"] == [
        "altium.edit.unexpected-change"
    ]
    assert "Tracks6" in issues[0].message


def test_a_stream_changed_outside_the_edited_storages_refuses(board: Path) -> None:
    original = board.read_bytes()
    state = State.of(original)
    name = next(p for p in state.streams if p.upper() == "BOARD6/DATA")
    assert b"|ORIGINX=1000mil" in state.streams[name]
    state.streams[name] = state.streams[name].replace(b"|ORIGINX=1000mil", b"|ORIGINX=2000mil", 1)
    data, issues = verify(original, state, declared_nets=set())
    assert data is None and issues[0].code == "altium.edit.unexpected-change" and name in issues[0].message


def test_a_document_that_does_not_read_back_refuses(board: Path) -> None:
    original = board.read_bytes()
    state = State.of(original)
    name = next(p for p in state.streams if p.upper() == "TRACKS6/DATA")
    state.streams[name] = state.streams[name][:-3]
    state.touched.add(state.name("Tracks6"))
    data, issues = verify(original, state, declared_nets=set())
    assert data is None and [i.code for i in issues] == ["altium.edit.readback"]
