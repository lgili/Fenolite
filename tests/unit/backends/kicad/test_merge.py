# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Three-way merge of KiCad boards by root item (capability file-safety, "Three-way difference of KiCad
boards"; change c0207). Hermetic: authored boards only."""

from __future__ import annotations

from pathlib import Path

from _merge_boards import (
    NEW_TRACK,
    TRACK_END,
    edge_block,
    replaced,
    segment_block,
    three_boards,
)

from fenolite.backends.kicad.merge import MergeItem, three_way
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.diff import diff_designs

DATA = Path(__file__).resolve().parents[3] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"


def _paths(a: bytes, b: bytes) -> list[tuple[str, str]]:
    report = diff_designs(read_board(a.decode("utf-8")), read_board(b.decode("utf-8")))
    return [(change.path, change.change) for change in report.changes]


def test_changes_of_two_sides_are_merged(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    base, ours, theirs = (p.read_bytes() for p in (boards.base, boards.ours, boards.theirs))
    merged = three_way(base, ours, theirs)
    assert merged.data is not None and merged.refused is None and merged.conflicts == ()
    assert [(i.change, i.status) for i in merged.items] == [("changed", "applied"), ("added", "applied")]
    assert merged.items[1].key == "segment 00000000-0000-4000-8000-000000000207"
    # THEIRS keeps its own change and its bytes; the segment of OURS and the new one follow it
    theirs_text = theirs.decode("utf-8")
    ours_segment = segment_block(ours.decode("utf-8"))
    expected = replaced(theirs_text, segment_block(theirs_text), ours_segment + NEW_TRACK)
    assert merged.data.decode("utf-8") == expected
    # the model difference that the merge adds to THEIRS is the one from BASE to OURS
    assert _paths(theirs, merged.data) == _paths(base, ours)
    assert ("/footprint/R1/position", "changed") in _paths(base, merged.data)


def test_a_change_made_on_both_sides_is_already_there(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    theirs = boards.write("both.kicad_pcb", boards.ours.read_text(encoding="utf-8"))
    merged = three_way(boards.base.read_bytes(), boards.ours.read_bytes(), theirs.read_bytes())
    assert {i.status for i in merged.items} == {"already"}
    assert merged.data == theirs.read_bytes()


def test_an_item_changed_on_both_sides_is_a_conflict(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    other = replaced(boards.base_text, TRACK_END, "\t\t(end 25 9)\n")
    theirs = boards.write("other.kicad_pcb", other)
    merged = three_way(boards.base.read_bytes(), boards.ours.read_bytes(), theirs.read_bytes())
    assert merged.data is None
    assert merged.conflicts == (
        MergeItem("segment 07af368b-89d1-537e-bd8c-1eba13e6bf03", "changed", "conflict"),
    )


def test_a_removed_item_takes_its_lines(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    edge = edge_block(boards.base_text)
    ours = boards.write("cut.kicad_pcb", replaced(boards.base_text, edge, ""))
    merged = three_way(boards.base.read_bytes(), ours.read_bytes(), boards.theirs.read_bytes())
    assert [(i.change, i.status) for i in merged.items] == [("removed", "applied")]
    assert merged.data is not None
    assert merged.data.decode("utf-8") == replaced(boards.theirs.read_text(encoding="utf-8"), edge, "")
    # removed in THEIRS too: nothing left to do
    again = three_way(boards.base.read_bytes(), ours.read_bytes(), ours.read_bytes())
    assert [i.status for i in again.items] == ["already"] and again.data == ours.read_bytes()


def test_boards_that_cannot_be_merged(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    newer = boards.write(
        "newer.kicad_pcb", replaced(boards.base_text, "(version 20260206)", "(version 20260207)")
    )
    merged = three_way(boards.base.read_bytes(), boards.ours.read_bytes(), newer.read_bytes())
    assert merged.data is None and merged.items == ()
    assert merged.refused is not None and "versions" in merged.refused
    # the numbered net table of a KiCad 9 board: equal tables merge, differing ones are refused
    nine = TWO_LAYER.read_bytes()
    assert three_way(nine, nine, nine).data == nine
    renamed = nine.replace(b'(net 3 "LED_A")', b'(net 3 "LED_B")')
    refused = three_way(nine, renamed, nine)
    assert refused.data is None and refused.refused is not None and "net tables" in refused.refused


def test_line_ends_of_theirs_are_kept(tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    crlf = boards.theirs.read_bytes().replace(b"\n", b"\r\n")
    merged = three_way(boards.base.read_bytes(), boards.ours.read_bytes(), crlf)
    assert merged.data is not None and merged.data != crlf
    assert b"\n" not in merged.data.replace(b"\r\n", b"")
