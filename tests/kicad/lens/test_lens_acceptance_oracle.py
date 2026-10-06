# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The boards of the lens acceptance on KiCad (capability layout-lens, "Lens acceptance fixture"; change
c0069): the rebuilt board and the board built from the source tree alone, with ``placements.toml`` and no
existing layout, both load and place every footprint where the edited board had it."""

from __future__ import annotations

import _renamecases as rn
import pytest
from _buildhelp import build
from _lensfix import PATHS, edit_script, renamed

from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import BOARD_ORIGIN, placements, to_model
from fenolite.lens.extract import extract_placements
from fenolite.lens.placements import read_placements, write_placements
from fenolite.lens.preserve import ExistingProject, match_footprints, prepare

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


def restored_files(target: int) -> rn.Files:
    """The renamed script built without a layout, placed by the file that ``sync`` would write from the
    rebuilt board."""
    made = rn.design(edit_script(rn.script()))
    model = to_model(made)
    board = read_board(rn.text_of(rn.rebuilt_files(target)))
    extracted = extract_placements(board, match_footprints(model, board), design=model)
    text = write_placements(extracted.placements, origin=BOARD_ORIGIN)
    source = read_placements(text, origin=BOARD_ORIGIN).entries
    assert sorted(source) == sorted(renamed(path) for path in PATHS.values())
    ready = prepare(model, placements(made), ExistingProject(), name=made.name, source=source)
    output = build(made, target, prepared=ready, placements_override=ready.placements)
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


@pytest.mark.parametrize("target", TARGETS)
def test_rebuilt_and_restored_boards_load(target: int) -> None:
    edited = rn.pos_rows(rn.input_files(target))
    rebuilt = rn.pos_rows(rn.rebuilt_files(target))
    restored_board = restored_files(target)
    restored = rn.pos_rows(restored_board)
    assert set(edited) == set(PATHS)
    for ref, row in edited.items():
        assert rebuilt[ref] == row, f"{ref}: the rebuilt board moved it"
        assert restored[ref] == row, f"{ref}: the board built from placements.toml moved it"
    assert "R9" in rebuilt and "R9" in restored
    # the restored board has no routing, so only its loading is judged: a report exists
    assert rn.drc(restored_board) is not None
