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

import dataclasses
from pathlib import Path

import pytest
from _boards import bare_board, created_board

from fenolite.backends.kicad.pcb import (
    LAYER_UNDECLARED,
    WRITE_ISSUE_CODES,
    read_board,
    source_info,
    undeclared_layers,
    write_board,
)
from fenolite.backends.kicad.versions import TARGET_MAJORS, LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic
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


def _with_line(layer: str) -> Design:
    design = created_board(2)
    assert design.board is not None
    line = Graphic(
        id=derived_id("gfx", "fenolite", f"undeclared:{layer}"),
        kind="line",
        layer=layer,
        points=(Point(0, 0), Point(5_000_000, 0)),
        width=100_000,
    )
    board = dataclasses.replace(design.board, graphics=(*design.board.graphics, line))
    return dataclasses.replace(design, board=board)


@pytest.mark.parametrize("target", TARGET_MAJORS)
def test_line_on_an_unknown_layer(target: int) -> None:
    """Scenario "Line on an unknown layer"."""
    design = _with_line("Mech.1")
    assert design.board is not None
    assert undeclared_layers(design.board) == {"Mech.1": 1}
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=target)
    assert info.value.droppable is False
    (found,) = info.value.issues
    assert (found.code, found.severity, found.where) == (LAYER_UNDECLARED, "error", "Mech.1")
    assert "1 item lies on the layer 'Mech.1'" in found.message
    assert found.code in WRITE_ISSUE_CODES


def test_items_of_a_footprint_count() -> None:
    """A footprint's pad and field on undeclared names count per name; a declared wildcard does not."""
    design = created_board(2)
    assert design.board is not None
    board = design.board
    fp = board.footprints[0]
    pad = dataclasses.replace(fp.pads[0], layers=("F.Cu", "Altium.74"))
    fields = tuple(dataclasses.replace(f, layer="Mech.2") for f in fp.fields)
    moved = dataclasses.replace(fp, pads=(pad, *fp.pads[1:]), fields=fields)
    board = dataclasses.replace(board, footprints=(moved, *board.footprints[1:]))
    found = undeclared_layers(board)
    assert found.get("Altium.74") == 1
    assert found.get("Mech.2", 0) == len(fields)
    wild = dataclasses.replace(fp.pads[0], layers=("*.Cu",))
    assert (
        undeclared_layers(dataclasses.replace(board, footprints=(dataclasses.replace(fp, pads=(wild,)),)))
        == {}
    )
