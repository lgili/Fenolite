# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the agent-evaluation tests: the harness modules and ways to run ``fenolite`` (c0081).

``tools/agent_eval`` is a developer tool outside the package, so its modules are imported from the
``tools`` folder. ``in_process`` runs a ``fenolite`` command line inside the test process, which is how
the hermetic tests build a solution without starting anything.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_eval import judge, run, shim, tasks  # noqa: E402  (imported after the sys.path setup above)

import fenolite.cli.main as cli_main  # noqa: E402

__all__ = [
    "ROOT",
    "copy_task",
    "hermetic",
    "in_process",
    "judge",
    "real_fenolite",
    "run",
    "shim",
    "tasks",
    "tool",
]

REAL = (
    f"import sys\n\nsys.path.insert(0, {str(ROOT / 'src')!r})\n\n"
    "from fenolite.cli.main import main\n\nraise SystemExit(main())\n"
)
"""A program that is the ``fenolite`` command of this checkout, for the interpreter that runs it."""


def in_process(argv: list[str], cwd: Path) -> tuple[int, dict[str, Any], str]:
    """Run ``fenolite <argv>`` in this process, in ``cwd``: ``(exit code, envelope, standard error)``."""
    out, err = io.StringIO(), io.StringIO()
    before = Path.cwd()
    streams = sys.stdout, sys.stderr
    os.chdir(cwd)
    sys.stdout, sys.stderr = out, err
    try:
        code = cli_main.main(list(argv))
    finally:
        sys.stdout, sys.stderr = streams
        os.chdir(before)
    try:
        envelope = json.loads(out.getvalue())
    except json.JSONDecodeError:
        envelope = {}
    return code, envelope, err.getvalue()


def tool(folder: Path, source: str, name: str = "program.py") -> Path:
    """A launcher named ``fenolite`` in ``folder`` that runs the Python text ``source`` with this
    interpreter. It is written by the harness's own launcher writer, so it starts on Windows too."""
    folder.mkdir(parents=True, exist_ok=True)
    program = folder / name
    program.write_text(source, encoding="utf-8", newline="\n")
    return shim.install(folder, Path(sys.executable), program)


def real_fenolite(folder: Path) -> Path:
    """A launcher of the ``fenolite`` of the test environment."""
    return tool(folder, REAL, "real.py")


def copy_task(name: str, target: Path, change: dict[str, str] | None = None) -> Path:
    """Copy a task into ``target`` and replace text in its ``task.toml``. Returns the tasks folder."""
    shutil.copytree(tasks.TASKS_DIR / name, target / name)
    path = target / name / "task.toml"
    text = path.read_text(encoding="utf-8")
    for old, new in (change or {}).items():
        assert old in text, old
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    return target


def hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No child process, no KiCad and no library: ``subprocess.run`` and ``subprocess.Popen`` raise, no
    ``kicad-cli`` is found, and the two functions of the harness that start ``fenolite`` run it in this
    process instead."""
    import subprocess

    import fenolite.backends.kicad.cli as kicad_cli

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a child process was started: {args!r}")

    def line(argv: list[str], cwd: Path, env: object = None) -> int:
        assert argv[0] == "fenolite", argv
        return in_process(list(argv[1:]), cwd)[0]

    def command(argv: list[str], cwd: Path) -> judge.Completed:
        assert argv[0] == "fenolite", argv
        code, envelope, err = in_process(list(argv[1:]), cwd)
        return judge.Completed(code, json.dumps(envelope), err)

    empty = tmp_path / "empty-path"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(run, "run_line", line)
    monkeypatch.setattr(judge, "run_command", command)
