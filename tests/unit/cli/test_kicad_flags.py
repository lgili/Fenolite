# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The global flags ``--kicad-version`` and ``--allow-lossy`` (capability cli-contract)."""

from __future__ import annotations

import argparse
import io
import json
from collections.abc import Callable, Iterator

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.versions import DEFAULT_TARGET, TARGET_MAJORS
from fenolite.cli.api import Command, Context, Result

Runner = Callable[[list[str]], tuple[int, dict[str, object], str]]


@pytest.fixture
def run_echo(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runner]:
    """A test-only command ``_kicad`` that returns the two context fields."""

    def run(args: argparse.Namespace, ctx: Context) -> Result:
        return Result(result={"kicad_target": ctx.kicad_target, "allow_lossy": ctx.allow_lossy})

    command = Command(
        name="_kicad", help="test-only command", mutates=False, register=lambda p: None, run=run
    )
    real = cli_main.discover
    monkeypatch.setattr(cli_main, "discover", lambda: {**real(), "_kicad": command})

    def invoke(argv: list[str]) -> tuple[int, dict[str, object], str]:
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        monkeypatch.setattr("sys.stderr", err)
        code = cli_main.main(argv)
        result: dict[str, object] = json.loads(out.getvalue())["result"] if out.getvalue().strip() else {}
        return code, result, err.getvalue()

    yield invoke


def test_flags_reach_the_context(run_echo: Runner) -> None:
    code, result, _ = run_echo(["--kicad-version", "9", "--allow-lossy", "_kicad", "--json"])
    assert code == 0 and result == {"kicad_target": 9, "allow_lossy": True}


def test_flags_after_the_command(run_echo: Runner) -> None:
    code, result, _ = run_echo(["_kicad", "--kicad-version", "9", "--allow-lossy", "--json"])
    assert code == 0 and result == {"kicad_target": 9, "allow_lossy": True}


def test_defaults(run_echo: Runner) -> None:
    code, result, _ = run_echo(["_kicad", "--json"])
    assert code == 0 and result == {"kicad_target": 10, "allow_lossy": False}


@pytest.mark.parametrize("value", ["8", "11", "ten"])
def test_unsupported_target_is_a_usage_error(run_echo: Runner, value: str) -> None:
    code, _, err = run_echo(["--kicad-version", value, "capabilities", "--json"])
    assert code == 2 and json.loads(err.strip().splitlines()[-1])["code"] == "FEN-2001"


def test_targets_match_the_backend() -> None:
    assert cli_main.KICAD_TARGETS == TARGET_MAJORS and cli_main.DEFAULT_KICAD_TARGET == DEFAULT_TARGET
    assert Context.__dataclass_fields__["kicad_target"].default == DEFAULT_TARGET
