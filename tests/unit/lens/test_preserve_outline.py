# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An outline change on a built board (capability layout-lens, "Outline changes across rebuilds" and "Board
content outside the design is kept"; change c0102). Each test builds a blink variant, edits the board by
token as KiCad would, and builds again over it."""

from __future__ import annotations

from _layout_edit import EDIT_UUIDS, add_items, add_to_footprint, edit_blink, net_ref
from _outlinehelp import BOARD, ROUNDED, board_text, build_script, codes, rebuild_script, variant

from fenolite.backends.kicad._edgesign import signed_uuids
from fenolite.backends.kicad.outline import board_outline, edge_graphics, position_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.lens.build import BuildOutput
from fenolite.lens.preserve import OUTLINE_HINT, PRESERVE_ISSUE_CODES
from fenolite.model.board import Graphic

MM = 1_000_000
WIDER = "design.board(mm(60), mm(30))"
NARROWER = "design.board(mm(40), mm(30))"
LOCKED = "design.board(mm(60), mm(30), locked=True)"
POUR = 'design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3), connection="solid")\n'
EDITED = (
    ("(start 150 100)\n\t\t(end 150 130)", "(start 155 100)\n\t\t(end 155 130)"),
    ("(start 100 100)\n\t\t(end 150 100)", "(start 100 100)\n\t\t(end 155 100)"),
    ("(start 150 130)\n\t\t(end 100 130)", "(start 155 130)\n\t\t(end 100 130)"),
)


def edited(text: str) -> str:
    for old, new in EDITED:
        assert old in text
        text = text.replace(old, new)
    return text


def edges(output: BuildOutput) -> tuple[Graphic, ...]:
    return edge_graphics(read_board(board_text(output)))


def right_edge(output: BuildOutput) -> int:
    return max(point.x for graphic in edges(output) for point in graphic.points)


def test_an_unchanged_outline_follows_the_script() -> None:
    first = build_script(variant())
    again = rebuild_script(variant(WIDER), edit_blink(board_text(first)))
    assert again.files and "kicad.outline.replaced" in codes(again)
    assert "layout.outline-kept" not in codes(again)
    assert again.design.board is not None and again.design.board.outline is not None
    found = edges(again)
    assert right_edge(again) == 160 * MM and len(found) == 4
    assert [g.native_ids["kicad"] for g in found] == list(signed_uuids(again.design.board.outline))
    read = read_board(board_text(again))
    assert read.board is not None
    kept = {item.native_ids["kicad"] for item in (*read.board.tracks, *read.board.vias)}
    assert set(EDIT_UUIDS) <= kept  # the segments and the via of the edit
    assert "kicad.outline.copper-dropped" not in codes(again)


def test_copper_that_no_longer_fits() -> None:
    text = board_text(build_script(variant()))
    gnd = net_ref(text, "GND")
    text = add_items(
        text,
        f'(segment (start 110 128) (end 120 128) (width 0.25) (layer "F.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000c0001"))',
        f'(segment (start 145 105) (end 148 105) (width 0.25) (layer "F.Cu") {gnd} '
        '(uuid "00000000-0000-4000-8000-0000000c0002"))',
    )
    again = rebuild_script(variant(NARROWER), text)
    assert again.files
    (dropped,) = [i for i in again.issues if i.code == "kicad.outline.copper-dropped"]
    assert dropped.severity == "warning" and "1 track," in dropped.message and "GND" in dropped.message
    read = read_board(board_text(again))
    assert read.board is not None
    uuids = {track.native_ids["kicad"] for track in read.board.tracks}
    assert "00000000-0000-4000-8000-0000000c0001" in uuids
    assert "00000000-0000-4000-8000-0000000c0002" not in uuids


def test_an_edited_outline_wins_unless_locked() -> None:
    text = edited(board_text(build_script(variant())))
    kept = rebuild_script(variant(WIDER), text)
    (issue,) = [i for i in kept.issues if i.code == "layout.outline-kept"]
    assert issue.severity == "warning" and issue.hint == OUTLINE_HINT and "locked=True" in issue.hint
    assert right_edge(kept) == 155 * MM
    forced = rebuild_script(variant(LOCKED), text)
    assert "kicad.outline.forced" in codes(forced) and "layout.outline-kept" not in codes(forced)
    assert right_edge(forced) == 160 * MM
    (issue,) = [i for i in forced.issues if i.code == "kicad.outline.forced"]
    assert issue.severity == "warning"


def test_outline_edited_in_kicad_and_the_script_unchanged() -> None:
    """Scenario "Outline edited in KiCad" of "Board content outside the design is kept"."""
    text = edited(board_text(build_script(variant())))
    again = rebuild_script(variant(), text)
    assert again.files and "layout.outline-kept" in codes(again)
    assert right_edge(again) == 155 * MM
    assert PRESERVE_ISSUE_CODES["layout.outline-kept"] == "warning"


def test_a_resaved_outline_keeps_its_signature() -> None:
    """The unit half of "A re-save keeps the signature": KiCad's re-save swaps the ends of a negatively
    oriented arc and keeps uuids and coordinates, so the edge texts and the signature do not change. The
    writer emits arcs positively oriented; the swap is made here by hand."""
    first = build_script(variant(ROUNDED))
    text = board_text(first)
    arc = "(gr_arc\n\t\t(start "
    assert text.count(arc) == 8
    head = text.index(arc)
    lines = text[head:].split("\n", 4)
    start, mid, end = lines[1], lines[2], lines[3]
    swapped = "\n".join(
        (lines[0], start.replace("(start", "(end"), mid, end.replace("(end", "(start"), lines[4])
    )
    resaved = text[:head] + swapped
    rounder = ROUNDED.replace("radius=mm(2)", "radius=mm(3)")
    again = rebuild_script(variant(rounder), resaved)
    assert "kicad.outline.replaced" in codes(again) and "layout.outline-kept" not in codes(again)


def test_a_zone_without_an_outline_follows() -> None:
    first = build_script(variant(append=POUR))
    again = rebuild_script(variant(WIDER, append=POUR), board_text(first))
    assert again.files and "kicad.zone.overridden" not in codes(again)
    read = read_board(board_text(again))
    assert read.board is not None
    (zone,) = read.board.zones
    corners = ((100, 100), (160, 100), (160, 130), (100, 130))
    assert zone.outline == tuple(Point(x * MM, y * MM) for x, y in corners)


def test_edges_of_an_older_fenolite() -> None:
    first = build_script(variant())
    assert first.design.board is not None and first.design.board.outline is not None
    outline = first.design.board.outline
    text = board_text(first)
    for index, graphic in enumerate(edges(first)):
        text = text.replace(graphic.native_ids["kicad"], position_uuid(outline, 0, index))
    assert text != board_text(first)
    same = rebuild_script(variant(), text)
    assert not [code for code in codes(same) if code.startswith(("kicad.outline.", "layout.outline-kept"))]
    assert [g.native_ids["kicad"] for g in edges(same)] == list(signed_uuids(outline))
    assert board_text(same) == board_text(first)  # the same lines under the uuids of this release
    other = rebuild_script(variant(WIDER), text)
    assert "layout.outline-kept" in codes(other) and right_edge(other) == 150 * MM
    assert [g.native_ids["kicad"] for g in edges(other)] == [position_uuid(outline, 0, k) for k in range(4)]


def test_edge_items_of_a_footprint_stay() -> None:
    text = add_to_footprint(
        board_text(build_script(variant())),
        "U1",
        "(fp_rect (start -1 -0.5) (end 1 0.5) (stroke (width 0.05) (type solid)) (fill no) "
        '(layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-0000000c0020"))',
    )
    again = rebuild_script(variant(WIDER), text)
    (issue,) = [i for i in again.issues if i.code == "kicad.outline.replaced"]
    assert "U1" in issue.message and right_edge(again) == 160 * MM
    written = board_text(again)
    assert "00000000-0000-4000-8000-0000000c0020" in written and "(fp_rect" in written
    assert len(board_outline(read_board(written)).rings) == 2


def test_a_rebuild_over_a_replaced_outline_is_stable() -> None:
    first = build_script(variant())
    replaced = rebuild_script(variant(WIDER), board_text(first))
    again = rebuild_script(variant(WIDER), board_text(replaced))
    assert not [code for code in codes(again) if code.startswith(("kicad.outline.", "layout.outline-kept"))]
    assert board_text(again) == board_text(replaced)
    assert board_text(replaced) == board_text(build_script(variant(WIDER)))  # as a fresh build writes it
    assert BOARD != WIDER
