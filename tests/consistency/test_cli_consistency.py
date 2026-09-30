# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every registered command honours the CLI contract (docs/cli-contract.md).

A new ``cmd_*.py`` is picked up automatically; if it breaks the contract, the failing test id
names it.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import _schema
import pytest

from fenolite.cli.api import Command, Context, Result, discover, module_name_for
from fenolite.cli.main import main

COMMANDS = discover()
NAMES = sorted(COMMANDS)
MUTATING = sorted(n for n, c in COMMANDS.items() if c.mutates)
ENVELOPE = _schema.load("fenolite.envelope.v0.json")
ERROR = _schema.load("fenolite.error.v0.json")
CapSys = pytest.CaptureFixture[str]


def _invoke(capsys: CapSys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _assert_envelope(name: str, out: str) -> dict[str, Any]:
    assert out.endswith("\n") and out.count("\n") == 1, "stdout must be one JSON document plus newline"
    data = json.loads(out)
    assert _schema.validate(data, ENVELOPE) == [], _schema.validate(data, ENVELOPE)
    assert data["command"] == name and data["schema"] == f"fenolite.{name}.v0"
    return data


def _assert_error(err: str, exit_code: int) -> dict[str, Any]:
    data = json.loads(err)
    assert _schema.validate(data, ERROR) == []
    assert int(data["code"][4]) == exit_code
    return data


def test_there_are_commands() -> None:
    assert "capabilities" in COMMANDS and "_echo" in COMMANDS


@pytest.mark.parametrize("name", NAMES)
def test_help(name: str, capsys: CapSys) -> None:
    code, out, _ = _invoke(capsys, [name, "--help"])
    assert code == 0 and f"usage: fenolite {name}" in out


@pytest.mark.parametrize("name", NAMES)
def test_json_envelope(name: str, capsys: CapSys) -> None:
    code, out, err = _invoke(capsys, [name, *COMMANDS[name].example_args, "--json"])
    assert code == 0, err
    data = _assert_envelope(name, out)
    assert data["ok"] is True and err == ""


@pytest.mark.parametrize("name", NAMES)
def test_text_mode(name: str, capsys: CapSys) -> None:
    code, out, _ = _invoke(capsys, [name, *COMMANDS[name].example_args, "--text"])
    assert code == 0 and out.strip()
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert out.startswith(f"fenolite {name}: ok")


@pytest.mark.parametrize("name", NAMES)
def test_fields_projection(name: str, capsys: CapSys) -> None:
    args = [name, *COMMANDS[name].example_args, "--json"]
    _, out, _ = _invoke(capsys, args)
    keys = list(json.loads(out)["result"])
    if not keys:
        pytest.skip(f"{name} returns an empty result")
    code, out, _ = _invoke(capsys, [*args, "--fields", keys[0]])
    assert code == 0 and list(json.loads(out)["result"]) == [keys[0]]
    code, _, err = _invoke(capsys, [*args, "--fields", "no-such-field"])
    assert code == 2 and _assert_error(err, 2)["code"] == "FEN-2002"


@pytest.mark.parametrize("name", NAMES)
def test_unknown_flag_is_usage_error(name: str, capsys: CapSys) -> None:
    code, out, err = _invoke(capsys, [name, "--no-such-flag", "--json"])
    assert code == 2 and out == ""
    _assert_error(err, 2)


@pytest.mark.parametrize("name", NAMES)
def test_internal_exception_maps_to_exit_1(
    name: str, capsys: CapSys, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_args: object, _ctx: Context) -> Result:
        raise RuntimeError("forced failure")

    module = sys.modules[f"fenolite.cli.{module_name_for(name)}"]
    command: Command = module.COMMAND
    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(command, run=boom))
    code, out, err = _invoke(capsys, [name, *command.example_args, "--json"])
    assert code == 1
    assert _assert_envelope(name, out)["ok"] is False
    assert _assert_error(err, 1)["code"] == "FEN-1001"


@pytest.mark.parametrize("name", MUTATING)
def test_mutation_protocol(
    name: str, capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = COMMANDS[name]
    assert command.mutation_example_args is not None, (
        f"{name} is mutating but declares no mutation_example_args"
    )
    monkeypatch.chdir(tmp_path)
    args = [name, *command.mutation_example_args, "--json"]

    code, out, err = _invoke(capsys, args)
    assert code == 4 and list(tmp_path.iterdir()) == []
    assert _assert_envelope(name, out)["result"]["plan"]
    assert _assert_error(err, 4)["code"] == "FEN-4001"

    code, out, _ = _invoke(capsys, [*args, "--dry-run"])
    assert code == 0 and list(tmp_path.iterdir()) == []
    plan = _assert_envelope(name, out)["result"]["plan"]

    code, out, _ = _invoke(capsys, [*args, "--confirm"])
    assert code == 0
    receipt = _assert_envelope(name, out)["receipt"]
    assert [w["path"] for w in receipt["written"]] == [p["path"] for p in plan]
    assert all((tmp_path / w["path"]).is_file() for w in receipt["written"])

    code, _, err = _invoke(capsys, [*args, "--dry-run", "--confirm"])
    assert code == 2 and _assert_error(err, 2)["code"] == "FEN-2003"


@pytest.mark.parametrize("name", NAMES)
def test_non_mutating_commands_reject_protocol_flags(name: str, capsys: CapSys) -> None:
    if COMMANDS[name].mutates:
        pytest.skip("mutating")
    code, _, _ = _invoke(capsys, [name, "--confirm", "--json"])
    assert code == 2
