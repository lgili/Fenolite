# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every command's ``example_args`` run without a subprocess, from an empty working directory
(capability verification-loop, scenario "Example arguments are hermetic"; change c0013)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run

from fenolite.cli.api import discover

COMMANDS = sorted(name for name, command in discover().items() if command.example_args)


@pytest.mark.parametrize("name", COMMANDS)
def test_example_arguments_are_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    hide_kicad(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"{name} started a subprocess")

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
