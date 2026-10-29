# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed test points judged by KiCad's DRC (capability assembly-test-features, "Placed test points";
change c0229; hypothesis ``H-K-TP-PLACE``). The boards are the authored benches of ``tests/_tpbench.py``;
``fenolite testpoints --place --drc`` runs ``kicad-cli`` DRC on the board before and after."""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner
from _tpbench import blocked, covered

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import main as cli_main
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
LIBRARY = {"lib_footprint_issues", "lib_footprint_mismatch"}


def _drc(board: Path) -> Counter[str]:
    report = runner().drc(board)
    assert report.report is not None
    found = (*report.report.violations, *report.report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


def run(
    monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(folder)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["testpoints", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


@pytest.mark.parametrize(
    ("bench", "side", "probes"),
    [(covered, "bottom", 6), (covered, "top", 6), (blocked, "bottom", 6)],
    ids=["covered-bottom", "covered-top", "blocked-bottom"],
)
def test_kicad_finds_nothing_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bench: Any, side: str, probes: int
) -> None:
    """Scenario "KiCad finds nothing new": no DRC type grows but the library table's."""
    design: Design = bench()
    board = tmp_path / "probes.kicad_pcb"
    board.write_text(write_board(design, target=major()).text, encoding="utf-8", newline="\n")
    before = _drc(board)
    code, env, err = run(monkeypatch, tmp_path, board.name, "--place", "--side", side, "--drc", "--confirm")
    assert code == 0, err
    place = env["result"]["place"]
    assert len(place["probes"]) == probes and place["drc"]["new"] == []
    assert env["evidence"]["level"] == "KICAD-VERIFIED"
    after = _drc(board)
    grown = {kind for kind in after if after[kind] > before.get(kind, 0)}
    assert grown <= LIBRARY, (before, after)
    assert after["unconnected_items"] == before["unconnected_items"]


def test_library_types_grow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The fact behind ``LIBRARY_TYPES``: each probe of a library in no table gives one more
    ``lib_footprint_issues``."""
    board = tmp_path / "probes.kicad_pcb"
    board.write_text(write_board(covered(), target=major()).text, encoding="utf-8", newline="\n")
    before = _drc(board)
    code, _, err = run(monkeypatch, tmp_path, board.name, "--place", "--side", "bottom", "--confirm")
    assert code == 0, err
    after = _drc(board)
    assert after["lib_footprint_issues"] == before["lib_footprint_issues"] + 6
