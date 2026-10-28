# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze`` with the practice kinds of change c0204 (capability board-analyses, "Practice kinds
in the analyze command"), on the benches of ``tests/_practicebench.py`` written as KiCad boards. Hermetic."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _practicebench import LOOP, bodies, coupling, cutout, dead, decoupling, relief
from _projects import tree_snapshot

from fenolite.analysis.requirements import SCHEMA
from fenolite.backends.kicad.pcb import write_board
from fenolite.model.design import Design

MM = 1_000_000
HEAD = f'schema = "{SCHEMA}"\n'
POWER_IN = '(net "+3V3")\n\t\t\t(uuid'
"""Where the board text of ``decoupling()`` names the net of ``U1-4``: the pin type goes after it, as KiCad
writes it (the board writer writes no pin type)."""


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def analyze(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bench: Callable[[], Design],
    *args: str,
    requirements: str | None = None,
    edit: Callable[[str], str] = lambda text: text,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    board = tmp_path / "practice.kicad_pcb"
    board.write_text(edit(write_board(bench(), target=10).text), encoding="utf-8", newline="\n")
    if requirements is not None:
        (tmp_path / "req.toml").write_text(HEAD + requirements, encoding="utf-8")
        args = (*args, "--requirements", "req.toml")
    before = tree_snapshot(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", str(board), *args)
    assert tree_snapshot(tmp_path) == before
    return code, env, err


def test_connectivity_of_a_stale_pour(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A pin left open by a cut-out", through the command: a warning, so exit 0."""
    code, env, err = analyze(
        monkeypatch, tmp_path, cutout, "--kinds", "connectivity", "--pour-grid", "0.25mm"
    )
    assert code == 0, err
    (row,) = env["result"]["connectivity"]
    assert row["net"] == "BUS" and row["copper"] == ["simulated"] and row["groups"] == [["D1-2"], ["J1-1"]]
    (zone,) = env["result"]["pours"]
    assert zone["state"] == "simulated" and zone["reason"].startswith("stale: fill inside the keep-out")
    assert [i["code"] for i in env["issues"]] == ["analysis.net-split"]
    assert env["result"]["inputs"]["pour_grid"] == MM // 4


def test_decoupling_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def power_in(text: str) -> str:
        assert text.count(POWER_IN) == 3  # U1-4, C1-1 and C2-1 in placement order
        return text.replace(POWER_IN, '(net "+3V3")\n\t\t\t(pintype "power_in")\n\t\t\t(uuid', 1)

    code, env, err = analyze(monkeypatch, tmp_path, decoupling, "--kinds", "decoupling", edit=power_in)
    assert code == 0 and env["issues"] == [], err
    (row,) = env["result"]["decoupling"]
    assert (row["pin"], row["capacitor"], row["distance"], row["loop_area_nm2"]) == (
        "U1-4",
        "C1-1",
        1_500_000,
        LOOP,
    )
    far = '[[decoupling]]\nparts = "U*"\nmax_distance_nm = 1000000\n'
    code, env, _ = analyze(
        monkeypatch, tmp_path, decoupling, "--kinds", "decoupling", requirements=far, edit=power_in
    )
    assert code == 5 and [i["code"] for i in env["issues"]] == ["analysis.decoupling-far"]


def test_bodies_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A KiCad board holds no body outline: the courtyard is the plan view. The board file holds no net
    class either (they live in the project file), so every net reads as ``Default``; the part's own pads do
    not count."""
    row = '[[body_copper]]\nnetclass = "Default"\nparts = "C*"\nlayers = ["F.Cu"]\n'
    code, env, _ = analyze(monkeypatch, tmp_path, bodies, "--kinds", "bodies", requirements=row)
    assert code == 5 and [i["code"] for i in env["issues"]] == ["analysis.body-copper"]
    (found,) = env["result"]["bodies"]
    assert (found["part"], found["plan"], found["layer"], found["nets"]) == (
        "C1",
        "courtyard",
        "F.Cu",
        ["HV"],
    )


def test_relief_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    row = '[[current]]\nselect = { net = "GND" }\nmilliamps = 5000\ntemp_rise_mk = 10000\n'
    code, env, _ = analyze(
        monkeypatch, tmp_path, relief, "--kinds", "relief", "--copper-thickness", "35um", requirements=row
    )
    assert code == 5 and [i["code"] for i in env["issues"]] == ["analysis.relief-exceeded"]
    (found,) = env["result"]["relief"]
    assert (found["spokes"], found["width"], found["copper"]) == (4, 2 * MM, "saved_fill")


def test_dead_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(monkeypatch, tmp_path, dead, "--kinds", "dead", "--dead-distance", "5mm")
    assert code == 0
    assert sorted(i["code"] for i in env["issues"]) == [
        "analysis.copper-dead",
        "analysis.copper-far",
        "analysis.copper-far",
    ]
    assert env["result"]["summary"]["dead"] == {"islands": 1, "far": 2, "dropped": 0}
    assert env["result"]["inputs"]["dead_distance"] == 5 * MM


def test_coupling_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A sense net beside a phase track", through the command."""
    code, env, err = analyze(
        monkeypatch,
        tmp_path,
        coupling,
        "--kinds",
        "coupling",
        "--aggressor",
        "PHASE_*",
        "--aggressor",
        "LED",
        "--victim",
        "ISENSE",
        "--board-thickness",
        "1.6mm",
    )
    assert code == 0, err
    first = env["result"]["coupling"][0]
    assert (first["aggressor"], first["victim"], first["parallel"]) == ("PHASE_U", "ISENSE", 10 * MM)
    assert "ranks pairs" in env["result"]["summary"]["coupling"]["note"]
    assert env["result"]["coupling_victims"][0]["net"] == "ISENSE"
    assert env["result"]["inputs"]["aggressors"] == ["PHASE_*", "LED"]


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "coupling", "--aggressor", "PHASE_*"),
        ("--kinds", "current", "--victim", "ISENSE"),
        ("--kinds", "current", "--aggressor", "LED"),
        ("--kinds", "current", "--dead-distance", "1mm"),
        ("--kinds", "current,decoupling", "--pour-grid", "0.1mm"),
        ("--kinds", "dead", "--pour-grid", "0mm"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err = analyze(monkeypatch, tmp_path, cutout, *args)
    assert code == 2 and err["code"] == "FEN-2001"
