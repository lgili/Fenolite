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
    LegacyEditRefusedError,
    LossyWriteError,
    VersionStatus,
    require_readable,
)
from fenolite.cli.api import Command, Context, Result
from fenolite.core.errors import FenoliteError, FormatError, Issue

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
    error = _error(stderr)
    assert code == 7 and error["code"] == "FEN-7002"
    assert "fenolite convert <project> --to kicad --kicad-version 9" in str(error["hint"])


def test_legacy_edit_maps_to_exit_7(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        raise LegacyEditRefusedError(FileKind.BOARD, 20240108)

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 7 and error["code"] == "FEN-7003" and "kicad-cli pcb upgrade" in str(error["hint"])


def test_lossy_write_maps_to_exit_7(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        issue = Issue("kicad.token.too-new", "error", "'duplicate_pad_numbers_are_jumpers' needs KiCad 10.0")
        raise LossyWriteError([issue], droppable=True)

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 7 and error["code"] == "FEN-7001" and "--allow-lossy" in str(error["hint"])


def test_kept_loss_keeps_its_own_hint(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    def raiser() -> None:
        issue = Issue("kicad.board.opaque-net-ref", "error", "net 7 is not in the source table")
        raise LossyWriteError([issue], droppable=False)

    code, stderr = run_raising(raiser, ["--json"])
    error = _error(stderr)
    assert code == 7 and error["code"] == "FEN-7001" and "--allow-lossy" not in str(error["hint"])


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


# --- refusals carry their issues and geometry errors (change c0011) ---------------------------------


@pytest.fixture
def run_raising_out(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[Raiser, list[str]], tuple[int, str, str]]]:
    """Like ``run_raising``, and also returns stdout, so the envelope's ``issues`` can be read."""
    holder: dict[str, Raiser] = {}

    def run(args: argparse.Namespace, ctx: Context) -> Result:
        holder["raise"]()
        return Result()

    command = Command(
        name="_raise", help="test-only command", mutates=False, register=lambda p: None, run=run
    )
    real = cli_main.discover
    monkeypatch.setattr(cli_main, "discover", lambda: {**real(), "_raise": command})

    def invoke(raiser: Raiser, extra: list[str]) -> tuple[int, str, str]:
        holder["raise"] = raiser
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr("sys.stderr", err)
        monkeypatch.setattr("sys.stdout", out)
        code = cli_main.main(["_raise", *extra])
        return code, out.getvalue(), err.getvalue()

    yield invoke


def test_geometry_error_maps_to_exit_3(run_raising: Callable[[Raiser, list[str]], tuple[int, str]]) -> None:
    from fenolite.geometry.errors import GeometryError

    def boom() -> None:
        raise GeometryError("zero-length segment", points=())

    code, err = run_raising(boom, ["--json"])
    assert code == 3 and json.loads(err)["code"] == "FEN-3005"


def test_registry_row_and_codes_table() -> None:
    from pathlib import Path

    from fenolite.cli.errors import REGISTRY
    from fenolite.cli.exitcodes import ExitCode

    assert REGISTRY["FEN-3005"].exit_code is ExitCode.INPUT
    contract = (Path(__file__).resolve().parents[3] / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    assert "| `FEN-3005` |" in contract


def test_lossy_refusal_lists_its_issues(
    run_raising_out: Callable[[Raiser, list[str]], tuple[int, str, str]],
) -> None:
    issues = [
        Issue("kicad.token.too-new", "error", "a", where="/x"),
        Issue("kicad.token.too-new", "error", "b"),
    ]

    def boom() -> None:
        raise LossyWriteError(issues, droppable=True)

    code, out, err = run_raising_out(boom, ["--json"])
    assert code == 7 and json.loads(err)["code"] == "FEN-7001"
    assert [i["message"] for i in json.loads(out)["issues"]] == ["a", "b"]


def test_exceptions_without_issues_are_unchanged(
    run_raising_out: Callable[[Raiser, list[str]], tuple[int, str, str]],
) -> None:
    def boom() -> None:
        raise FormatError("bad", file="x")

    code, out, _ = run_raising_out(boom, ["--json"])
    assert code == 3 and json.loads(out)["issues"] == []
