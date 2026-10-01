# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library exceptions raised inside a command map to registered codes (capability cli-contract)."""

from __future__ import annotations

import argparse
import io
import json
from collections.abc import Callable, Iterator

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.versions import (
    DowngradeRefusedError,
    FileKind,
    FormatInfo,
    FutureFormatError,
    VersionStatus,
    require_readable,
)
from fenolite.cli.api import Command, Context, Result
from fenolite.core.errors import FenoliteError, FormatError

Raiser = Callable[[], None]


class Unregistered(FenoliteError):
    cli_code = "FEN-3999"


@pytest.fixture
def run_raising(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Raiser, list[str]], tuple[int, str]]]:
    """Register a test-only command ``_raise`` in the discovered set and run it."""
    holder: dict[str, Raiser] = {}

    def run(args: argparse.Namespace, ctx: Context) -> Result:
        holder["raise"]()
        return Result()

    command = Command(
        name="_raise", help="test-only command", mutates=False, register=lambda p: None, run=run
    )
    real = cli_main.discover

    monkeypatch.setattr(cli_main, "discover", lambda: {**real(), "_raise": command})

    def invoke(raiser: Raiser, extra: list[str]) -> tuple[int, str]:
        holder["raise"] = raiser
        err = io.StringIO()
        monkeypatch.setattr("sys.stderr", err)
        monkeypatch.setattr("sys.stdout", io.StringIO())
        code = cli_main.main(["_raise", *extra])
        return code, err.getvalue()

    yield invoke


def _error(stderr: str) -> dict[str, object]:
    return json.loads(stderr.strip().splitlines()[-1])


def test_future_format_maps_to_exit_3(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        raise FutureFormatError("board 20990101 is newer than 20260206", file="a.kicad_pcb")

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 3 and error["code"] == "FEN-3002" and error["where"] == "a.kicad_pcb"
    assert not str(error["message"]).startswith("a.kicad_pcb")


def test_too_old_input_carries_the_upgrade_hint(
    run_raising: Callable[[Raiser, list[str]], tuple[int, str]],
) -> None:
    def raiser() -> None:
        require_readable(FormatInfo(FileKind.BOARD, 20221018, None, VersionStatus.TOO_OLD))

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 3 and error["code"] == "FEN-3003" and "kicad-cli pcb upgrade" in str(error["hint"])


def test_downgrade_maps_to_exit_7(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        raise DowngradeRefusedError(FileKind.BOARD, 10, 9)

    code, stderr = run_raising(raiser, ["--json"])
    assert code == 7 and _error(stderr)["code"] == "FEN-7002"


def test_plain_format_error_maps_to_exit_3(
    run_raising: Callable[[Raiser, list[str]], tuple[int, str]],
) -> None:
    def raiser() -> None:
        raise FormatError("unbalanced parenthesis", file="b.kicad_pcb", offset=12)

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 3 and error["code"] == "FEN-3004"
    assert error["message"] == "unbalanced parenthesis" and error["where"] == "b.kicad_pcb:@12"


def test_unregistered_code_falls_back_to_internal_error(
    run_raising: Callable[[Raiser, list[str]], tuple[int, str]],
) -> None:
    def raiser() -> None:
        raise Unregistered("odd")

    code, stderr = run_raising(raiser, ["--json"])
    assert code == 1 and _error(stderr)["code"] == "FEN-1001"


def test_text_mode(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        raise FormatError("bad", file="c.kicad_pcb", locator="/kicad_pcb", offset=3)

    code, stderr = run_raising(raiser, ["--text"])
    assert code == 3 and "FEN-3004" in stderr
