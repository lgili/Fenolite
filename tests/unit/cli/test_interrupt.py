# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A command stopped by a signal stops its tools, writes nothing and ends in ``FEN-1003`` (capability
cli-contract, "Interrupted commands write nothing and stop their tools"; change c0120). Hermetic."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot
from _fakerouter import create_fake_router

import fenolite.cli.main as cli_main
from fenolite.cli import cmd__echo
from fenolite.cli.api import Context, Result

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "routing" / "two_pads.kicad_pcb"
MonkeyPatch = pytest.MonkeyPatch
posix = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows cannot deliver SIGTERM to a handler: a forced stop is not handled",
)


def test_interrupt_inside_a_command(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    def stopped(_args: object, _ctx: Context) -> Result:
        raise cli_main.Interrupted(signal.SIGTERM)

    monkeypatch.setattr(cmd__echo, "COMMAND", dataclasses.replace(cmd__echo.COMMAND, run=stopped))
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "a.txt", "--confirm")
    assert code == 1 and err["code"] == "FEN-1003" and err["retryable"] is True
    assert err["message"] == "stopped by a signal; nothing was written"
    assert env["ok"] is False and env["receipt"] is None and list(tmp_path.iterdir()) == []


def test_keyboard_interrupt_is_handled_the_same_way(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    def stopped(_args: object, _ctx: Context) -> Result:
        raise KeyboardInterrupt

    monkeypatch.setattr(cmd__echo, "COMMAND", dataclasses.replace(cmd__echo.COMMAND, run=stopped))
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo")
    assert code == 1 and err["code"] == "FEN-1003" and env["ok"] is False


def test_signal_during_the_write(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A signal during the write": the first replacement is taken back."""
    (tmp_path / "a.txt").write_bytes(b"a-old")
    (tmp_path / "b.txt").write_bytes(b"b-old")
    before = folder_snapshot(tmp_path)
    real = os.replace
    replaced: list[str] = []

    def replace(src: Any, dst: Any, **kwargs: Any) -> None:
        if Path(src).suffix == ".tmp":
            if replaced:
                raise cli_main.Interrupted(signal.SIGINT)
            replaced.append(Path(dst).name)
        real(src, dst, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    args = ("_echo", "--write", "a.txt", "--write", "b.txt", "--confirm")
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert replaced == ["a.txt"]
    assert code == 1 and err["code"] == "FEN-1003" and env["receipt"] is None
    assert folder_snapshot(tmp_path) == before, "both files hold their previous bytes and no .bak was added"


def test_handlers_are_put_back(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
    seen: list[object] = []

    def looking(_args: object, _ctx: Context) -> Result:
        seen.append(signal.getsignal(signal.SIGTERM))
        return Result()

    monkeypatch.setattr(cmd__echo, "COMMAND", dataclasses.replace(cmd__echo.COMMAND, run=looking))
    code, _, _, _ = run(monkeypatch, tmp_path, "_echo")
    assert code == 0 and seen and seen[0] is not before[1], "the command ran under Fenolite's handler"
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


@posix
def test_signal_inside_a_design_script(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """A signal that arrives while the design script runs is the signal, not a failure of the script."""
    (tmp_path / "design.py").write_text(
        "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\nraise SystemExit('not reached')\n",
        encoding="utf-8",
    )
    code, env, err, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "proj", "--confirm")
    assert code == 1 and err["code"] == "FEN-1003" and env["ok"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["design.py"]
    assert signal.getsignal(signal.SIGTERM) is not signal.SIG_IGN, "the caller's handler is back"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for(condition: Any, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return bool(condition())


@posix
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT], ids=["term", "int"])
def test_stopped_route_stops_its_router(tmp_path: Path, signum: int) -> None:
    """Scenario "A stopped route stops its router" (measured 7: the router kept running, with parent 1).
    The signal goes to the ``fenolite`` process alone, never to its group."""
    checkout = create_fake_router(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(BOARD, work / "board.kicad_pcb")
    before = folder_snapshot(work)
    pid_file = tmp_path / "router.pid"
    env = {
        **os.environ,
        "FENOLITE_TEST_SOURCE": str(ROOT / "src"),
        "FAKE_ROUTER_MODE": "sleep",
        "FAKE_ROUTER_SLEEP": "120",
        "FAKE_ROUTER_PID": str(pid_file),
    }
    command = [
        sys.executable, "-m", "fenolite", "route", "board.kicad_pcb", "--router", "kicadroutingtools",
        "--router-path", str(checkout), "--router-python", sys.executable, "--confirm", "--progress",
        "--json",
    ]  # fmt: skip
    process = subprocess.Popen(
        command, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,  # its own group: nothing but os.kill below reaches the router
    )  # fmt: skip
    router = 0
    try:
        assert _wait_for(lambda: pid_file.is_file() and pid_file.read_text(encoding="utf-8").strip(), 60), (
            "the fake router did not start"
        )
        router = int(pid_file.read_text(encoding="utf-8"))
        assert _alive(router)
        os.kill(process.pid, signum)
        out, err = process.communicate(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        if router and _alive(router):
            _wait_for(lambda: not _alive(router), 5)
            if _alive(router):
                os.kill(router, signal.SIGKILL)
                pytest.fail("the router outlived fenolite")
    assert process.returncode == 1, (out, err)
    lines = err.strip().splitlines()
    assert json.loads(lines[-1])["code"] == "FEN-1003"
    assert all("progress" in json.loads(line) for line in lines[:-1]) and len(lines) >= 2
    envelope = json.loads(out)
    assert envelope["ok"] is False and envelope["receipt"] is None
    assert not _alive(router), "the router process no longer exists"
    assert folder_snapshot(work) == before, "the board file is unchanged"
