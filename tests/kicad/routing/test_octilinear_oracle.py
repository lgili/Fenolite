# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite route --router octilinear`` judged by the running ``kicad-cli`` (change c0228; capability
routing, "Octilinear shapes" and "Octilinear pairs"; hypothesis ``H-K-OCTI-DRC``), on the authored gate
loop and sense pair of ``tests/_octibench.py`` written for the tool's major with their project and
library."""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _octibench import gate_loop, sense
from _probes import major, runner
from _reusebench import project_files

from fenolite.cli import main as cli_main
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

BENCHES = {"gate": (gate_loop, ("--nets", "GATE", "--nets", "KSRC")), "sense": (sense, ())}


def _write(folder: Path, design: Design) -> Path:
    for file, text in project_files(design, name="bench", major=major()).items():
        path = folder / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return folder / "bench.kicad_pcb"


def _drc(board: Path) -> tuple[Counter[str], int]:
    report = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    violations = Counter(item.type for item in report.report.violations if not item.excluded)
    unconnected = sum(1 for item in report.report.unconnected_items if not item.excluded)
    return violations, unconnected


def _route(monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(folder)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    code = cli_main.main(["route", "bench.kicad_pcb", "--router", "octilinear", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


@pytest.mark.parametrize("bench", sorted(BENCHES))
def test_routed_bench_passes_drc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bench: str) -> None:
    """``H-K-OCTI-DRC``: after the route no violation type has more entries, and nothing is unconnected
    where the bench before had open connections."""
    build, nets = BENCHES[bench]
    board = _write(tmp_path, build())
    before, open_before = _drc(board)
    code, env = _route(monkeypatch, tmp_path, *nets, "--confirm")
    assert code == 0 and env["result"]["unrouted"] == [], env
    after, open_after = _drc(board)
    assert open_before > 0 and open_after == 0, (open_before, open_after)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)


@pytest.mark.parametrize("bench", sorted(BENCHES))
def test_gate_drops_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bench: str) -> None:
    """With ``--gate drc`` the gate keeps every track and the reply is ``KICAD-VERIFIED``."""
    build, nets = BENCHES[bench]
    _write(tmp_path, build())
    code, env = _route(monkeypatch, tmp_path, *nets, "--gate", "drc", "--confirm")
    assert code == 0, env
    gate = env["result"]["gate"]
    assert gate["dropped"] == [] and gate["findings"] == [], gate
    assert env["result"]["unrouted"] == [] and env["evidence"]["level"] == "KICAD-VERIFIED"
