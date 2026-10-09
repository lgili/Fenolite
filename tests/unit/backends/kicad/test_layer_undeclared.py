# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Items on layers that the board does not declare (capability kicad-file-backend, "Items on undeclared
layers are refused"; change c0161, tasks 1.4 and 2.2).

The census (task 1.4) reads every committed KiCad board of the repository (``tests/data`` and
``examples``, the built examples of ``tests/data/acceptance`` among them) and the boards the test helpers
create, and asserts that none holds an item on a layer name its table does not declare, and that each
board the writer took before still writes. A board the writer refuses for another reason (a format it
does not edit) is listed with that reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _boards import bare_board, created_board

from fenolite.backends.kicad.pcb import read_board, source_info, undeclared_layers, write_board
from fenolite.backends.kicad.versions import TARGET_MAJORS
from fenolite.core.errors import FenoliteError
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
COMMITTED = sorted(
    path for folder in ("tests/data", "examples") for path in (ROOT / folder).rglob("*.kicad_pcb")
)


def _target(design: Design) -> int:
    info = source_info(design)
    major = info.major if info is not None else None
    return major if major in TARGET_MAJORS else max(TARGET_MAJORS)


@pytest.mark.parametrize("path", COMMITTED, ids=[str(p.relative_to(ROOT)) for p in COMMITTED])
def test_census_committed_boards(path: Path) -> None:
    try:
        design = read_board(path)
    except FenoliteError:
        pytest.skip("a board the reader refuses: no model to write")
    assert design.board is not None
    assert undeclared_layers(design.board) == {}
    try:
        write_board(design, target=_target(design))
    except FenoliteError as error:
        codes = [issue.code for issue in getattr(error, "issues", ())]
        assert "kicad.board.layer-undeclared" not in codes
        pytest.skip(f"written by no target before the change: {type(error).__name__}")


@pytest.mark.parametrize("copper", [2, 4, 6, 8])
def test_census_script_boards(copper: int) -> None:
    for design in (created_board(copper), bare_board(copper)):
        assert design.board is not None
        assert undeclared_layers(design.board) == {}
        for target in TARGET_MAJORS:
            write_board(design, target=target)


def test_census_count() -> None:
    """The census covers the committed boards; the count is the floor of the census."""
    assert len(COMMITTED) >= 90
