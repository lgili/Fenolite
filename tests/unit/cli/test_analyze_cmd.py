# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze`` (capability board-analyses, "Analyze command"; change c0047). Hermetic: the command
runs no tool and writes no file."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _analysis import creep_bench
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli.cmd_analyze import COMMAND, KINDS

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
HEAD = 'schema = "fenolite.requirements.v0"\n'


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", *args)
    return code, env, err


def bench(tmp_path: Path, name: str = "slot") -> Path:
    path = tmp_path / f"{name}.kicad_pcb"
    path.write_text(write_board(creep_bench(name).design, target=10).text, encoding="utf-8")
    return path


def requirements(tmp_path: Path, **values: int) -> Path:
    body = "".join(f"{key} = {value}\n" for key, value in values.items())
    path = tmp_path / "requirements.toml"
    path.write_text(HEAD + '[[distance]]\na = { net = "A" }\nb = { net = "B" }\n' + body, encoding="utf-8")
    return path


def test_command_metadata() -> None:
    assert (COMMAND.name, COMMAND.mutates, COMMAND.schema) == ("analyze", False, "fenolite.analyze.v0")
    assert KINDS == ("current", "clearance", "creepage")


def test_example_capacity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(FIXTURE), "--kinds", "current", "--temp-rise", "10",
        "--copper-thickness", "35um",
    )  # fmt: skip
    assert code == 0 and env["schema"] == "fenolite.analyze.v0"
    rows = env["result"]["current"]
    assert sorted(row["kind"] for row in rows) == ["arc", "track", "track", "track"]
    assert all(type(row["capacity_ma"]) is int and row["capacity_ma"] > 0 for row in rows)
    assert "distances" not in env["result"]
    assert env["evidence"]["level"] in ("INFERRED", "UNVERIFIED")
    assert env["result"]["inputs"]["temp_rise_mk"] == 10_000
    assert env["result"]["inputs"]["copper_thickness"] == {"*": 35_000}
    assert env["result"]["summary"]["current"]["fit"] == "S-0269"


def test_example_with_vias_and_layer_thickness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(FIXTURE), "--kinds", "current", "--temp-rise", "12.5",
        "--copper-thickness", "35um", "--copper-thickness", "B.Cu=70um", "--via-plating", "25um",
    )  # fmt: skip
    assert code == 0 and env["issues"] == []
    rows = env["result"]["current"]
    assert {row["thickness"] for row in rows if row["layer"] == "B.Cu"} == {70_000}
    assert [row["kind"] for row in rows].count("via") == 1
    assert env["result"]["inputs"]["temp_rise_mk"] == 12_500 and env["evidence"]["level"] == "INFERRED"


def test_requirement_not_met_exits_5(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "creepage",
        "--requirements", str(requirements(tmp_path, creepage_nm=12_000_000)),
    )  # fmt: skip
    assert code == 5
    (found,) = [issue for issue in env["issues"] if issue["severity"] == "error"]
    assert found["code"] == "analysis.creepage-below" and "11 mm" in found["message"]
    (row,) = env["result"]["distances"]
    assert set(row) == {"net_a", "net_b", "creepage"} and row["creepage"]["low"] == 11_000_000
    assert env["result"]["inputs"]["boundary"] == {"source": "edge", "band": 0, "cutouts": 1}


def test_requirement_met_and_kinds_filter_the_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    file = str(requirements(tmp_path, creepage_nm=12_000_000, clearance_nm=1_000_000))
    code, env, _ = analyze(monkeypatch, tmp_path, str(board), "--kinds", "clearance", "--requirements", file)
    assert code == 0 and [i for i in env["issues"] if i["severity"] == "error"] == []
    (row,) = env["result"]["distances"]
    assert set(row) == {"net_a", "net_b", "gaps", "clearance"} and row["clearance"]["low"] == 9_000_000


def test_pair_and_board_thickness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path, "edge")
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "clearance,creepage", "--pair", "A", "B",
        "--board-thickness", "1.6mm",
    )  # fmt: skip
    assert code == 0
    (row,) = env["result"]["distances"]
    assert row["creepage"]["low"] == 5_100_000 and row["creepage"]["layer"] == "F.Cu/B.Cu"
    assert row["clearance"]["high"] == 5_100_002
    assert row["creepage"]["points"][1] == {"x": 25_000_000, "y": 20_000_000}
    without, env2, _ = analyze(monkeypatch, tmp_path, str(board), "--kinds", "creepage", "--pair", "A", "B")
    assert without == 0 and env2["result"]["distances"][0]["creepage"] is None
    assert [i["where"] for i in env2["issues"]] == ["board thickness"]
    assert env2["evidence"]["level"] == "UNVERIFIED"


def test_within_on_the_example(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(monkeypatch, tmp_path, str(FIXTURE), "--kinds", "clearance", "--within", "1mm")
    assert code == 0 and len(env["result"]["distances"]) >= 1
    assert env["result"]["summary"]["distances"]["unsupported"] == {}


def test_readonly_and_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = bench(tmp_path)
    file = requirements(tmp_path, creepage_nm=1_000_000)
    before = tree_snapshot(tmp_path)
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--requirements", str(file), "--temp-rise", "10",
        "--copper-thickness", "35um",
    )  # fmt: skip
    assert code == 0 and env["receipt"] is None
    assert tree_snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "thermal"),
        ("--kinds", ""),
        ("--temp-rise", "warm"),
        ("--temp-rise", "10.0001"),
        ("--temp-rise", "0"),
        ("--copper-thickness", "35"),
        ("--copper-thickness", "F.Cu=thin"),
        ("--via-plating", "0mm"),
        ("--within", "1"),
        ("--pair", "A"),
        ("--pair", "A", "A"),
        ("--pair", "A", "B", "C"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err = analyze(monkeypatch, tmp_path, str(FIXTURE), *args)
    assert code == 2 and err["code"] == "FEN-2001"


def test_unreadable_requirements(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = analyze(monkeypatch, tmp_path, str(FIXTURE), "--requirements", str(tmp_path / "none.toml"))
    assert code == 3 and err["code"] == "FEN-3004" and str(tmp_path) not in err["message"]
    bad = tmp_path / "bad.toml"
    bad.write_text(HEAD + '[[current]]\nselect = { net = "A" }\nmilliamps = 2.5\ntemp_rise_mk = 1\n')
    code, _, err = analyze(monkeypatch, tmp_path, str(FIXTURE), "--requirements", str(bad))
    assert code == 3 and err["code"] == "FEN-3004" and "current[0].milliamps" in err["message"]


def test_missing_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = analyze(monkeypatch, tmp_path, str(tmp_path / "none.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
