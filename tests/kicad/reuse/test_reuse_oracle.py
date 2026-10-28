# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --strategy reuse`` judged by the running ``kicad-cli`` (change c0210; capability
layout-reuse, "Reuse strategy of place"; hypothesis ``H-K-REUSE-DRC``), on the authored bench of
``tests/_reusebench.py`` written for the tool's major with its project and library."""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner
from _reusebench import project_files, reference, target

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import main as cli_main
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad


def _write(folder: Path, design: Design) -> Path:
    for name, text in project_files(design, major=major()).items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (folder / "reference.kicad_pcb").write_text(
        write_board(reference(), target=major()).text, encoding="utf-8", newline="\n"
    )
    return folder / "target.kicad_pcb"


def _drc(board: Path) -> Counter[str]:
    report = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    found = (*report.report.violations, *report.report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


def place(monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(folder)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    argv = ["place", "target.kicad_pcb", "--from", "reference.kicad_pcb", "--drc"]
    code = cli_main.main([*argv, *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_a_copied_block_adds_no_drc_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The block is placed by its pads, ``R4`` on the bottom, with ``in`` and ``out`` copied: KiCad finds
    no violation type with more entries, and two fewer unconnected items."""
    board = _write(tmp_path, target())
    before = _drc(board)
    code, env = place(monkeypatch, tmp_path, "--only", "U1,R1,R2,R3,R4", "--copper", "--confirm")
    assert code == 0, env
    reuse = env["result"]["reuse"]
    assert reuse["drc"]["new"] == [] and "H-K-REUSE-DRC" in env["evidence"]["hypotheses"]
    assert reuse["copper"]["copied"] == 2
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)
    assert before["unconnected_items"] - after["unconnected_items"] == 2
