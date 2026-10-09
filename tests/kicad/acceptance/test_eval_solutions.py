# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every reference solution of the agent evaluation is replayed and judged on ``kicad-cli`` (capability
agent-eval, scenarios "Replay of a solution on KiCad" and "A correct project passes"; change c0081).

The runner ``replay`` plays the lines of a solution through the call log, with no agent, and the judge
decides with ``fenolite check``. So a change that breaks what a task needs fails here, and the five
tasks double as acceptance tests of an outsider's path. The solutions build KiCad 10 projects, so the
tests are skipped on ``kicad-cli`` 9.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _agenteval import ROOT, real_fenolite, run, tasks

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]

NAMES = tasks.names()
LEVELS = ("KICAD-VERIFIED", "ORACLE-VERIFIED", "CORPUS-VERIFIED", "INFERRED")


@pytest.mark.parametrize("name", NAMES, ids=[name.replace("-", "_") for name in NAMES])
def test_replay(tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str) -> None:
    """Scenario "Replay of a solution on KiCad": every line exits 0 and the verdict is ``passed``."""
    task = tasks.load(name)
    place = run.Place(tmp_path / "place", real_fenolite(tmp_path / "real"), Path(sys.executable))
    place.workdir.mkdir(parents=True)
    result = run.execute(task, run.load_runners()["replay"], place, checkout=ROOT)
    assert result is not None
    said = capsys.readouterr().out
    assert result["verdict"]["status"] == "passed", (said, result["verdict"])
    assert [check["name"] for check in result["verdict"]["checks"]] == [
        "project",
        "check",
        "nets",
        "board",
        "outputs",
    ]
    assert all(check["passed"] for check in result["verdict"]["checks"])
    lines = task.commands()
    assert result["calls"] == len(lines)
    assert result["calls_by_exit"] == {"0": len(lines)}
    assert result["first_failure"] is None and result["timed_out"] is False
    assert (result["runner"], result["runner_version"], result["isolated"]) == ("replay", "builtin", True)
    calls = run.read_log(place.log)
    assert [call["argv"] for call in calls] == [line.split()[1:] for line in lines]
    assert [call["exit"] for call in calls] == [0] * len(lines)
    assert f"verdict: passed  task={name} runner=replay calls={len(lines)} failed=0" in said
    assert json.loads(place.result.read_text(encoding="utf-8")) == result
    assert not (place.workdir / "solution").exists() and not (place.workdir / "task.toml").exists()


def test_a_correct_project_passes(tmp_path: Path) -> None:
    """Scenario "A correct project passes": ``evidence_level`` is the level of ``fenolite check``."""
    task = tasks.load("led-indicator")
    real = real_fenolite(tmp_path / "real")
    place = run.Place(tmp_path / "place", real, Path(sys.executable))
    place.workdir.mkdir(parents=True)
    result = run.execute(task, run.load_runners()["replay"], place, checkout=ROOT)
    assert result is not None and result["verdict"]["status"] == "passed"
    check = subprocess.run(
        [str(real), "check", task.expect.project, "--json"],
        cwd=place.workdir, capture_output=True, text=True, encoding="utf-8", timeout=900, check=False,
    )  # fmt: skip
    assert check.returncode == 0, check.stderr
    envelope = json.loads(check.stdout)
    assert result["verdict"]["evidence_level"] == envelope["evidence"]["level"]
    assert envelope["evidence"]["level"] in LEVELS
    stages = {stage["name"]: stage for stage in envelope["result"]["stages"]}
    assert stages["drc.kicad"]["status"] == "ok"
    assert stages["drc.kicad"]["evidence"]["level"] == "KICAD-VERIFIED"


def test_the_starting_project_of_fix_short_fails_the_judge(tmp_path: Path) -> None:
    """Before the repair, the judge's ``check`` does not pass on KiCad either: the task is not solved
    by doing nothing."""
    task = tasks.load("fix-short")
    real = real_fenolite(tmp_path / "real")
    work = tmp_path / "work"
    assert run.prepare(task, work, real) is None
    verdict = run.judging.judge(work, task, real)
    assert verdict.status == "failed"
    checks = {check.name: check for check in verdict.checks}
    assert not checks["check"].passed and "copper.short" in checks["check"].detail
    assert checks["nets"].passed and checks["board"].passed and not checks["outputs"].passed


@pytest.mark.slow
def test_replay_in_a_fresh_environment(capsys: pytest.CaptureFixture[str]) -> None:
    """The whole runner once: the wheel of the checkout is built and installed with no index in a new
    environment under a temporary folder, and ``led-indicator`` is replayed with the installed command."""
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH: it builds the wheel and the environment of a run")
    code = run.main(["--task", "led-indicator", "--runner", "replay"])
    said = capsys.readouterr()
    assert code == 0, said
    assert "time budget: 20 minutes" in said.out
    assert "verdict: passed  task=led-indicator runner=replay calls=4 failed=0" in said.out
    assert "kept:" not in said.out
