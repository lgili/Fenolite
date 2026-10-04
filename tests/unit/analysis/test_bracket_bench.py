# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the recorded KiCad bracket, built without KiCad (capability board-analyses, "KiCad
creepage bracket is recorded", scenario "Bench is hermetic to build"; change c0047)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _analysis import BRACKET_NM, CANARY_NETS, creep_bench

from fenolite.analysis import analyze_distances, board_boundary
from fenolite.analysis.report import DistanceRow
from fenolite.backends.kicad.pcb import read_board, write_board


@pytest.mark.parametrize(("name", "wanted"), [("slot", 11_000_000), ("edge", 5_100_000)])
def test_bench_is_hermetic_to_build(name: str, wanted: int, tmp_path: Path) -> None:
    bench = creep_bench(name)
    assert bench.creepage == wanted
    for target in (9, 10):
        path = tmp_path / f"{name}-{target}.kicad_pcb"
        path.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        design = read_board(path)
        assert design.board is not None
        boundary = board_boundary(design.board, thickness=bench.thickness)
        assert boundary.source == "edge"
        report = analyze_distances(design, pads=None, boundary=boundary, pairs=(("A", "B"),))
        (row,) = report.rows
        assert isinstance(row, DistanceRow) and row.creepage is not None
        assert (row.creepage.low, row.creepage.high) == (wanted, wanted + 2)
        assert {net.name for net in design.circuit.nets} >= {"A", "B", *CANARY_NETS}


def test_rules_text_brackets_the_value() -> None:
    bench = creep_bench("edge")
    below, above = bench.rules(bench.creepage - BRACKET_NM), bench.rules(bench.creepage + BRACKET_NM)
    assert below.startswith("(version 1)\n(rule canary\n")
    assert "(constraint creepage (min 5.05mm))" in below and "(constraint creepage (min 5.15mm))" in above
    assert "A.NetName == 'A' && B.NetName == 'B'" in below
    with pytest.raises(KeyError):
        creep_bench("other")
