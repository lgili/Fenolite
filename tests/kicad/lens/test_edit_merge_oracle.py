# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of the edit merge acceptance loop on KiCad (capability edit-merge, "Merged files accepted by
KiCad"; change c0250): the board and the schematic that the loop rebuilds over a value, a footprint, a
reference, a user property and positions edited by token edit load in ``kicad-cli``, and its DRC and ERC
report nothing that the unedited build does not have."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest
from _edit_help import FIXTURE, FIXTURE_NAME, edit_fixture, issues
from _probes import runner
from _project import Project

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
SWAPPED = "lib_footprint_mismatch"
"""The DRC finding of ``R2``, whose footprint id the token edit swaps without KiCad's new pads: KiCad's
"Change Footprint" would replace them, so the merged board is judged without it for that one footprint."""


def _files(folder: Path, keep: str) -> dict[str, Path]:
    return {
        path.relative_to(folder).as_posix(): path
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != keep and not path.name.endswith(".bak")
    }


def _drc(folder: Path) -> tuple[Counter[tuple[str, str]], int]:
    board = folder / f"{FIXTURE_NAME}.kicad_pcb"
    report = runner().drc(board, files=_files(folder, board.name)).report
    assert report is not None, f"{board}: kicad-cli wrote no DRC report"
    found = Counter((v.type, v.severity) for v in report.violations if v.type != SWAPPED)
    return found, len(report.unconnected_items)


def _erc(folder: Path) -> Counter[tuple[str, str]]:
    sheet = folder / f"{FIXTURE_NAME}.kicad_sch"
    report = runner().erc(sheet, files=_files(folder, sheet.name)).report
    assert report is not None, f"{sheet}: kicad-cli wrote no ERC report"
    return Counter((v.type, v.severity) for v in report.violations)


@pytest.mark.parametrize("target", TARGETS)
def test_merged_files_accepted_by_kicad(target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    p = Project(tmp_path, monkeypatch, target, folder=FIXTURE, name=FIXTURE_NAME)
    unedited = tmp_path / "unedited"
    shutil.copytree(p.out, unedited)
    edit_fixture(p)
    code, env, err = p.build("--confirm")
    assert code == 0 and not issues(env, "sync.conflict"), err
    merged = tmp_path / "merged"
    shutil.copytree(p.out, merged)
    code, _, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    code, _, err = p.build("--confirm")
    assert code == 0, err
    for folder in (merged, p.out):
        drc, unconnected = _drc(folder)
        before, before_unconnected = _drc(unedited)
        assert not drc - before and unconnected <= before_unconnected, (folder.name, drc - before)
        assert not _erc(folder) - _erc(unedited), folder.name
