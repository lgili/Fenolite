# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Renamed footprints pass the oracle (capability kicad-oracle, "Renamed footprints pass the oracle";
hypothesis H-K-LENS-RENAME; change c0069): the lens acceptance fixture, rebuilt with its module ``power``
renamed ``supply``, loads at its edited placements, keeps the DRC report of the edited board, and keeps
its group and uuids through a re-save on 10.0."""

from __future__ import annotations

import _renamecases as rn
import pytest
from _lensfix import PATHS, TRACKS
from _probes import run

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("target", TARGETS)
def test_renamed_module_loads_and_keeps_its_drc(target: int) -> None:
    text = rn.text_of(rn.rebuilt_files(target))
    assert rn.group_is_renamed(text), "the group does not list the renamed footprints by their new uuids"
    assert rn.loads_at_its_placements(target), "pcb export pos differs between the edited and rebuilt board"
    assert rn.same_drc(target), "the DRC report changed with the rename"
    rows = rn.pos_rows(rn.rebuilt_files(target))
    assert set(PATHS) <= set(rows)
    board = read_board(text).board
    assert board is not None and {t.native_ids["kicad"] for t in board.tracks} == {u for u, *_ in TRACKS}
    assert run(f"lens-rename-t{target}") == "equal"


@pytest.mark.kicad_min_major(10)
def test_resave_keeps_the_group_and_the_uuids() -> None:
    assert rn.resave_keeps_identity()
    assert len(rn.renamed_uuids(rn.text_of(rn.rebuilt_files(10)))) > 20


@pytest.mark.kicad_min_major(10)
def test_second_rebuild_identical() -> None:
    """Without the ``moved()`` call the next build writes the same files."""
    from _lensfix import drop_alias, edit_script

    first = rn.rebuilt_files(10)
    assert rn.rebuild(first, 10, drop_alias(edit_script(rn.script()))) == first
