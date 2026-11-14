# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit plan of a PCB session and its replay onto a newer save (change c0502), on the Part J kit board.
A "newer save" is a copy of the kit board that the test changes itself."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.plan import PLAN_OPS, EditPlan, fingerprint, queue, replay
from fenolite.backends.altium.edit.session import Session, _records, open_document
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TrackRecord
from fenolite.core.errors import FormatError
from tests.unit.backends.altium.edit.conftest import OPEN, mm

PROBE = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")
FEED = edit.Track((mm(5), mm(25)), (mm(11.2), mm(25)), "VIN")


def _session(board: Path) -> Session:
    return open_document(board, gates=OPEN)


def _changed(before: bytes, after: bytes) -> set[str]:
    old, new = _records(before), _records(after)
    return {n for n in set(old) | set(new) if old.get(n, Counter[bytes]()) != new.get(n, Counter[bytes]())}


def _save(board: Path, session: Session, name: str) -> Path:
    """A newer save of ``board``: ``session``'s edits written to a sibling file."""
    out = board.parent / name
    receipt = session.commit(out, backup=False)
    assert receipt.written, receipt.issues
    return out


def _widths(data: bytes) -> list[int]:
    return [t.width for t in read_pcbdoc(data).tracks if isinstance(t, TrackRecord)]


def test_entries_round_trip_every_operation(board: Path) -> None:
    """Task 1.1: every public operation records its entry, and the entries queue the same operations."""
    ring = [(mm(1), mm(1)), (mm(2), mm(1)), (mm(2), mm(2))]
    session = _session(board)
    session.delete(PROBE).move(PROBE, 0, mm(1), expect={"width": mm(0.25)})
    session.rotate(edit.Component("R2"), 90, old_rotation=0)
    session.rotate(edit.Designator("R2"), 45.5, old_rotation=0, about="anchor")
    session.flip(edit.Component("D1")).set_property(edit.Component("R1"), "comment", "2k2", old="1k")
    session.clone(PROBE, start=(mm(1), mm(1)), width=mm(0.3)).remap_layer("Mechanical 1", "Mechanical 2")
    session.set_rule("Clearance", "GAP", "10mil", old="8mil")
    session.set_outline(edit.Polygon("P"), ring, old=ring).unpour(edit.Polygon("P"))
    session.add_arc((0, 0), mm(1), 0, 90.5, width=mm(0.2), layer="Top Layer").add_fill(
        (0, 0), (mm(1), mm(1)), layer="Top Layer", rotation=12.25
    )
    session.add_region(ring, layer="Top Layer").add_polygon("Q", ring, layer="Top Layer", net="GND")
    session.add_board_cutout(ring, drawing="Mechanical 1").add_polygon_cutout(ring, layer="Top Layer")
    session.set_via_mask(edit.Vias(net="GND"), tented_top=True, tented_bottom=False, count=1)
    session.draw_board_shape("Mechanical 1", width=mm(0.1), old_count=4)
    session.add_component(board, "R1", designator="R9", at=(mm(3), mm(3)), nets={"1": "GND"})
    session.link("R1", project=board.parent / "edit.PrjPcb", part="R1")
    entries = [q.entry for q in session.queued]
    assert None not in entries and {e["op"] for e in entries if e} == PLAN_OPS - {"declare_connectivity"}
    again = _session(board)
    for index, entry in enumerate(entries):
        queue(again, entry, index, allowed=PLAN_OPS)
    assert [q.entry for q in again.queued] == entries
    assert [q.label for q in again.queued] == [q.label for q in session.queued]
    assert [q.gate for q in again.queued] == [q.gate for q in session.queued]
    assert next(e for e in entries if e and e["op"] == "add_arc")["end"] == "90.5deg"


def test_entries_write_the_same_bytes(board: Path) -> None:
    session = _session(board).move(PROBE, 0, mm(1)).rotate(edit.Component("R2"), 90, old_rotation=0)
    session.set_property(edit.Component("R1"), "comment", "2k2", old="1k")
    session.clone(FEED, start=(mm(5), mm(26)), width=mm(0.3))
    again = _session(board)
    for index, entry in enumerate(q.entry for q in session.queued):
        queue(again, entry, index)
    assert again.pending()[0] == session.pending()[0] is not None


def test_fingerprint_holds_only_the_fields_of_its_operation(board: Path) -> None:
    state = State.of(board.read_bytes())
    storage, position = edit.ops.View(state).find(PROBE)
    track = edit.plan.plain(PROBE)
    moved = fingerprint(state, {"op": "move", "item": track}, storage, position)
    assert set(moved) == {"storage", "start", "end", "layer", "net"}
    expected = fingerprint(state, {"op": "move", "item": track, "expect": {"width": 1}}, storage, position)
    assert set(expected) == set(moved) | {"width"}
    width = fingerprint(state, {"op": "set_property", "item": track, "key": "width"}, storage, position)
    assert width == {"storage": "Tracks6", "width": 98425}


def test_round_trip(board: Path) -> None:
    """Scenario "A plan written and read back"."""
    session = _session(board).move(PROBE, 0, mm(1))
    session.set_property(edit.Component("R1"), "comment", "2k2", old="1k")
    session.clone(FEED, start=(mm(5), mm(26)))
    plan = session.plan()
    text = plan.text()
    assert EditPlan.read(text) == plan and session.plan().text() == text
    assert str(board.parent) not in text and board.parent.as_posix() not in text

    def floats(value: object) -> bool:
        if isinstance(value, dict):
            return any(floats(v) for v in value.values())  # pyright: ignore[reportUnknownVariableType]
        if isinstance(value, list):
            return any(floats(v) for v in value)  # pyright: ignore[reportUnknownVariableType]
        return isinstance(value, float)

    assert not floats(json.loads(text))
    [move, comment, made] = plan.operations
    assert move.target == {"unique_id": None, "key": move.entry["item"]} and move.base != move.result
    assert comment.target is not None and comment.target["unique_id"] == "YNQCVRLM"
    assert comment.base == {"storage": "Components6", "comment": "1k"} and comment.result == {
        "storage": "Components6",
        "comment": "2k2",
    }
    assert made.target is not None and made.result is not None and made.result["storage"] == "Tracks6"


def test_source_bytes_cannot_be_planned(board: Path) -> None:
    """Scenario "Source bytes cannot be planned"."""
    session = _session(board).add_component(board.read_bytes(), "R1", designator="R9")
    with pytest.raises(ValueError, match="add the component R1"):
        session.plan()


def test_a_plan_that_does_not_read() -> None:
    with pytest.raises(FormatError, match="schema"):
        EditPlan.read('{"schema": "other"}')
    bad = {"schema": "fenolite.altium-edit-plan.v0", "document": "a", "base_sha256": "0", "operations": [
        {"entry": {"op": "explode"}, "gate": "move", "label": "x"}]}  # fmt: skip
    with pytest.raises(FormatError, match="no operation"):
        EditPlan.read(json.dumps(bad))


def test_reordered_records_and_a_renamed_component(board: Path) -> None:
    """Scenario "Records reordered and a component renamed"."""
    session = _session(board).rotate(edit.Component("D1"), 90, old_rotation=0).move(PROBE, 0, mm(1))
    plan = session.declare_connectivity(*{"VIN", "MID", "GND"}).plan()
    expected = _changed(board.read_bytes(), _save(board, session, "expected.PcbDoc").read_bytes())
    state = State.of(board.read_bytes())
    tracks = state.get("Tracks6")
    tracks.reverse()
    state.touched.add(state.name("Tracks6"))
    position = edit.ops.View(state).component("D1")
    record = state.properties("Components6")[position]
    state.replace("Components6", position, rec.set_property(record.raw, {"SOURCEDESIGNATOR": "D7"}))
    newer = board.parent / "newer.PcbDoc"
    newer.write_bytes(state.data())
    replayed = replay(plan, newer, gates=OPEN)
    assert [s.status for s in replayed.rebased] == ["applied", "applied"]
    out = board.parent / "out.PcbDoc"
    receipt = replayed.commit(out, backup=False)
    assert receipt.written, receipt.issues
    doc = read_pcbdoc(out.read_bytes())
    [d7] = [c for c in doc.components if c.source_designator == "D7"]
    assert round(d7.rotation) == 90
    assert _changed(newer.read_bytes(), out.read_bytes()) == expected


def test_unrelated_changes_in_the_newer_save(board: Path) -> None:
    """Scenario "Unrelated changes in the newer save"."""
    plan = _session(board).move(PROBE, 0, mm(1)).plan()
    other = edit.Track((mm(2), mm(2)), (mm(12), mm(2)), None)
    vias = read_pcbdoc(board.read_bytes()).vias
    newer = _session(board).move(other, 0, mm(2))
    newer = _save(board, newer, "newer.PcbDoc")
    first = State.of(newer.read_bytes())
    first.append("Vias6", first.get("Vias6")[0])
    newer.write_bytes(first.data())
    assert len(read_pcbdoc(newer.read_bytes()).vias) == len(vias) + 1
    replayed = replay(plan, newer, gates=OPEN)
    out = board.parent / "out.PcbDoc"
    receipt = replayed.commit(out, backup=False)
    assert receipt.written and [s.status for s in replayed.rebased] == ["applied"], receipt.issues
    data = out.read_bytes()
    assert len(read_pcbdoc(data).vias) == len(vias) + 1
    assert _changed(newer.read_bytes(), data) == {"Tracks6"}


def test_the_target_changed_in_the_newer_save(board: Path) -> None:
    """Scenario "The target changed in the newer save"."""
    plan = _session(board).set_property(PROBE, "width", mm(0.5), old=mm(0.25)).plan()
    newer = _save(board, _session(board).set_property(PROBE, "width", mm(0.3), old=mm(0.25)), "newer.PcbDoc")
    replayed = replay(plan, newer, gates=OPEN)
    out = board.parent / "out.PcbDoc"
    receipt = replayed.commit(out)
    assert receipt.exit_code == 5 and not out.exists()
    [issue] = receipt.issues
    assert issue.code == "altium.edit.rebase-conflict" and "width" in issue.message
    assert "0.25 mm" in issue.message and "0.3 mm" in issue.message
    [step] = replayed.rebased
    assert step.status == "conflict" and [f[0] for f in step.fields] == ["width"]


def test_the_target_deleted_in_the_newer_save(board: Path) -> None:
    """Scenario "The target deleted in the newer save"."""
    plan = _session(board).move(PROBE, 0, mm(1)).plan()
    newer = _save(board, _session(board).delete(PROBE).declare_connectivity("GND"), "newer.PcbDoc")
    receipt = replay(plan, newer, gates=OPEN).commit(board.parent / "out.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.rebase-missing"]
    assert "(10, 5) mm" in receipt.issues[0].message and not (board.parent / "out.PcbDoc").exists()


def test_a_plan_replayed_on_its_own_result(board: Path) -> None:
    """Scenario "A plan replayed on its own result"."""
    session = _session(board).move(PROBE, 0, mm(1)).rotate(edit.Component("R2"), 90, old_rotation=0)
    session.set_property(edit.Component("R1"), "comment", "2k2", old="1k").declare_connectivity("VIN", "GND")
    session.clone(FEED, start=(mm(5), mm(26))).delete(edit.Text("FENOLITE EDIT"))
    plan = session.plan()
    result = _save(board, session, "result.PcbDoc")
    replayed = replay(plan, result, gates=OPEN)
    out = board.parent / "again.PcbDoc"
    receipt = replayed.commit(out, backup=False)
    assert receipt.written and {s.status for s in replayed.rebased} == {"already-applied"}
    assert [i.code for i in receipt.issues] == ["altium.edit.rebase-applied"] * 5
    assert out.read_bytes() == result.read_bytes()
