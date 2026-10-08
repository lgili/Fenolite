# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the recorded KiCad probes of change c0115 are built without KiCad (capability
board-analyses, "Power and insulation KiCad probes", scenario "Benches are hermetic to build")."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from _analysis import MM

from fenolite.analysis import analyze_distances, board_boundary
from fenolite.analysis.fills import fill_regions
from fenolite.analysis.report import DistanceRow
from fenolite.analysis.section import Port, narrowest_section
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.geometry import Thick

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kicad" / "analysis"))
import _powerbench  # noqa: E402  (the benches live beside the probes that run them)


def creepage(name: str) -> int:
    design = _powerbench.bench(name)
    assert design.board is not None
    report = analyze_distances(design, pads=None, boundary=board_boundary(design.board), pairs=(("A", "B"),))
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None
    return row.creepage.low


@pytest.mark.parametrize("name", _powerbench.BENCHES)
def test_bench_reads_back(name: str, tmp_path: Path) -> None:
    design = _powerbench.bench(name)
    text = write_board(design, target=10).text
    path = tmp_path / "bench.kicad_pcb"
    path.write_text(text, encoding="utf-8", newline="\n")
    back = read_board(path.read_text(encoding="utf-8"))
    assert back.board is not None and design.board is not None
    assert len(back.board.tracks) == len(design.board.tracks) and len(back.board.zones) == len(
        design.board.zones
    )
    assert "canary" in _powerbench.rules(name) and _powerbench.project(name).strip().startswith("{")
    assert _powerbench.PROBE_IDS[name] and _powerbench.MAJORS[name] == (10,)


def test_fenolite_values_on_the_benches() -> None:
    assert creepage("groove-slot") == 11 * MM
    assert creepage("creepage-split") == 8 * MM  # over the track of the third net, which KiCad stops at
    (region,), left_out = fill_regions(_powerbench.bench("neck-plain"))
    assert left_out == 0
    shift = 20 * MM
    ports = [
        Port(name, (Thick((Point(x * MM + shift, 5 * MM + shift),), MM),))
        for name, x in (("a", 5), ("b", 18))
    ]
    assert narrowest_section(region, ports[0], ports[1]).measure.low == 2 * MM


@pytest.mark.parametrize("name", _powerbench.NINE)
def test_nine_bench_writes_for_target_nine(name: str) -> None:
    """The benches that also run on KiCad 9 are written for target 9, ``neck-plain`` with its stored fill."""
    design = _powerbench.bench(name)
    back = read_board(write_board(design, target=9).text)
    assert back.board is not None and design.board is not None
    assert len(back.board.tracks) == len(design.board.tracks)
    if name == "neck-plain":
        (zone,) = back.board.zones
        assert zone.fills and fill_regions(back)[1] == 0
