# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.run`` (capability python-api, "In-process command runner" and "In-process limits"; change
c0206). The comparison with the command line for every command is ``tests/consistency/test_api_run.py``."""

from __future__ import annotations

import dataclasses
import os
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fenolite.api import Reply, run
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.main import IN_PROCESS_HELP

DATA = Path(__file__).resolve().parents[2] / "data"
BOARD = DATA / "kicad" / "board" / "two_layer.kicad_pcb"


def _code(reply: Reply) -> str:
    assert reply.error is not None
    return str(reply.error["code"])


def test_reply_of_a_read_only_command(capfd: pytest.CaptureFixture[str]) -> None:
    """Scenario "Nothing printed": the envelope comes back as a value, and nothing reaches fd 1 or 2."""
    reply = run("inspect", str(BOARD), "--summary")
    assert reply.ok and reply.error is None and reply.envelope is not None
    assert reply.envelope["command"] == "inspect" and reply.envelope["schema"] == "fenolite.inspect.v0"
    assert reply.result is reply.envelope["result"]
    assert reply.envelope["evidence"]["level"]
    assert capfd.readouterr() == ("", "")


def test_signal_handlers_and_cwd_are_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM), os.getcwd())
    assert run("_echo", "--write", "x.txt", cwd=tmp_path / ".").exit_code == 4
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM), os.getcwd()) == before


@pytest.mark.parametrize("flag", ["--help", "-h", "--hel"])
def test_help_is_a_usage_error(flag: str, capfd: pytest.CaptureFixture[str]) -> None:
    """Scenario "Terminal-only forms refused": argparse's abbreviation of ``--help`` too."""
    reply = run("analyze", flag)
    assert reply.exit_code == 2 and reply.envelope is None and _code(reply) == "FEN-2001"
    assert reply.error is not None and reply.error["message"] == IN_PROCESS_HELP
    assert capfd.readouterr() == ("", "")


def test_text_restore_stdin_and_serve_are_usage_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Terminal-only forms refused": no stdin is read and nothing blocks."""
    monkeypatch.setattr(sys, "stdin", None)  # a read would raise: the refusal comes first
    assert _code(run("capabilities", "--text")) == "FEN-2001"
    restore = run("restore", "-", "--dry-run")
    assert restore.exit_code == 2 and _code(restore) == "FEN-2001" and restore.envelope is not None
    serve = run("view", str(BOARD), "--serve", "--no-browser")
    assert serve.exit_code == 2 and _code(serve) == "FEN-2001"
    assert serve.error is not None and serve.error["where"] == "--serve"


def test_seed_and_timestamp_keywords_are_the_flags(tmp_path: Path) -> None:
    by_flags = run("_echo", "--gen-id", "--seed", "3", "--timestamp", "2026-10-28T00:00:00Z", cwd=tmp_path)
    by_keywords = run("_echo", "--gen-id", cwd=tmp_path, seed=3, timestamp=datetime(2026, 10, 28, tzinfo=UTC))
    assert by_flags.ok and by_flags.result == by_keywords.result


def test_python_faults_raise() -> None:
    with pytest.raises(ValueError, match="not a command name"):
        run("--json")
    with pytest.raises(TypeError, match="str arguments"):
        run("inspect", BOARD)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="seed is given twice"):
        run("_echo", "--seed", "1", seed=2)
    with pytest.raises(ValueError, match="not a folder"):
        run("_echo", cwd=BOARD)


def test_unknown_command_is_a_usage_reply() -> None:
    reply = run("no-such-command")
    assert reply.exit_code == 2 and reply.envelope is None and _code(reply) == "FEN-2001"


def test_internal_failure_and_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bug is ``FEN-1001`` with the envelope, an interrupt ``FEN-1003``, as on the command line."""
    module = sys.modules["fenolite.cli.cmd__echo"]
    command: Command = module.COMMAND

    def boom(_args: object, _ctx: Context) -> Result:
        raise RuntimeError("forced failure")

    def stop(_args: object, _ctx: Context) -> Result:
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(command, run=boom))
    failed = run("_echo")
    assert failed.exit_code == 1 and _code(failed) == "FEN-1001"
    assert failed.envelope is not None and failed.envelope["ok"] is False
    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(command, run=stop))
    stopped = run("_echo")
    assert stopped.exit_code == 1 and _code(stopped) == "FEN-1003"


def test_every_public_name_is_on_the_api_page() -> None:
    """Scenario "Every public name documented": each name of ``fenolite.api.__all__`` is on the page."""
    import fenolite.api

    page = (Path(__file__).resolve().parents[3] / "docs" / "api.md").read_text(encoding="utf-8")
    missing = [name for name in fenolite.api.__all__ if f"`{name}" not in page]
    assert missing == []
