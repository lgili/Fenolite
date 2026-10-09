# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper locks against ``kicad-cli`` (change c0108; capability kicad-oracle, "Copper locks pass the
oracle"; ``H-K-LOCK-FORM``).

``pcb-lock-form`` (KiCad 10, which has ``pcb upgrade``): KiCad saves the bench again with the children
Fenolite wrote. ``pcb-lock-load`` (both majors): the bench with locks is judged as the bench without.
"""

from __future__ import annotations

import _lockbench as lb
import pytest

from fenolite.backends.kicad.pcb import read_board, write_board

pytestmark = pytest.mark.needs_kicad


@pytest.mark.kicad_min_major(10)
def test_form_kicad_keeps_the_place_of_a_lock() -> None:
    """Scenario "KiCad 10 keeps the place of a lock"."""
    written, saved = lb.resaved()
    ours, theirs = lb.copper_nodes(written), lb.copper_nodes(saved)
    uuids = lb.lock_bench(10)[1]
    for label, uuid in uuids.items():
        assert uuid in theirs, f"{label}: the uuid is gone after the save"
        assert lb.compact(theirs[uuid]) == lb.compact(ours[uuid]), label
    assert lb.children(theirs[uuids["locked-segment"]]) == lb.SEGMENT_ORDER
    assert lb.children(theirs[uuids["locked-arc"]]) == lb.ARC_ORDER
    assert lb.children(theirs[uuids["locked-via"]]) == lb.VIA_ORDER
    assert "locked" not in lb.children(theirs[uuids["free-segment"]])
    assert lb.form_outcome() == "equal"


@pytest.mark.kicad_min_major(10)
def test_form_a_lock_written_first_is_moved() -> None:
    """The 10.0.6 record of where ``pcb upgrade --force`` puts a lock that a token edit wrote as the first
    child: after ``width`` (segment, arc) and after ``layers`` (via), the uuids kept."""
    saved = lb.copper_nodes(lb.resaved_lock_first())
    uuids = lb.lock_bench(10, locked=False)[1]
    assert lb.children(saved[uuids["locked-segment"]]) == lb.SEGMENT_ORDER
    assert lb.children(saved[uuids["locked-arc"]]) == lb.ARC_ORDER
    assert lb.children(saved[uuids["locked-via"]]) == lb.VIA_ORDER
    assert "locked" not in lb.children(saved[uuids["free-segment"]])
    # read by Fenolite, the saved board holds the three locks and its copper is written back as saved
    design = read_board(lb.resaved_lock_first())
    assert design.board is not None
    assert [track.locked for track in design.board.tracks] == [True, False]
    assert [arc.locked for arc in design.board.arcs] == [True]
    assert [via.locked for via in design.board.vias] == [True]
    rebuilt = lb.copper_nodes(write_board(design, target=10).text)
    assert {uuid: lb.compact(node) for uuid, node in rebuilt.items()} == {
        uuid: lb.compact(node) for uuid, node in saved.items()
    }


def test_load_both_majors_judge_locked_copper_as_unlocked() -> None:
    """Scenario "Both majors load locked copper"."""
    locked, free = lb.reports()
    assert locked is not None and free is not None, "kicad-cli wrote no DRC report for the bench"
    assert locked.entries() == free.entries()
    assert locked.unconnected_items == ()
    assert lb.load_outcome() == "equal"
