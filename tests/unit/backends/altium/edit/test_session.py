# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit session of an Altium PCB document on the kit board: delete, move, rotate and set_property, and
their gates (change c0241, tasks 3.1 and 3.2). Every gate is opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import integrity
from fenolite.backends.altium.edit.ops import View
from fenolite.backends.altium.edit.session import _records, unique_id_entries
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import to_units
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, TrackRecord
from tests.unit.backends.altium.edit.conftest import OPEN, mm

PROBE = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")


def _session(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def _diff(before: bytes, after: bytes) -> dict[str, tuple[int, int]]:
    """Per storage, the records removed and added."""
    old, new = _records(before), _records(after)
    out: dict[str, tuple[int, int]] = {}
    for name in sorted(set(old) | set(new)):
        a, b = old.get(name, Counter[bytes]()), new.get(name, Counter[bytes]())
        if a != b:
            out[name] = (sum((a - b).values()), sum((b - a).values()))
    return out


def _tracks_mm(data: bytes) -> list[tuple[float, float, float, float]]:
    state = State.of(data)
    view = View(state)
    ox, oy = view.origin
    return [
        tuple(
            round((v - o) * 127 / 50 / 1e6, 3)
            for v, o in zip((t.x1, t.y1, t.x2, t.y2), (ox, oy, ox, oy), strict=True)
        )
        for t in read_pcbdoc(data).tracks
        if isinstance(t, TrackRecord)
    ]  # type: ignore[misc]


def test_every_gate_is_off_and_each_names_its_rows() -> None:
    assert set(edit.GATES) == set(edit.OPERATIONS) and not any(edit.GATES.values())
    assert all("H-A-EDIT-KIT" in edit.ROWS[op] for op in edit.OPERATIONS)
    assert edit.EVIDENCE.level.name == "INFERRED"


def test_a_closed_gate_refuses_before_any_edit(board: Path, tmp_path: Path) -> None:
    session = edit.open(board)
    assert isinstance(session, edit.Session)
    receipt = session.flip(edit.Component("D1")).commit(tmp_path / "never.PcbDoc")
    assert not receipt.written and receipt.exit_code == 5 and not (tmp_path / "never.PcbDoc").exists()
    [issue] = receipt.issues
    assert issue.code == "altium.edit.gate" and "H-A-EDIT-FLIP" in issue.message


def test_move_reads_back_with_every_other_record_equal(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "moved.PcbDoc"
    receipt = _session(board).move(PROBE, 0, mm(1)).commit(out, backup=False)
    assert receipt.written and receipt.exit_code == 0 and receipt.issues == ()
    assert receipt.evidence.level.name == "INFERRED"
    data = out.read_bytes()
    assert (10.0, 6.0, 20.0, 6.0) in _tracks_mm(data) and (10.0, 5.0, 20.0, 5.0) not in _tracks_mm(data)
    assert _diff(board.read_bytes(), data) == {"Tracks6": (1, 1)}
    assert integrity.check_pcbdoc(data) == ()


def test_a_wrong_stated_value_refuses(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "never.PcbDoc"
    receipt = _session(board).move(PROBE, 0, mm(1), expect={"width": mm(0.3)}).commit(out)
    [issue] = receipt.issues
    assert issue.code == "altium.edit.assertion" and "0.25 mm" in issue.message and "0.3 mm" in issue.message
    assert not out.exists()


def test_an_item_that_is_not_there_refuses(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).delete(edit.Component("R7")).commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"] and "R7" in receipt.issues[0].message


def test_delete_a_component_leaves_no_index_entry(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "deleted.PcbDoc"
    session = _session(board).delete(edit.Component("R1")).declare_connectivity("VIN", "MID", "GND")
    receipt = session.commit(out, backup=False)
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    doc = read_pcbdoc(data)
    assert sorted(c.source_designator for c in doc.components) == ["D1", "R2"]
    pads = [p for p in doc.pads if isinstance(p, PadRecord)]
    assert {p.prefix.component for p in pads} == {0, 1}
    entries = unique_id_entries(data)
    assert sorted(int(e["PRIMITIVEINDEX"]) for e in entries) == list(range(len(pads)))
    assert integrity.check_pcbdoc(data) == ()


def test_rotate_states_the_old_rotation(board: Path, tmp_path: Path) -> None:
    wrong = (
        _session(board).rotate(edit.Component("R2"), 90, old_rotation=180).commit(tmp_path / "never.PcbDoc")
    )
    assert [i.code for i in wrong.issues] == ["altium.edit.assertion"]
    out = tmp_path / "rotated.PcbDoc"
    receipt = _session(board).rotate(edit.Component("R2"), 90, old_rotation=0)
    assert receipt.declare_connectivity("VIN", "GND").commit(out, backup=False).written
    doc = read_pcbdoc(out.read_bytes())
    [r2] = [c for c in doc.components if c.source_designator == "R2"]
    assert round(r2.rotation) == 90
    assert integrity.check_pcbdoc(out.read_bytes()) == ()


def test_set_property_changes_the_wide_string_of_a_comment(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "comment.PcbDoc"
    receipt = _session(board).set_property(edit.Component("R1"), "comment", "2k2", old="1k").commit(out)
    assert receipt.written, receipt.issues
    changed = _diff(board.read_bytes(), out.read_bytes())
    assert set(changed) == {"WideStrings6"}, changed
    wrong = _session(board).set_property(edit.Component("R1"), "comment", "2k2", old="4k7")
    assert [i.code for i in wrong.commit(tmp_path / "never.PcbDoc").issues] == ["altium.edit.assertion"]


def test_set_property_changes_a_free_text_and_a_track_width(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "text.PcbDoc"
    text = edit.Text("FENOLITE EDIT")
    assert (
        _session(board).set_property(text, "text", "FENOLITE EDIT 2", old="FENOLITE EDIT").commit(out).written
    )
    doc = read_pcbdoc(out.read_bytes())
    assert "FENOLITE EDIT 2" in [t.text for t in doc.texts]
    wide = tmp_path / "wide.PcbDoc"
    assert _session(board).set_property(PROBE, "width", mm(0.3), old=mm(0.25)).commit(wide).written
    widths = [t.width for t in read_pcbdoc(wide.read_bytes()).tracks if isinstance(t, TrackRecord)]
    assert widths.count(to_units(mm(0.3))) == 1


def test_a_commit_keeps_the_previous_file(board: Path) -> None:
    receipt = _session(board).move(PROBE, 0, mm(1)).commit(board)
    assert receipt.written and receipt.backup is not None and receipt.backup.exists()
    assert receipt.path == board
