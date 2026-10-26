# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite edit`` (capability cli-contract, "Edit command" and "Edit checks without running";
change c0196): whole texts and exact edits of design files, planned with a diff, parsed and never run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.main import main

SCRIPT = 'from fenolite.dsl import Design\n\nWIDTH_MM = 20\ndesign = Design("demo")\n'


@pytest.fixture(autouse=True)
def folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def run(capsys: Any, *argv: str) -> tuple[int, Any, Any]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out.strip() else None
    err = json.loads(captured.err.strip().splitlines()[-1]) if captured.err.strip() else None
    return code, out, err


def edits(folder: Path, *pairs: tuple[str, str]) -> str:
    (folder / "edits.json").write_text(json.dumps([{"old": o, "new": n} for o, n in pairs]), encoding="utf-8")
    return "edits.json"


def test_exact_edit_planned_and_written(capsys: Any, folder: Path) -> None:
    """Scenario "An exact edit planned and written"."""
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    name = edits(folder, ("WIDTH_MM = 20", "WIDTH_MM = 25"))
    code, out, _ = run(capsys, "edit", "design.py", "--edits-file", name, "--dry-run")
    assert code == 0 and (folder / "design.py").read_text(encoding="utf-8") == SCRIPT
    result = out["result"]
    assert (result["lines_added"], result["lines_removed"], result["changed"]) == (1, 1, True)
    assert "-WIDTH_MM = 20\n+WIDTH_MM = 25" in result["diff"]
    code, out, _ = run(
        capsys, "edit", "design.py", "--edits-file", name, "--confirm", "--plan", result["plan_id"]
    )
    assert code == 0 and [w["path"] for w in out["receipt"]["written"]] == ["design.py"]
    assert "WIDTH_MM = 25" in (folder / "design.py").read_text(encoding="utf-8")


def test_edit_that_breaks_the_script_is_refused(capsys: Any, folder: Path) -> None:
    """Scenario "An edit that breaks the script is refused": parsed, never run, nothing staged."""
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    name = edits(folder, ('Design("demo")', 'Design("demo"'))
    code, _, err = run(capsys, "edit", "design.py", "--edits-file", name, "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and err["where"] == "design.py:4"
    assert not (folder.parent / "state" / "plans").exists() or not any(
        (folder.parent / "state" / "plans").iterdir()
    )


def test_old_text_found_twice(capsys: Any, folder: Path) -> None:
    """Scenario "An old text found twice"."""
    (folder / "design.py").write_text(SCRIPT + "WIDTH_MM = 20\n", encoding="utf-8")
    code, _, err = run(
        capsys, "edit", "design.py", "--edits-file", edits(folder, ("WIDTH_MM = 20", "x = 1")), "--dry-run"
    )
    assert code == 3 and err["code"] == "FEN-3004" and "found 2 times" in err["message"]


def test_script_is_never_run(capsys: Any, folder: Path) -> None:
    """A script that would write a file when run is only parsed."""
    (folder / "new.txt").write_text('open("ran.txt", "w").write("x")\n', encoding="utf-8")
    code, out, _ = run(capsys, "edit", "design.py", "--content-file", "new.txt", "--dry-run")
    assert code == 0 and out["result"]["created"] is True and not (folder / "ran.txt").exists()


def test_create_with_content(capsys: Any, folder: Path) -> None:
    (folder / "new.txt").write_text(SCRIPT, encoding="utf-8")
    code, out, _ = run(capsys, "edit", "boards/design.py", "--content-file", "new.txt", "--dry-run")
    assert code == 0 and out["result"]["created"] is True and out["result"]["lines_added"] == 4
    assert out["result"]["plan"][0]["path"] == "boards/design.py"


def test_edits_need_an_existing_file(capsys: Any, folder: Path) -> None:
    code, _, err = run(capsys, "edit", "design.py", "--edits-file", edits(folder, ("a", "b")), "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"


def test_other_files_are_refused(capsys: Any, folder: Path) -> None:
    (folder / "new.txt").write_text("x", encoding="utf-8")
    code, _, err = run(capsys, "edit", "board.kicad_pcb", "--content-file", "new.txt", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_toml_must_parse(capsys: Any, folder: Path) -> None:
    (folder / "placements.toml").write_text('[R1]\nx = "1 mm"\n', encoding="utf-8")
    name = edits(folder, ('x = "1 mm"', 'x = "1 mm'))
    code, _, err = run(capsys, "edit", "placements.toml", "--edits-file", name, "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and "TOML" in err["message"]


def test_library_table_needs_no_parse(capsys: Any, folder: Path) -> None:
    (folder / "table.txt").write_text("(fp_lib_table\n  (version 7)\n)\n", encoding="utf-8")
    code, out, _ = run(capsys, "edit", "fp-lib-table", "--content-file", "table.txt", "--dry-run")
    assert code == 0 and out["result"]["kind"] == "library-table"


def test_line_ends_are_kept(capsys: Any, folder: Path) -> None:
    (folder / "design.py").write_bytes(SCRIPT.replace("\n", "\r\n").encode("utf-8"))
    name = edits(folder, ("WIDTH_MM = 20\nd", "WIDTH_MM = 21\nd"))
    code, out, _ = run(capsys, "edit", "design.py", "--edits-file", name, "--dry-run")
    assert code == 0, out
    code, _, _ = run(
        capsys, "edit", "design.py", "--edits-file", name, "--confirm", "--plan", out["result"]["plan_id"]
    )
    assert code == 0 and (folder / "design.py").read_bytes().count(b"\r\n") == 4
    assert b"WIDTH_MM = 21\r\n" in (folder / "design.py").read_bytes()


def test_unchanged_text_plans_nothing(capsys: Any, folder: Path) -> None:
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    code, out, _ = run(capsys, "edit", "design.py", "--content-file", "design.py")
    assert code == 0 and out["result"]["changed"] is False and out["receipt"] is None


def test_path_on_another_drive(monkeypatch: pytest.MonkeyPatch, capsys: Any, folder: Path) -> None:
    """On Windows a file on another drive has no path relative to the working folder: it is shown absolute."""
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")

    def no_relative(path: object, start: object = None) -> str:
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    monkeypatch.setattr("fenolite.cli.cmd_edit.os.path.relpath", no_relative)
    code, out, err = run(capsys, "edit", str(folder / "design.py"), "--content-file", "design.py")
    assert code == 0, err
    assert out["result"]["path"] == (folder / "design.py").as_posix()
