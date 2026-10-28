# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze`` with the pour-shape kinds and ``--split`` of change c0213 (capability board-analyses,
"Pour shape kinds in the analyze command"), on the benches of ``tests/_shapebench.py`` written as KiCad
boards and on ``tests/data/analysis/strip_10.kicad_pcb``. Hermetic."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _projects import tree_snapshot
from _shapebench import balance, loop, neck

from fenolite.analysis.requirements import SCHEMA
from fenolite.backends.kicad.pcb import write_board
from fenolite.model.design import Design

MM = 1_000_000
HEAD = f'schema = "{SCHEMA}"\n'
STRIP = Path(__file__).resolve().parents[2] / "data" / "analysis" / "strip_10.kicad_pcb"
LOOPS = "".join(
    f'[[loop]]\nname = "{name}"\npads = ["U1-4", "{name}-1", "{name}-2", "U1-2"]\n'
    f"max_area_nm2 = {10 * MM * MM}\n"
    for name in ("C1", "C2")
)


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def write(tmp_path: Path, name: str, bench: Callable[[], Design]) -> Path:
    board = tmp_path / name
    board.write_text(write_board(bench(), target=10).text, encoding="utf-8", newline="\n")
    return board


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path, *args: str, requirements: str | None = None
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    if requirements is not None:
        (tmp_path / "req.toml").write_text(HEAD + requirements, encoding="utf-8")
        args = (*args, "--requirements", "req.toml")
    before = tree_snapshot(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", board.name, *args)
    assert tree_snapshot(tmp_path) == before
    return code, env, err


def test_necks_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = write(tmp_path, "neck.kicad_pcb", neck)
    rule = '[[neck]]\nselect = { net = "GND" }\nmin_width_nm = 500000\n'
    code, env, err = analyze(
        monkeypatch, tmp_path, board, "--kinds", "necks", "--pour-grid", "0.05mm", requirements=rule
    )
    assert code == 5, err
    (row,) = env["result"]["necks"]
    assert (row["shape"], row["width"], row["copper"]) == ("neck", 300_000, ["saved_fill"])
    assert [i["code"] for i in env["issues"]] == ["analysis.neck-narrow"]
    assert (
        env["result"]["summary"]["necks"]["necks"] == 1 and env["result"]["inputs"]["pour_grid"] == MM // 20
    )


def test_loops_with_a_baseline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = write(tmp_path, "loop.kicad_pcb", loop)
    write(tmp_path, "base.kicad_pcb", lambda: loop(far=25))
    code, env, err = analyze(
        monkeypatch,
        tmp_path,
        board,
        "--kinds",
        "loops",
        "--loop-baseline",
        "base.kicad_pcb",
        requirements=LOOPS,
    )
    assert code == 5, err
    rows = [(r["name"], r["area_nm2"], r["baseline_nm2"], r["change_nm2"]) for r in env["result"]["loops"]]
    assert rows == [("C1", 3 * MM * MM, 3 * MM * MM, 0), ("C2", 20 * MM * MM, 10 * MM * MM, 10 * MM * MM)]
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("analysis.loop-area", "C2")]
    assert env["result"]["inputs"]["loop_baseline"] == "base.kicad_pcb"


def test_balance_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = write(tmp_path, "balance.kicad_pcb", balance)
    code, env, err = analyze(monkeypatch, tmp_path, board, "--kinds", "balance", "--pour-grid", "0.25mm")
    assert code == 0 and env["issues"] == [], err
    (row,) = env["result"]["balance"]
    assert (row["part"], row["copper_nm2"], row["ratio_permille"]) == (
        "R1",
        [8 * MM * MM, MM * MM // 2],
        16_000,
    )


def test_power_split_of_the_strip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / STRIP.name
    shutil.copyfile(STRIP, board)
    code, env, err = analyze(
        monkeypatch,
        tmp_path,
        board,
        "--kinds", "power", "--split", "--path", "J1-1", "U1-1",
        "--copper-thickness", "50um", "--resistivity", "20", "--pour-grid", "0.5mm",
    )  # fmt: skip
    assert code == 0, err
    (row,) = env["result"]["split"]
    assert [(e["kind"], e["share_permille"]) for e in row["elements"]] == [("fill", 1000)]
    assert row["resistance_uohm"] == 1440 and row["bounds"] == {"low": 1440, "high": 1440} and row["within"]
    assert env["result"]["inputs"]["split"] is True and env["result"]["summary"]["split"]["paths"] == 1


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "current", "--split"),
        ("--kinds", "necks", "--loop-baseline", "base.kicad_pcb"),
        ("--kinds", "power", "--pour-grid", "0.1mm"),
        ("--kinds", "necks,thermal"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    board = write(tmp_path, "neck.kicad_pcb", neck)
    code, _, err = analyze(monkeypatch, tmp_path, board, *args)
    assert code == 2 and err["code"] == "FEN-2001"
