# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The mutation protocol and same-major fill through a fake KiCad runner or --from."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli

from fenolite.backends.kicad.pcb import write_board
from fenolite.model.design import Design

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "kicad" / "fill"


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    folder = tmp_path / "project"
    folder.mkdir()
    path = folder / "board.kicad_pcb"
    shutil.copyfile(FIXTURES / "triad_t9.kicad_pcb", path)
    return path


def test_from_plans_then_confirms_one_same_major_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    source = str(FIXTURES / "triad_t9_refilled.kicad_pcb")
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--from", source, "--dry-run")
    assert code == 0 and env["result"]["changed"] and len(env["result"]["plan"]) == 1
    assert board.read_bytes() == (FIXTURES / "triad_t9.kicad_pcb").read_bytes()
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--from", source, "--confirm")
    assert code == 0 and board.read_bytes() == (FIXTURES / "triad_t9_filled.kicad_pcb").read_bytes()
    assert env["receipt"]["written"][0]["sha256"] == hashlib.sha256(board.read_bytes()).hexdigest()
    assert board.with_suffix(".kicad_pcb.bak").is_file()
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--from", source, "--dry-run")
    assert code == 0 and not env["result"]["changed"] and "plan" not in env["result"]


def test_fake_runner_gets_copy_set_and_never_edits_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    saved = (FIXTURES / "triad_t9_refilled.kicad_pcb").read_text(encoding="utf-8")
    fake = fake_kicad_cli(tmp_path / "bin", refill_board=saved)
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--kicad-cli", str(fake), "--dry-run")
    assert code == 0 and env["result"]["changed"] and env["result"]["tool_version"] == "10.0.6"
    assert board.read_bytes() == (FIXTURES / "triad_t9.kicad_pcb").read_bytes()
    assert any("--refill-zones" in c["args"] and "--save-board" in c["args"] for c in calls(fake))


def test_missing_or_old_tool_is_typed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "fill", str(board), "--dry-run")
    assert code == 6 and error["code"] == "FEN-6001"
    old = fake_kicad_cli(tmp_path / "bin", version="9.0.9")
    code, _, error, _ = run(monkeypatch, tmp_path, "fill", str(board), "--kicad-cli", str(old), "--dry-run")
    assert code == 6 and error["code"] == "FEN-6002" and "--from" in error["hint"]


def test_no_zone_needs_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = tmp_path / "empty.kicad_pcb"
    board.write_text(write_board(Design.new("empty", seed=0), target=9).text, encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--dry-run")
    assert code == 0 and env["result"]["changed"] is False
    assert [i["code"] for i in env["issues"]] == ["zone.none"]


def test_output_path_and_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    source = str(FIXTURES / "triad_t9_refilled.kicad_pcb")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "fill", str(board), "--from", source, "--out", "other.kicad_pcb", "--confirm"
    )
    assert code == 0 and (tmp_path / "other.kicad_pcb").is_file()
    assert board.read_bytes() == (FIXTURES / "triad_t9.kicad_pcb").read_bytes()
    wrong = tmp_path / "wrong.kicad_pcb"
    wrong.write_text(
        (FIXTURES / "triad_t9_refilled.kicad_pcb")
        .read_text()
        .replace("2d81e5b3-01a4-5810-b23d-324ba9f75285", "11111111-1111-4111-8111-111111111111"),
        encoding="utf-8",
    )
    code, env, _, _ = run(monkeypatch, tmp_path, "fill", str(board), "--from", str(wrong), "--dry-run")
    assert code == 5 and any(i["code"] == "zone.fill-mismatch" for i in env["issues"])
    assert "plan" not in env["result"]
