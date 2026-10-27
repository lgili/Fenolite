# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite refs`` (change c0201; capability file-safety, "Project references")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run
from _safetyproject import OLD, project, table

from fenolite.safety.files import companions
from fenolite.safety.refs import project_refs, repoint


def test_paths_of_a_project(tmp_path: Path) -> None:
    board = project(tmp_path)
    refs = project_refs(board.parent, companions(board))
    rows = [(r.document, r.kind, r.value, r.exists, r.outside) for r in refs]
    assert rows == [
        ("fp-lib-table", "library", "${KIPRJMOD}/Local.pretty", True, False),
        ("fp-lib-table", "library", f"{OLD}/Shared.pretty", False, True),
    ]


def test_a_copied_project_still_points_at_the_old_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "A copied project still points at the old folder"."""
    board = project(tmp_path, "copy")
    old = (tmp_path / "old").as_posix()
    (board.parent / "Shared.pretty").mkdir()
    (board.parent / "fp-lib-table").write_text(table(uri_outside=f"{old}/Shared.pretty"), encoding="utf-8")
    code, env, err, _ = run(monkeypatch, tmp_path, "refs", "copy")
    assert code == 0, err and "plan" not in env["result"]
    assert [i["code"] for i in env["issues"]] == ["refs.outside"]
    new = board.parent.as_posix()
    code, env, err, _ = run(monkeypatch, tmp_path, "refs", "copy", "--repoint", f"{old}={new}", "--confirm")
    assert code == 0, err and env["result"]["rewritten"] == ["fp-lib-table"]
    text = (board.parent / "fp-lib-table").read_text(encoding="utf-8")
    assert text == table(uri_outside=f"{new}/Shared.pretty")
    code, env, _, _ = run(monkeypatch, tmp_path, "refs", "copy")
    assert code == 0 and env["issues"] == []


def test_models_sheets_and_worksheet(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "b.kicad_pcb").write_text(
        '(kicad_pcb (version 20240108)\n  (footprint "R" (model "/lib/3d/r.step" (offset (xyz 0 0 0))))\n)\n',
        encoding="utf-8",
    )
    (root / "b.kicad_sch").write_text(
        "(kicad_sch (version 20231120)\n"
        '  (sheet (property "Sheetname" "s") (property "Sheetfile" "sub.kicad_sch"))\n)\n',
        encoding="utf-8",
    )
    (root / "sub.kicad_sch").write_text("(kicad_sch (version 20231120))\n", encoding="utf-8")
    (root / "b.kicad_pro").write_text(
        '{"pcbnew": {"page_layout_descr_file": "/lib/a.kicad_wks"}}\n', encoding="utf-8"
    )
    files = companions(root / "b.kicad_pcb")
    assert "sub.kicad_sch" in {rel.as_posix() for rel in files}
    kinds = {(r.kind, r.value) for r in project_refs(root, files)}
    assert kinds == {
        ("model", "/lib/3d/r.step"),
        ("sheet", "sub.kicad_sch"),
        ("worksheet", "/lib/a.kicad_wks"),
    }
    changed, kept = repoint(root, files, "/lib", "/new")
    assert kept == () and sorted(changed) == ["b.kicad_pcb", "b.kicad_pro"]
    assert b'(model "/new/3d/r.step"' in changed["b.kicad_pcb"]
    assert changed["b.kicad_pro"] == b'{"pcbnew": {"page_layout_descr_file": "/new/a.kicad_wks"}}\n'


def test_altium_project_is_not_rewritten(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "a"
    root.mkdir()
    (root / "a.PrjPcb").write_text("[Document1]\r\nDocumentPath=C:\\old\\a.SchDoc\r\n", encoding="utf-8")
    code, env, err, _ = run(
        monkeypatch, tmp_path, "refs", "a/a.PrjPcb", "--repoint", "C:\\old=C:\\new", "--dry-run"
    )
    assert code == 0, err
    assert (
        env["result"]["refs"][0]["value"] == "C:\\old\\a.SchDoc"
        and env["result"]["refs"][0]["writable"] is False
    )
    assert "refs.not-writable" in [i["code"] for i in env["issues"]] and "plan" not in env["result"]


def test_bad_repoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "refs", "proj", "--repoint", "nothing")
    assert code == 2 and err["code"] == "FEN-2001"
