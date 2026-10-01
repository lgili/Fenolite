# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written boards in both net forms load and keep their nets (capability kicad-oracle; hypotheses
H-K-TOK-NETNAME and H-K-TOK-OBSOLETE; change c0017).

The triad and ``two_layer.kicad_pcb`` are written for every target the running major loads; each text
loads, and the net partition of ``pcb export ipcd356`` equals the model's nets.
"""

from __future__ import annotations

from pathlib import Path

import _triad
import pytest
from _boards import FIXTURE
from _frame import pad_report
from _probes import major, run, runner

from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
TARGETS = [9, 10]


def design_of(name: str, target: int) -> Design:
    return _triad.triad(target) if name == "triad" else read_board(FIXTURE)


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("name", ["triad", "two-layer"])
def test_written_board_keeps_its_nets(name: str, target: int, tmp_path: Path) -> None:
    if target > major():
        pytest.skip(f"KiCad {major()} does not load target {target}")
    assert run(f"pcb-write-{name}-{target}") == "load"
    design = design_of(name, target)
    board = tmp_path / "board.kicad_pcb"
    board.write_text(write_board(design, target=target).text, encoding="utf-8")
    report = pad_report(design, read_ipcd356(runner().export_ipcd356(board)))
    assert report.problems == [] and report.matched > 0


@pytest.mark.parametrize("target", TARGETS)
def test_led_net_of_the_authored_board(target: int, tmp_path: Path) -> None:
    if target > major():
        pytest.skip(f"KiCad {major()} does not load target {target}")
    board = tmp_path / "board.kicad_pcb"
    board.write_text(write_board(read_board(FIXTURE), target=target).text, encoding="utf-8")
    records = read_ipcd356(runner().export_ipcd356(board)).records
    nets = {(r.ref, r.pin): r.net for r in records}
    assert nets[("R1", "2")] == nets[("D1", "2")] == "LED_A"
