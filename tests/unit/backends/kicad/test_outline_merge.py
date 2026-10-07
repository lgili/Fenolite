# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``outline.merge_outline``: the signature, the five cases, re-signing and the lock, on token-edited
boards (capability layout-lens, "Outline changes across rebuilds", unit half; change c0102)."""

from __future__ import annotations

import dataclasses

from _layout_edit import add_items, add_to_footprint, net_ref
from _outlinehelp import BOARD, ROUNDED, board_text, build_script, variant

from fenolite.backends.kicad.outline import (
    MERGE_ISSUE_CODES,
    OutlineMerge,
    edge_graphics,
    is_signed,
    merge_outline,
    outline_case,
    position_uuid,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.lens.build import BuildOutput
from fenolite.model.design import Design

MM = 1_000_000
WIDER = "design.board(mm(60), mm(30))"
NARROWER = "design.board(mm(40), mm(30))"
EDITED = (
    ("(start 150 100)\n\t\t(end 150 130)", "(start 155 100)\n\t\t(end 155 130)"),
    ("(start 100 100)\n\t\t(end 150 100)", "(start 100 100)\n\t\t(end 155 100)"),
    ("(start 150 130)\n\t\t(end 100 130)", "(start 155 130)\n\t\t(end 100 130)"),
)
"""The right edge line moved 5 mm right, with the top and bottom lines lengthened to meet it."""


def fresh(board: str = BOARD, append: str = "") -> BuildOutput:
    return build_script(variant(board, append=append))


def edited(text: str) -> str:
    for old, new in EDITED:
        assert old in text
        text = text.replace(old, new)
    return text


def built(board: str, append: str = "") -> Design:
    return build_script(variant(board, append=append)).design


def codes(merge: OutlineMerge) -> list[str]:
    return [found.code for found in merge.issues]


def segment(text: str, x0: float, y0: float, x1: float, y1: float, n: int, net: str = "GND") -> str:
    item = (
        f'(segment (start {x0} {y0}) (end {x1} {y1}) (width 0.25) (layer "F.Cu") {net_ref(text, net)} '
        f'(uuid "00000000-0000-4000-8000-0000000c{n:04d}"))'
    )
    return add_items(text, item)


def test_the_closed_table() -> None:
    assert dict(MERGE_ISSUE_CODES) == {
        "kicad.outline.forced": "warning",
        "kicad.outline.copper-dropped": "warning",
        "kicad.outline.replaced": "info",
    }


def test_no_edge_content_is_unchanged() -> None:
    board = read_board(board_text(fresh()))
    assert board.board is not None
    bare = dataclasses.replace(
        board,
        board=dataclasses.replace(
            board.board, graphics=tuple(g for g in board.board.graphics if g.layer != "Edge.Cuts")
        ),
    )
    merge = merge_outline(built(WIDER), bare)
    assert merge.board is bare and not merge.replaced and merge.issues == ()
    assert outline_case(built(WIDER), bare) == "none"


def test_equal_content_is_kept() -> None:
    output = fresh()
    board = read_board(board_text(output))
    merge = merge_outline(output.design, board)
    assert merge.board is board and not merge.replaced and merge.issues == ()
    assert outline_case(output.design, board) == "kept"
    # an outline with arcs, written and read back, is equal too
    rounded = fresh(ROUNDED)
    assert outline_case(rounded.design, read_board(board_text(rounded))) == "kept"


def test_signed_content_is_replaced() -> None:
    board = read_board(board_text(fresh()))
    new = built(WIDER)
    merge = merge_outline(new, board)
    assert merge.replaced and codes(merge) == ["kicad.outline.replaced"]
    assert merge.issues[0].severity == "info"
    assert merge.board.board is not None and new.board is not None
    assert edge_graphics(merge.board) == () and merge.board.board.outline == new.board.outline
    assert dict(merge.dropped) == {"tracks": 0, "arcs": 0, "vias": 0}


def test_edited_content_wins_unless_locked() -> None:
    board = read_board(edited(board_text(fresh())))
    new = built(WIDER)
    assert new.board is not None and new.board.outline is not None
    assert not is_signed(new.board.outline, edge_graphics(board))
    kept = merge_outline(new, board)
    assert kept.board is board and not kept.replaced and kept.issues == ()
    forced = merge_outline(new, board, locked=True)
    assert forced.replaced and codes(forced) == ["kicad.outline.forced"]
    assert forced.issues[0].severity == "warning"
    assert forced.board.board is not None and forced.board.board.outline == new.board.outline
    assert (outline_case(new, board), outline_case(new, board, locked=True)) == ("kept", "forced")


def test_a_lock_changes_nothing_when_the_outline_is_equal_or_signed() -> None:
    output = fresh()
    board = read_board(board_text(output))
    assert merge_outline(output.design, board, locked=True).board is board
    assert codes(merge_outline(built(WIDER), board, locked=True)) == ["kicad.outline.replaced"]


def old_uuids(text: str, design: Design) -> str:
    """``text`` with the four edge lines under the position uuids of a Fenolite before this change."""
    assert design.board is not None and design.board.outline is not None
    outline = design.board.outline
    graphics = edge_graphics(read_board(text))
    assert len(graphics) == 4
    for index, graphic in enumerate(graphics):
        text = text.replace(graphic.native_ids["kicad"], position_uuid(outline, 0, index))
    return text


def test_edges_of_an_older_fenolite_are_resigned_when_equal() -> None:
    output = fresh()
    board = read_board(old_uuids(board_text(output), output.design))
    assert output.design.board is not None and output.design.board.outline is not None
    assert not is_signed(output.design.board.outline, edge_graphics(board))
    merge = merge_outline(output.design, board)
    assert outline_case(output.design, board) == "resigned"
    assert not merge.replaced and merge.issues == ()
    assert merge.board.board is not None
    assert edge_graphics(merge.board) == () and merge.board.board.outline == output.design.board.outline
    # with another outline they count as edited: nothing tells whether KiCad changed them
    other = merge_outline(built(WIDER), board)
    assert other.board is board and other.issues == ()


def test_copper_that_no_longer_fits_is_dropped() -> None:
    text = board_text(fresh())
    text = segment(text, 110, 128, 120, 128, 1)  # stays inside the 40 mm board
    text = segment(text, 145, 105, 148, 105, 2)  # wholly outside it
    text = segment(text, 135, 110, 145, 110, 3)  # across the new edge
    text = add_items(
        text,
        f'(via (at 147 120) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") {net_ref(text, "GND")} '
        '(uuid "00000000-0000-4000-8000-0000000c0009"))',
    )
    board = read_board(text)
    merge = merge_outline(built(NARROWER), board)
    assert merge.replaced and codes(merge) == ["kicad.outline.replaced", "kicad.outline.copper-dropped"]
    assert merge.board.board is not None
    assert [(t.start, t.end) for t in merge.board.board.tracks] == [
        (Point(110 * MM, 128 * MM), Point(120 * MM, 128 * MM))
    ]
    assert merge.board.board.vias == ()
    assert dict(merge.dropped) == {"tracks": 2, "arcs": 0, "vias": 1}
    dropped = merge.issues[1]
    assert dropped.severity == "warning" and "2 tracks" in dropped.message and "1 via " in dropped.message
    assert "GND" in dropped.message


def test_copper_in_a_cutout_or_touching_a_ring_is_dropped() -> None:
    text = board_text(fresh())
    text = segment(text, 144, 105, 146, 105, 1)  # inside the round cut-out of the rounded board
    text = segment(text, 105, 115, 115, 115, 2)  # clear of every ring
    text = segment(text, 100.5, 100.5, 102, 102, 3)  # across the rounded corner
    merge = merge_outline(built(ROUNDED), read_board(text))
    assert merge.board.board is not None
    assert [t.start for t in merge.board.board.tracks] == [Point(105 * MM, 115 * MM)]
    assert dict(merge.dropped) == {"tracks": 2, "arcs": 0, "vias": 0}
    assert "2 tracks" in merge.issues[1].message


def test_edge_items_of_a_footprint_are_left_alone_and_named() -> None:
    text = add_to_footprint(
        board_text(fresh()),
        "U1",
        "(fp_rect (start -1 -0.5) (end 1 0.5) (stroke (width 0.05) (type solid)) (fill no) "
        '(layer "Edge.Cuts") '
        '(uuid "00000000-0000-4000-8000-0000000c0020"))',
    )
    board = read_board(text)
    merge = merge_outline(built(WIDER), board)
    assert merge.replaced and codes(merge) == ["kicad.outline.replaced"]
    assert "U1" in merge.issues[0].message and "stay" in merge.issues[0].message
    assert merge.board.board is not None and board.board is not None
    assert merge.board.board.footprints == board.board.footprints


def test_a_zone_declared_without_an_outline_follows() -> None:
    pour = 'design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3), connection="solid")\n'
    board = read_board(board_text(fresh(append=pour)))
    new = built(WIDER, pour)
    merge = merge_outline(new, board)
    assert merge.board.board is not None and new.board is not None
    (zone,) = merge.board.board.zones
    assert zone.outline == new.board.zones[0].outline
    assert zone.outline[2] == Point(160 * MM, 130 * MM)
    # a zone with an outline of its own stays as it is
    own = 'design.zone(gnd, layers=("B.Cu",), outline=((mm(1), mm(1)), (mm(40), mm(1)), (mm(40), mm(20))))\n'
    held = read_board(board_text(fresh(append=own)))
    kept = merge_outline(built(WIDER, own), held)
    assert kept.board.board is not None and held.board is not None
    assert kept.board.board.zones == held.board.zones
