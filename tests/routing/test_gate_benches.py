# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the feasibility gate of change c0110 build (task 1.3): the pair, name, QFN and BGA benches
of ``_routepairbench``, ``_namebench`` and ``_escapebench``, each built by ``fenolite build`` for targets 9
and 10 into a temporary folder. ``test_bench_builds`` needs no tool; ``test_bench_loads`` loads the board of
the running major in ``kicad-cli`` (the ``routing`` jobs of CI, the local ``kicad-cli``)."""

from __future__ import annotations

from pathlib import Path

import _escapebench as eb
import _gate as gate
import _namebench as nb
import _routepairbench as pairb
import pytest

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board

BENCHES = {
    "pair": ("_routepairbench", "bench_design", {}, pairb.NETS),
    "name": ("_namebench", "bench_design", {}, nb.NETS),
    "qfn": ("_escapebench", "bench_design", {"kind": "qfn"}, (*eb.QFN_SIGNALS, "GND", "VCC")),
    "bga": ("_escapebench", "bench_design", {"kind": "bga"}, (*eb.BGA_SIGNALS, "GND", "VCC")),
}
PADS = {"pair": 16, "name": 20, "qfn": 49 + 40, "bga": 121 + 100}
CASES = [pytest.param(name, target, id=f"{name}-t{target}") for name in BENCHES for target in (9, 10)]


def _build(tmp_path: Path, name: str, target: int) -> Path:
    module, function, arguments, _nets = BENCHES[name]
    return gate.build(module, function, tmp_path / f"{name}-t{target}", target, **arguments)


@pytest.mark.parametrize(("name", "target"), CASES)
def test_bench_builds(name: str, target: int, tmp_path: Path) -> None:
    """The bench builds; its board holds the nets and pads of the design of c0110."""
    board = _build(tmp_path, name, target)
    design = read_board(board.read_text(encoding="utf-8"))
    assert design.board is not None
    nets = {net.name for net in design.circuit.nets}
    assert set(BENCHES[name][3]) <= nets, sorted(set(BENCHES[name][3]) - nets)
    pads = board_pads(design)
    assert len(pads) == PADS[name]
    copper = [layer.name for layer in design.board.layers if layer.kind == "copper"]
    assert copper == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]


@pytest.mark.needs_kicad
@pytest.mark.parametrize("name", list(BENCHES))
def test_bench_loads(name: str, tmp_path: Path) -> None:
    """``kicad-cli`` of this machine loads the bench built for its own major: ``pcb drc`` writes a report."""
    target = 10 if gate.running_major() >= 10 else 9
    board = _build(tmp_path, name, target)
    report = gate.drc(board)
    found = (len(report.violations), len(report.unconnected_items))
    print(f"{name}-t{target}: {found[0]} violation(s), {found[1]} unconnected item(s)")
