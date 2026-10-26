# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Undeclared-layer precondition and refusal (c0161 tasks 1.4/2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.layers import undeclared_layers
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.errors import FenoliteError

ROOT = Path(__file__).resolve().parents[4]


def test_census_committed_boards() -> None:
    checked = 0
    for path in sorted((ROOT / "tests/data").rglob("*.kicad_pcb")):
        try:
            design = read_board(path)
        except (FenoliteError, ValueError):
            continue  # intentionally invalid reader fixtures
        assert design.board is not None
        assert not undeclared_layers(design.board), (path.relative_to(ROOT), undeclared_layers(design.board))
        checked += 1
    assert checked > 20


def test_census_examples_and_scripts() -> None:
    import dataclasses

    from fenolite.backends.kicad.layers import created_layers
    from fenolite.cli._script import run_design_script
    from fenolite.dsl import to_model

    paths = sorted((ROOT / "examples").rglob("*.py"))
    paths += sorted((ROOT / "tests/data").rglob("design.py"))
    checked = 0
    for path in paths:
        # Only executable design scripts, not import-only support modules.
        text = path.read_text()
        if "Design(" not in text:
            continue
        script = run_design_script(path).design
        design = to_model(script)
        if design.board is not None:
            # The build installs exactly this table before resolving footprints.
            board = dataclasses.replace(design.board, layers=created_layers(script.copper))
            assert not undeclared_layers(board), path.relative_to(ROOT)
            checked += 1
    assert checked >= 8


@pytest.mark.parametrize("allow_lossy", (False, True))
def test_undeclared_layer_is_not_droppable(allow_lossy: bool) -> None:
    import dataclasses

    from fenolite.backends.kicad.pcb import write_board
    from fenolite.backends.kicad.versions import LossyWriteError
    from fenolite.core.coords import Point
    from fenolite.model.board import Graphic

    design = read_board(ROOT / "tests/data/kicad/board/two_layer.kicad_pcb")
    assert design.board is not None
    graphic = Graphic(
        id="gra-undeclared",
        kind="line",
        layer="Mech.1",
        points=(Point(0, 0), Point(1000000, 0)),
        width=100000,
    )
    design = dataclasses.replace(
        design, board=dataclasses.replace(design.board, graphics=(*design.board.graphics, graphic))
    )
    with pytest.raises(LossyWriteError) as caught:
        write_board(design, allow_lossy=allow_lossy)
    assert not caught.value.droppable
    issue = caught.value.issues[0]
    assert issue.code == "kicad.board.layer-undeclared" and issue.where == "Mech.1"
    assert "1 item" in issue.message
