# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --turn`` and the zones of ``--strategy reuse`` judged by the running ``kicad-cli``
(change c0227; capability layout-reuse, "Group moves" and "Zones of a copied block"; hypotheses
``H-K-GROUP-DRC`` and ``H-G-REUSE-ZONE``), on the authored benches of ``tests/_groupbench.py`` and
``tests/_reusebench.py`` written for the tool's major with their project and library."""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _groupbench import GROUP, module
from _probes import major, runner
from _reusebench import project_files, reference, target, with_zones

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import main as cli_main
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad


def _write(folder: Path, design: Design, name: str) -> Path:
    for file, text in project_files(design, name=name, major=major()).items():
        path = folder / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return folder / f"{name}.kicad_pcb"


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
    code = cli_main.main(["place", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_a_turned_group_adds_no_drc_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``H-K-GROUP-DRC``: the module turned by 90° with its satellites, two of them on the bottom, gives
    no violation type more entries and no more unconnected items."""
    board = _write(tmp_path, module(), "board")
    before = _drc(board)
    code, env = place(
        monkeypatch, tmp_path, board.name, "--turn", ",".join(GROUP), "--about", "20mm,20mm", "--angle", "90",
        "--confirm",
    )  # fmt: skip
    assert code == 0, env
    assert env["result"]["group"]["copper"]["items"] == 8
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)


def test_a_copied_zone_adds_no_drc_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``H-G-REUSE-ZONE``: the block copied with its ground pour gives no
    violation type more entries with ``--drc``."""
    board = _write(tmp_path, target(), "target")
    (tmp_path / "reference.kicad_pcb").write_text(
        write_board(with_zones(reference()), target=major()).text, encoding="utf-8", newline="\n"
    )
    before = _drc(board)
    code, env = place(
        monkeypatch, tmp_path, board.name, "--from", "reference.kicad_pcb", "--only", "U1,R1,R2,R3,R4",
        "--copper", "--drc", "--confirm",
    )  # fmt: skip
    assert code == 0, (env["issues"], env["result"]["reuse"]["drc"])
    reuse = env["result"]["reuse"]
    assert (
        reuse["drc"]["new"] == [] and [item["kind"] for item in reuse["copper"]["items"]].count("zone") == 1
    )
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)
