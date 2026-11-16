# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check --compare-native`` (change c0498, task 4.2; capability altium-verification, "Comparison
with Altium's DRC"). The PCB documents are the committed ``blink`` sample with authored violation storages
(``tests/_violations.py``); no tool runs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _violations import storage, violation, with_storages

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink"


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("check ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def project(tmp_path: Path, *violations: dict[str, str]) -> Path:
    folder = tmp_path / "blink"
    shutil.copytree(BLINK, folder)
    if violations:
        target = folder / "blink.PcbDoc"
        with_storages(target, storage("TClearanceViolation", list(violations)), source=BLINK / "blink.PcbDoc")
    return folder


def stage_names(envelope: dict[str, Any]) -> list[str]:
    return [stage["name"] for stage in envelope["result"]["stages"]]


def test_native_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A fault Fenolite misses": a stored Clearance violation between two pads the copper check
    passes."""
    folder = project(tmp_path, violation(1, ("Pad", 0), ("Pad", 2), "1000mil", "2000mil", "Clearance"))
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(folder / "blink.PcbDoc"), "--compare-native")
    assert code == 0, err
    native = env["result"]["native"]
    assert native["source"] == "stored" and native["file"] == "blink.PcbDoc"
    assert len(native["native_only"]) == 1 and native["by_kind"]["Clearance"]["native_only"] == 1
    assert native["matched"] == 0 and native["fenolite_only"] == []
    assert [i["code"] for i in env["issues"]].count("check.native-only") == 1
    assert {"silk.clearance", "altium.native-drc"} <= set(stage_names(env))
    assert stage_names(env)[-1] == "altium.native-drc"


def test_without_a_stored_drc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Without a stored DRC"."""
    folder = project(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(folder / "blink.PcbDoc"), "--compare-native")
    assert code == 0, err
    assert [i["code"] for i in env["issues"]].count("check.native-missing") == 1
    assert "native" not in env["result"]


def test_a_text_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = project(tmp_path)
    report = folder / "Design Rule Check - blink.drc"
    report.write_text(
        "Processing Rule : Clearance Constraint (Gap=10mil) (All),(All)\n"
        "   Violation between Clearance Constraint: Track (0mil,0mil)(10mil,0mil) on Top Layer\n",
        encoding="utf-8",
    )
    code, env, err, _ = run(monkeypatch, folder, "check", "blink.PcbDoc", "--compare-native", report.name)
    assert code == 0, err
    native = env["result"]["native"]
    assert native["source"] == "report" and native["file"] == report.name and len(native["native_only"]) == 1
    code, _, err, _ = run(monkeypatch, folder, "check", "blink.PcbDoc", "--compare-native", "report.html")
    assert code == 2 and err["code"] == "FEN-2001"


def test_on_a_kicad_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "On a KiCad board"."""
    board = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--compare-native")
    assert code == 2 and err["code"] == "FEN-2001"


def test_without_the_option_nothing_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = project(tmp_path, violation(1, ("Pad", 0), ("Pad", 2), "0mil", "0mil"))
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(folder / "blink.PcbDoc"))
    assert code == 0 and "native" not in env["result"]
    assert not {"silk.clearance", "altium.native-drc"} & set(stage_names(env))
