# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze --kinds length`` (capability board-analyses, "Length kind in the analyze command";
change c0106). Hermetic: the command runs no tool and writes no file."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import _lengthbench as lb
import pytest
from _checkcli import run
from _projects import tree_snapshot

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    return code, env, err


def bench(tmp_path: Path, case: str = "two", target: int = 10) -> Path:
    folder = tmp_path / case
    folder.mkdir()
    return lb.write_case(case, target, folder).files[f"{lb.STEM}.kicad_pcb"]


def test_bench_length_of_a_net(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    before = tree_snapshot(tmp_path)
    code, env, err = analyze(
        monkeypatch, tmp_path, "analyze", str(board), "--kinds", "length", "--net", "L_VIA2"
    )
    assert code == 0, err
    (row,) = env["result"]["lengths"]
    assert row == {
        "net": "L_VIA2", "routed": 20_000_000, "vias": 1_580_000, "die": 0, "total": 21_580_000,
        "via_count": 1, "start": None, "paths": [], "off_path": 0,
    }  # fmt: skip
    assert env["result"]["pairs"] == []
    assert env["result"]["summary"]["length"] == {
        "nets": 1, "major": 10, "stackup": "default", "count_vias": True,
    }  # fmt: skip
    inputs = env["result"]["inputs"]
    assert (inputs["kinds"], inputs["nets"], inputs["from"], inputs["kicad_version"]) == (
        ["length"], ["L_VIA2"], [], 10,
    )  # fmt: skip
    assert [i["code"] for i in env["issues"]] == ["kicad.length.default-stackup"]
    assert env["evidence"]["level"] == "INFERRED"
    assert {"H-G-NETLEN-PATH", "H-K-NETLEN-VIA10"} <= set(env["evidence"]["hypotheses"])
    assert "current" not in env["result"] and "distances" not in env["result"]
    assert tree_snapshot(tmp_path) == before
    code, nine, _ = analyze(
        monkeypatch,
        tmp_path,
        "--kicad-version",
        "9",
        "analyze",
        str(board),
        "--kinds",
        "length",
        "--net",
        "L_VIA2",
    )
    assert code == 0 and nine["result"]["lengths"][0]["total"] == 21_545_000
    assert (
        nine["result"]["inputs"]["kicad_version"] == 9 and nine["result"]["summary"]["length"]["major"] == 9
    )


def test_bench_paths_and_from(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    code, env, _ = analyze(
        monkeypatch, tmp_path, "analyze", str(board), "--kinds", "length",
        "--net", "L_BRANCH", "--net", "L_PASS",
        "--from", "R9", "--from", "R17-1",
    )  # fmt: skip
    assert code == 0
    branch, passing = env["result"]["lengths"]
    assert branch["start"] == "R9-2" and passing["start"] == "R17-1"
    assert [(p["end"], p["length"]) for p in branch["paths"]] == [
        ("R10-1", 18_400_000),
        ("R11-1", 14_200_000),
    ]
    assert passing["off_path"] == 800_000
    assert env["result"]["inputs"]["from"] == ["R9", "R17-1"]
    codes = [i["code"] for i in env["issues"]]
    assert codes == ["analysis.length-stub", "kicad.length.default-stackup"]


def test_bench_project_switch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The project file next to the board turns the via heights off."""
    board = bench(tmp_path, "two-noheight")
    code, env, _ = analyze(
        monkeypatch, tmp_path, "analyze", str(board), "--kinds", "length", "--net", "L_VIA2"
    )
    assert code == 0 and env["result"]["lengths"][0]["total"] == 20_000_000
    assert env["result"]["summary"]["length"]["count_vias"] is False


def test_default_kinds_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(
        monkeypatch, tmp_path, "analyze", str(FIXTURE), "--temp-rise", "10", "--copper-thickness", "35um"
    )
    assert code == 0
    assert "current" in env["result"] and "distances" in env["result"]
    assert "lengths" not in env["result"] and "pairs" not in env["result"]
    assert "length" not in env["result"]["summary"]
    assert not {"nets", "from", "kicad_version"} & set(env["result"]["inputs"])


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    for args in (
        ("--net", "X"),
        ("--kinds", "current", "--from", "R1", "--temp-rise", "10"),
    ):
        code, _, err = analyze(monkeypatch, tmp_path, "analyze", str(board), *args)
        assert code == 2 and err["code"] == "FEN-2001", args


def test_no_selection_exits_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    code, env, _ = analyze(monkeypatch, tmp_path, "analyze", str(board), "--kinds", "length")
    assert code == 0 and env["result"]["lengths"] == []
    missing = [i for i in env["issues"] if i["code"] == "analysis.input-missing"]
    assert len(missing) == 1 and "net selection" in missing[0]["message"]
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_altium_document_has_no_facts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An Altium PCB document: routed lengths and paths without facts, whatever ``--kicad-version``."""
    document = tmp_path / ALTIUM.name
    shutil.copyfile(ALTIUM, document)
    replies = []
    for version in ("10", "9"):
        code, env, err = analyze(
            monkeypatch, tmp_path, "--kicad-version", version, "analyze", str(document), "--kinds", "length",
            "--net", "*",
        )  # fmt: skip
        assert code == 0, err
        replies.append(env["result"]["lengths"])
        assert env["result"]["lengths"], "the sample holds nets with copper or pads"
        for row in env["result"]["lengths"]:
            assert row["vias"] == 0 and row["die"] == 0 and row["total"] == row["routed"]
        assert env["result"]["summary"]["length"]["major"] is None
        assert env["result"]["summary"]["length"]["stackup"] is None
        missing = [i for i in env["issues"] if i["code"] == "analysis.input-missing"]
        assert len(missing) == 1 and "length facts" in missing[0]["message"]
        assert env["evidence"]["level"] == "UNVERIFIED"
    assert replies[0] == replies[1]
