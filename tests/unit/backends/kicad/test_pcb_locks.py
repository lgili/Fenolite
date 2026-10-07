# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``locked`` of a segment, an arc and a via in the board reader and writer (change c0108; capability
kicad-file-backend, "Copper locks on boards"; ``H-K-LOCK-FORM``). Hermetic: the oracle half is
``tests/kicad/board/test_copper_locks.py``."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import CANONICAL_ORDER, TRACK_FIELDS, VIA_FIELDS, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse, walk
from fenolite.core.errors import Issue
from fenolite.model.design import Design

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SEGMENT = ("start", "end", "width", "locked", "layer", "net", "uuid")
ARC = ("start", "mid", "end", "width", "locked", "layer", "net", "uuid")
VIA = ("at", "size", "drill", "layers", "locked", "net", "uuid")


def nodes(text: str, kind: str) -> list[Node]:
    return [node for _, node in walk(parse(text)) if node.name == kind]


def heads(node: Node) -> tuple[str, ...]:
    return tuple(child.name for child in node.nodes())


def rebuilt() -> str:
    """The authored board as Fenolite writes it for its own major: a text that a rebuild keeps."""
    text = write_board(read_board(FIXTURE), target=9).text
    assert write_board(read_board(text), target=9).text == text
    return text


def locked_design() -> Design:
    """The authored board with its first track, its arc and its via locked."""
    design = read_board(FIXTURE)
    board = design.board
    assert board is not None and len(board.tracks) >= 2 and board.arcs and board.vias
    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=(dataclasses.replace(board.tracks[0], locked=True), *board.tracks[1:]),
            arcs=(dataclasses.replace(board.arcs[0], locked=True), *board.arcs[1:]),
            vias=(dataclasses.replace(board.vias[0], locked=True), *board.vias[1:]),
        ),
    )


def test_lock_fields_and_order() -> None:
    assert TRACK_FIELDS["locked"] == "locked" and VIA_FIELDS["locked"] == "locked"
    assert CANONICAL_ORDER["segment"] == SEGMENT and CANONICAL_ORDER["arc"] == ARC
    assert tuple(name for name in CANONICAL_ORDER["via"] if name != "via_type") == VIA


@pytest.mark.parametrize("target", [9, 10])
def test_locks_written_where_kicad_writes_them(target: int) -> None:
    """Scenario "Locks written where KiCad writes them"."""
    text = write_board(locked_design(), target=target).text
    first, *others = nodes(text, "segment")
    assert heads(first) == SEGMENT and first.find("locked") == parse("(locked yes)")
    assert all("locked" not in heads(other) for other in others) and others
    (arc,) = nodes(text, "arc")
    assert heads(arc) == ARC
    (via,) = nodes(text, "via")
    assert heads(via) == VIA
    assert text.count("(locked yes)") == 3


@pytest.mark.parametrize("target", [9, 10])
def test_locks_read_and_a_board_with_locks_keeps_its_bytes(target: int) -> None:
    """Scenarios "Locks read" and, for a rebuilt board, "Same-version rebuild"."""
    text = write_board(locked_design(), target=target).text
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    board = design.board
    assert board is not None
    assert [track.locked for track in board.tracks] == [True, *[False] * (len(board.tracks) - 1)]
    assert [arc.locked for arc in board.arcs] == [True] and [via.locked for via in board.vias] == [True]
    assert not [issue for issue in issues if issue.code == "kicad.board.kept-opaque"]
    assert write_board(design, target=target).text == text
    # unlocking in the model removes the child
    unlocked = dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=tuple(dataclasses.replace(t, locked=False) for t in board.tracks),
            arcs=tuple(dataclasses.replace(a, locked=False) for a in board.arcs),
            vias=tuple(dataclasses.replace(v, locked=False) for v in board.vias),
        ),
    )
    assert "(locked" not in write_board(unlocked, target=target).text


def test_lock_read_as_the_first_child_keeps_its_place() -> None:
    """A lock that another tool wrote first is read, and a read entity keeps its order."""
    text = rebuilt()
    for kind in ("segment", "arc", "via"):
        head = f"\t({kind}\n"
        assert head in text
        text = text.replace(head, f"{head}\t\t(locked yes)\n", 1)
    design = read_board(text)
    assert design.board is not None
    assert design.board.tracks[0].locked and design.board.arcs[0].locked and design.board.vias[0].locked
    assert not design.board.tracks[1].locked
    assert write_board(design, target=9).text == text


def test_lock_no_is_unlocked_and_kept_as_written() -> None:
    """``(locked no)`` gives ``False``; the writer would not write it, so it is kept, with its info."""
    text = rebuilt()
    head = "\t(segment\n"
    text = text.replace(head, f"{head}\t\t(locked no)\n", 1)
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert design.board is not None and not design.board.tracks[0].locked
    kept = [issue for issue in issues if issue.code == "kicad.board.kept-opaque"]
    assert len(kept) == 1 and kept[0].severity == "info"
    assert write_board(design, target=9).text == text


def test_lock_with_another_value_reads_as_locked() -> None:
    text = rebuilt()
    head = "\t(via\n"
    text = text.replace(head, f"{head}\t\t(locked maybe)\n", 1)
    design = read_board(text)
    assert design.board is not None and design.board.vias[0].locked
    assert write_board(design, target=9).text == text
