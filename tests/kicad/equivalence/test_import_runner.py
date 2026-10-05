# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadCli.import_board`` and ``altium_import.import_design`` with the real ``kicad-cli`` 10.0
(capability design-equivalence, "Board import runner"; change c0045; ``H-K-00``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _projects import tree_snapshot
from _resources import kicad_cli

from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import IMPORT_REPORT, IMPORTED_BOARD, KicadCli, cli_for

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
PCBDOC = Path(__file__).resolve().parents[2] / "data" / "altium" / "blink" / "blink.PcbDoc"


def _cli() -> KicadCli:
    path = kicad_cli()
    assert path is not None
    return cli_for(Path(path), timeout=300)


def test_import_of_the_committed_document() -> None:
    before = tree_snapshot(PCBDOC.parent)
    found = altium_import.import_design(_cli(), PCBDOC)
    design = found.read.design
    assert design.board is not None and len(design.board.footprints) == 3
    assert sorted(c.ref for c in design.circuit.components) == ["D1", "R1", "U1"]
    assert found.tool_version.startswith("10.")
    assert all(m.startswith(("warning: ", "error: ")) for m in found.messages)
    assert not any("fenolite-kicad-" in m for m in found.messages)
    assert tree_snapshot(PCBDOC.parent) == before


def test_the_run_writes_a_board_and_a_json_report() -> None:
    run = _cli().import_board(PCBDOC)
    assert run.run.ok and run.board is not None and run.board.startswith(b"(kicad_pcb")
    assert isinstance(run.report, dict)
    assert {IMPORTED_BOARD, IMPORT_REPORT} <= set(run.run.outputs)
