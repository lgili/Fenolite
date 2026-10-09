# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite ready`` (capability cli-contract, "Ready command" to "Ready example and documentation";
change c0098). Every test hides the machine's ``kicad-cli``; ERC and DRC run against the fake of
``tests/_fakecli.py``."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli, report_with
from _projects import tree_snapshot

from fenolite.agent import guide
from fenolite.checks.readiness import READY_CHECKS
from fenolite.cli._examples import EXAMPLE_BOARD, EXAMPLE_READY

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(EXAMPLE_READY).parent
CLEARANCE = {
    "type": "clearance",
    "description": "Clearance violation",
    "severity": "error",
    "items": [
        {"uuid": "00000000-0000-0000-0000-000000000001", "description": "Track", "pos": {"x": 1, "y": 0}}
    ],
}


@pytest.fixture(autouse=True)
def hidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def _refuse(*args: object, **kwargs: object) -> None:
    raise AssertionError("ready started a subprocess")


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "ready"
    shutil.copytree(FIXTURE, root)
    return root


def _check(env: dict[str, Any], name: str) -> dict[str, Any]:
    return next(check for check in env["result"]["checks"] if check["name"] == name)


def _codes(env: dict[str, Any]) -> list[str]:
    return sorted(issue["code"] for issue in env["issues"])


def test_ready_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A ready project"."""
    root = _copy(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin")
    before = tree_snapshot(root)
    code, env, err, _ = run(monkeypatch, tmp_path, "ready", str(root), "--kicad-cli", str(fake))
    assert code == 0, (err, env["issues"])
    result = env["result"]
    assert result["ready"] is True and result["complete"] is True
    assert [check["name"] for check in result["checks"]] == list(READY_CHECKS)
    assert {check["status"] for check in result["checks"]} == {"ok"}
    assert result["project"] == {"board": "blink.kicad_pcb", "built": False}
    assert result["counts"] == {"error": 0, "warning": 0, "info": 0}
    assert env["evidence"]["level"] == "INFERRED"
    ran = [c["args"][:2] for c in calls(fake)]
    assert ["sch", "erc"] in ran and ["pcb", "drc"] in ran
    assert tree_snapshot(root) == before


def test_open_nets_make_a_project_not_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Open nets make a project not ready"."""
    code, env, err, _ = run(monkeypatch, tmp_path, "ready", EXAMPLE_BOARD, "--no-kicad")
    assert code == 5 and err["code"] == "FEN-5001"
    assert env["result"]["ready"] is False
    assert [check["name"] for check in env["result"]["checks"]] == list(READY_CHECKS)
    opened = [issue for issue in env["issues"] if issue["code"] == "ready.net-open"]
    assert [issue["where"] for issue in opened] == ["LED_A"]
    assert _check(env, "nets.open")["summary"] == {"nets": 1, "connections": 1}


def test_no_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "No kicad-cli"."""
    code, _, err, out = run(monkeypatch, tmp_path, "ready", str(_copy(tmp_path)))
    assert code == 6 and err["code"] == "FEN-6001" and "--no-kicad" in err["hint"]
    assert out == "" or '"ok": false' in out


def test_skipped_by_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Skipped by option"."""
    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)
    code, env, err, _ = run(monkeypatch, tmp_path, "ready", str(_copy(tmp_path)), "--no-kicad")
    assert code == 0, err
    assert env["result"]["ready"] is True and env["result"]["complete"] is False
    for name in ("erc.kicad", "drc.kicad"):
        assert (_check(env, name)["status"], _check(env, name)["reason"]) == ("skipped", "no-kicad")
    skips = [issue for issue in env["issues"] if issue["code"] == "ready.check-skipped"]
    assert [(i["severity"], i["where"]) for i in skips] == [
        ("warning", "erc.kicad"),
        ("warning", "drc.kicad"),
    ]


def test_drc_findings_are_passed_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "DRC findings are passed on"."""
    fake = fake_kicad_cli(tmp_path / "bin", drc_report=report_with(CLEARANCE))
    code, env, _, _ = run(monkeypatch, tmp_path, "ready", str(_copy(tmp_path)), "--kicad-cli", str(fake))
    assert code == 5
    assert _check(env, "drc.kicad")["status"] == "errors"
    assert env["result"]["counts"]["error"] == 1
    assert _codes(env) == ["kicad.drc.clearance"]


def test_stage_skip_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A project without its schematic: ``erc.kicad`` skips itself, and ``ready`` says so."""
    root = _copy(tmp_path)
    (root / "blink.kicad_sch").unlink()
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, err, _ = run(monkeypatch, tmp_path, "ready", str(root), "--kicad-cli", str(fake))
    assert code == 0, err
    assert (_check(env, "erc.kicad")["status"], _check(env, "erc.kicad")["reason"]) == (
        "skipped",
        "no-schematic",
    )
    assert _check(env, "drc.kicad")["status"] == "ok"
    assert env["result"]["complete"] is False and _codes(env) == ["ready.check-skipped"]


def _starter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    work = tmp_path / "work"
    (work / "blink").mkdir(parents=True)
    for file, data in guide.render_starter("blink", "blink").items():
        (work / "blink" / file).write_bytes(data)
    code, _, err, _ = run(monkeypatch, work, "build", "blink/design.py", "--out", "blink/build", "--confirm")
    assert code == 0, err
    return work / "blink" / "build"


def test_built_project_is_judged_on_its_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A built project is judged on its model"."""
    build = _starter(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "ready", str(build), "--no-kicad")
    assert code == 5
    assert env["result"]["project"]["built"] is True
    opened = sorted(i["where"] for i in env["issues"] if i["code"] == "ready.net-open")
    assert opened == ["GND", "LED_A", "VIN"]
    assert "ready.pin-unconnected" not in _codes(env)


def test_unreadable_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "An unreadable model"."""
    build = _starter(monkeypatch, tmp_path)
    (build / ".fenolite" / "board.json").write_text("{", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "ready", str(build), "--no-kicad")
    assert code == 5
    assert _codes(env).count("check.cache-unreadable") == 1
    assert [check["name"] for check in env["result"]["checks"]] == list(READY_CHECKS)
    assert env["result"]["project"]["built"] is True


def test_altium_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Altium input"."""
    document = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
    code, _, err, _ = run(monkeypatch, tmp_path, "ready", str(document))
    assert code == 2 and err["code"] == "FEN-2001" and "fenolite check" in err["hint"]
