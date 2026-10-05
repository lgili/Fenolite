# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The placements file in the precedence, and the extraction that writes it (capability layout-lens,
"Placement precedence" and "Placement extraction"; change c0069)."""

from __future__ import annotations

from _buildhelp import blink
from _layout_edit import D1_SHIFT, edit_blink, move_footprint
from _preserve_help import board_text, fresh, prepared, rebuild

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import BOARD_ORIGIN, Design, mm, placements, to_model
from fenolite.lens.extract import extract_placements
from fenolite.lens.placements import SourcePlacement
from fenolite.lens.preserve import (
    FILE_HINT,
    STALE_HINT,
    FilePlacement,
    KeptPlacement,
    LayoutMatch,
    effective_placements,
    match_footprints,
)

MM = 1_000_000
ELSEWHERE = SourcePlacement(
    Point(BOARD_ORIGIN.x + 20 * MM, BOARD_ORIGIN.y + 10 * MM), 90_000_000, "top", False
)


def unplaced_r1() -> Design:
    d = blink()
    d.parts["R1"].request = None
    return d


def without_r1(text: str) -> str:
    """The board ``text`` without the footprint of ``R1``."""
    from _layout_edit import footprint_node

    from fenolite.backends.kicad.sexpr import dumps, parse

    root = parse(text)
    gone = footprint_node(text, "R1")
    return dumps(root.with_children([c for c in root.children if c != gone]), style="kicad")


def test_the_file_places_an_unmatched_part() -> None:
    d = blink()
    ready = prepared(d, without_r1(board_text()), source={"R1": ELSEWHERE})
    placed = ready.placements["R1"]
    assert isinstance(placed, FilePlacement) and isinstance(placed, KeptPlacement)
    assert (placed.at, placed.rotation, placed.side, placed.locked) == (
        ELSEWHERE.at,
        90_000_000,
        "top",
        False,
    )
    (found,) = [i for i in ready.issues if i.code == "layout.place-overridden"]
    assert found.where == "R1" and found.hint == FILE_HINT and "placements.toml" in found.hint


def test_the_board_wins_over_a_stale_file() -> None:
    d = blink()
    at_place = placements(d)["D1"]
    entry = SourcePlacement(at_place.at, at_place.rotation, at_place.side, False)
    ready = prepared(d, board_text(edit=edit_blink), source={"D1": entry})
    kept = ready.placements["D1"]
    assert type(kept) is KeptPlacement and kept.at.x == at_place.at.x + D1_SHIFT
    (stale,) = [i for i in ready.issues if i.code == "layout.source-stale"]
    assert stale.where == "D1" and stale.severity == "info" and stale.hint == STALE_HINT


def test_a_current_entry_is_silent() -> None:
    d = blink()
    text = board_text(edit=edit_blink)
    board = read_board(text)
    model = to_model(d)
    entries = extract_placements(board, match_footprints(model, board), design=model).placements
    ready = prepared(d, text, source=entries)
    assert [i.code for i in ready.issues] == ["layout.place-overridden"]  # D1 against its place()


def test_a_locked_place_wins_over_the_file() -> None:
    d = blink()
    ready = prepared(d, None, source={"U1": ELSEWHERE})
    assert ready.placements["U1"] == placements(d)["U1"] and ready.issues == ()
    assert not isinstance(ready.placements["U1"], FilePlacement)


def test_the_file_wins_over_place_without_a_board() -> None:
    d = blink()
    ready = prepared(d, None, source={"R1": ELSEWHERE})
    assert isinstance(ready.placements["R1"], FilePlacement) and ready.board is None and ready.match is None
    assert [(i.code, i.where) for i in ready.issues] == [("layout.place-overridden", "R1")]
    same = prepared(d, None, source={"R1": SourcePlacement(*_request(d, "R1"), False)})
    assert same.issues == () and isinstance(same.placements["R1"], FilePlacement)


def _request(d: Design, path: str) -> tuple[Point, int, str]:
    request = placements(d)[path]
    return request.at, request.rotation, request.side


def test_no_file_no_board_gives_the_requests_unchanged() -> None:
    d = blink()
    requested = placements(d)
    model = to_model(d)
    effective, issues = effective_placements(requested, LayoutMatch({}), design=model, board=None)
    assert dict(effective) == dict(requested) and issues == ()


def test_the_file_places_a_part_off_the_board() -> None:
    """A staged footprint lies off the board: its file entry wins over staging it again."""
    d = unplaced_r1()
    text = fresh(design=d).files["blink.kicad_pcb"].decode("utf-8")
    staged = prepared(unplaced_r1(), text)
    assert "R1" not in staged.placements
    ready = prepared(unplaced_r1(), text, source={"R1": ELSEWHERE})
    assert isinstance(ready.placements["R1"], FilePlacement) and ready.issues == ()
    out = rebuild(unplaced_r1(), text, source={"R1": ELSEWHERE})
    assert "layout.unplaced" not in [i.code for i in out.issues]


def test_unknown_entry() -> None:
    ready = prepared(blink(), None, source={"R9": ELSEWHERE, "R1": ELSEWHERE})
    (unknown,) = [i for i in ready.issues if i.code == "layout.source-unknown"]
    assert unknown.where == "R9" and unknown.severity == "warning" and "R9" not in ready.placements


def test_a_locked_footprint_in_the_file() -> None:
    locked = SourcePlacement(ELSEWHERE.at, 0, "top", True)
    d = unplaced_r1()
    out = rebuild(d, None, source={"R1": locked})
    text = out.files["blink.kicad_pcb"].decode("utf-8")
    board = read_board(text)
    refs = {c.id: c.ref for c in board.circuit.components}
    (r1,) = [fp for fp in board.board.footprints if refs[fp.component_id] == "R1"]  # type: ignore[union-attr]
    assert r1.position == locked.at and r1.locked and "layout.unplaced" not in [i.code for i in out.issues]
    # the lock gives the entry no precedence: a later edit of the board still wins
    moved = move_footprint(text, "R1", 3 * MM, 0)
    ready = prepared(unplaced_r1(), moved, source={"R1": locked})
    kept = ready.placements["R1"]
    assert type(kept) is KeptPlacement and kept.at.x == locked.at.x + 3 * MM and kept.locked
    assert [i.code for i in ready.issues] == ["layout.source-stale"]


# -- extraction


def test_moved_footprint_extracted() -> None:
    d = blink()
    board = read_board(board_text(edit=edit_blink))
    model = to_model(d)
    found = extract_placements(board, match_footprints(model, board), design=model)
    assert list(found.placements) == ["D1", "R1", "U1"] and found.unplaced == ()
    d1 = found.placements["D1"]
    assert d1.at == Point(placements(d)["D1"].at.x + D1_SHIFT, placements(d)["D1"].at.y)
    assert (d1.side, d1.locked) == ("bottom", False) and found.placements["U1"].locked


def test_staged_part_not_extracted() -> None:
    d = unplaced_r1()
    board = read_board(fresh(design=d).files["blink.kicad_pcb"].decode("utf-8"))
    model = to_model(unplaced_r1())
    found = extract_placements(board, match_footprints(model, board), design=model)
    assert list(found.placements) == ["D1", "U1"] and found.unplaced == ("R1",)


def test_orphans_and_board_only_are_not_extracted() -> None:
    from _board_only import add_h1

    d = blink()
    del d.parts["D1"]
    board = read_board(add_h1()(board_text()))
    model = to_model(d)
    match = match_footprints(model, board)
    assert len(match.orphans) == 1 and len(match.board_only) == 1
    assert list(extract_placements(board, match, design=model).placements) == ["R1", "U1"]


def test_mm_helper_frame() -> None:
    """``ELSEWHERE`` is ``place(mm(20), mm(10))`` in the written frame."""
    d = unplaced_r1()
    d.parts["R1"].place(mm(20), mm(10), rot=90)
    assert _request(d, "R1") == (ELSEWHERE.at, ELSEWHERE.rotation, ELSEWHERE.side)
