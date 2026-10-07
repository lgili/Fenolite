# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import io
import json

import pytest

from fenolite.cli.errors import ErrorInfo
from fenolite.cli.output import (
    Envelope,
    Evidence,
    FieldNotFoundError,
    InputRef,
    Issue,
    Receipt,
    WrittenFile,
    parse_fields,
    project_fields,
    render_json,
    render_text,
    resolve_mode,
    write_error,
)


class _Stream(io.StringIO):
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _envelope(**kw: object) -> Envelope:
    base: dict[str, object] = {
        "ok": True, "command": "demo", "schema": "fenolite.demo.v0", "input": None,
        "result": {"a": 1, "b": {"c": [1, 2], "d": None}}, "issues": (), "evidence": Evidence(),
        "receipt": None, "elapsed_ms": 3,
    }  # fmt: skip
    base.update(kw)
    return Envelope(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("force_json", "force_text", "tty", "expected"),
    [
        (False, False, False, "json"),
        (False, False, True, "text"),
        (True, False, True, "json"),
        (False, True, False, "text"),
    ],
)
def test_mode_selection(force_json: bool, force_text: bool, tty: bool, expected: str) -> None:
    assert resolve_mode(force_json=force_json, force_text=force_text, stream=_Stream(tty)) == expected


def test_json_has_exactly_the_envelope_keys_in_order() -> None:
    data = json.loads(render_json(_envelope()))
    assert list(data) == [
        "ok",
        "command",
        "schema",
        "input",
        "result",
        "issues",
        "evidence",
        "receipt",
        "elapsed_ms",
    ]
    assert data["evidence"] == {"level": "UNVERIFIED", "oracle": None, "hypotheses": []}


def test_json_is_a_single_line_document() -> None:
    assert "\n" not in render_json(_envelope())


def test_projection_keeps_only_requested_paths() -> None:
    result = {"a": 1, "b": {"c": [1, 2], "d": None}, "e": 5}
    assert project_fields(result, ["b.c", "e"]) == {"b": {"c": [1, 2]}, "e": 5}
    assert parse_fields(" a, b.c ,,") == ["a", "b.c"]


def test_projection_unknown_path() -> None:
    with pytest.raises(FieldNotFoundError):
        project_fields({"a": 1}, ["a.b"])
    with pytest.raises(FieldNotFoundError):
        project_fields({"a": 1}, ["nope"])


@pytest.mark.parametrize("code", ["model.duplicate-ref", "kicad.drc.clearance", "echo.error"])
def test_valid_issue_codes(code: str) -> None:
    assert Issue(code=code, severity="error", message="m").code == code


@pytest.mark.parametrize("code", ["Bad Code", "nodot", "Model.x", "a..b"])
def test_invalid_issue_codes(code: str) -> None:
    with pytest.raises(ValueError):
        Issue(code=code, severity="error", message="m")


def test_invalid_severity() -> None:
    with pytest.raises(ValueError):
        Issue(code="a.b", severity="fatal", message="m")  # type: ignore[arg-type]


def test_text_rendering_is_not_json_and_carries_the_same_content() -> None:
    env = _envelope(
        ok=False,
        input=InputRef(path="board.kicad_pcb", sha256=None, kind="kicad_pcb", format_version="20260206"),
        issues=(Issue(code="a.b", severity="error", message="boom", where="R1", hint="fix"),),
        evidence=Evidence(level="ORACLE-VERIFIED", oracle="kicad-import"),
        receipt=Receipt(written=(WrittenFile(path="out.txt", sha256="0" * 64),), backup=("out.txt.bak",)),
    )
    text = render_text(env)
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    for needle in (
        "FAILED",
        "board.kicad_pcb",
        "error: a.b: boom [R1] (hint: fix)",
        "evidence: ORACLE-VERIFIED(kicad-import)",
        "wrote: out.txt",
        "backup: out.txt.bak",
        "c:",
    ):
        assert needle in text  # fmt: skip


def test_error_writer_modes() -> None:
    info = ErrorInfo(code="FEN-2001", message="bad", hint="try --help", retryable=False, where="")
    js, tx = io.StringIO(), io.StringIO()
    write_error(info, "json", js)
    write_error(info, "text", tx)
    assert json.loads(js.getvalue()) == {"code": "FEN-2001", "message": "bad", "hint": "try --help",
                                         "retryable": False, "where": ""}  # fmt: skip
    assert tx.getvalue() == "error FEN-2001: bad (try --help)\n"


# --- c0079: a command's own text (capability cli-contract, "Command text") ---------------------------


def _echo(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    from fenolite.cli.main import main

    code = main(["_echo", *args])
    return code, capsys.readouterr().out


def test_command_text_is_printed_after_the_status_line(capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Text is printed after the status line"."""
    code, out = _echo(capsys, "--text-body", "line one", "--text")
    assert code == 0 and out == "fenolite _echo: ok\n\nline one\n"
    code, out = _echo(capsys, "--text-body", "line one", "--json")
    envelope = json.loads(out)
    assert code == 0 and "line one" not in out and "text" not in envelope
    code, plain = _echo(capsys, "--json")
    assert sorted(envelope) == sorted(json.loads(plain))


def test_command_text_is_followed_by_issues(capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Issues follow the text"."""
    code, out = _echo(capsys, "--text-body", "line one", "--issue", "warning", "--text")
    lines = out.split("\n")
    assert code == 0 and lines[:4] == ["fenolite _echo: ok", "", "line one", ""]
    assert lines[4].startswith("warning: echo.warning:") and lines[5:] == [""]


def test_command_text_keeps_its_own_newline_and_the_receipt(
    capsys: pytest.CaptureFixture[str], tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(str(tmp_path))
    code, out = _echo(capsys, "--text-body", "a\n\nb\n", "--text")
    assert code == 0 and out == "fenolite _echo: ok\n\na\n\nb\n"
    code, out = _echo(capsys, "--text-body", "body", "--write", "x.txt", "--confirm", "--text")
    lines = out.split("\n")
    assert code == 0 and lines[:4] == ["fenolite _echo: ok", "", "body", ""]
    assert lines[4].startswith("wrote: x.txt sha256=") and lines[5:] == [""]
    assert "evidence:" not in out and "result:" not in out


def test_command_text_with_concise_format(capsys: pytest.CaptureFixture[str]) -> None:
    """``--format concise`` folds the issues and leaves the text alone."""
    code, out = _echo(capsys, "--text-body", "line one", "--issues", "3", "--format", "concise", "--text")
    lines = out.split("\n")
    assert code == 0 and lines[:4] == ["fenolite _echo: ok", "", "line one", ""]
    assert [line.split(":")[0] for line in lines[4:] if line] == ["warning"]


def test_command_text_is_not_printed_for_a_failed_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _echo(capsys, "--text-body", "line one", "--issue", "error", "--text")
    assert code == 5 and out.startswith("fenolite _echo: FAILED\n") and "evidence:" in out


def test_text_rendering_without_command_text_is_unchanged() -> None:
    envelope = _envelope()
    assert render_text(envelope) == render_text(envelope, None)
    assert render_text(envelope, "x").split("\n") == ["fenolite demo: ok", "", "x"]
