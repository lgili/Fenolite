# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every command's ``example_args`` run without a subprocess, from an empty working directory
(capability verification-loop, scenario "Example arguments are hermetic"; change c0013). A command that
names ``kicad-cli`` in ``example_tools`` runs against the fake instead (capability cli-contract,
"Tool-backed command examples"; change c0024)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakecli import fake_kicad_cli

from fenolite.cli.api import discover

COMMANDS = sorted(name for name, command in discover().items() if command.example_args)


@pytest.mark.parametrize("name", COMMANDS)
def test_example_arguments_are_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    hide_kicad(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"{name} started a subprocess")

    command = discover()[name]
    if "kicad-cli" in command.example_tools:
        monkeypatch.setenv("FENOLITE_KICAD_CLI", str(fake_kicad_cli(tmp_path / "fake-kicad")))
    else:
        monkeypatch.setattr(subprocess, "run", refuse)
        monkeypatch.setattr(subprocess, "Popen", refuse)
    work = tmp_path / "work"
    work.mkdir()
    code, env, err, _ = run(monkeypatch, work, name, *discover()[name].example_args)
    assert code == 0, err
    if name == "check":
        assert env["input"]["path"] == "two_layer.kicad_pcb"


def test_check_is_listed() -> None:
    assert "check" in COMMANDS


def test_tool_backed_commands() -> None:
    """Only ``export`` and ``render`` need a tool for their examples; every other command stays tool-free."""
    assert sorted(n for n, c in discover().items() if c.example_tools) == ["export", "render"]
