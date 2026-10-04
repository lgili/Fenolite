# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copy set of a project for a DRC run (capability kicad-oracle, "Check project copy set"; change
c0013). Projects are assembled in ``tmp_path``; nothing is run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _projects import STEM, authored_project, tree_snapshot

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.projectset import (
    MAX_COPY_BYTES,
    WORKSHEET_POINTER,
    ProjectNotFoundError,
    ProjectResolutionError,
    project_set,
    resolve_board,
)

LIB = "libs/Mini.pretty"
CORE = {f"{STEM}.kicad_pcb", f"{STEM}.kicad_pro", f"{STEM}.kicad_dru", "fp-lib-table"}


def _table(root: Path, *rows: LibRow) -> None:
    (root / "fp-lib-table").write_text(
        write_lib_table(LibTable("footprint", rows), target=10), encoding="utf-8"
    )


def test_closed_include_list(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=True)
    before = tree_snapshot(root)
    project = project_set(root)
    assert set(project.files) == CORE | {LIB}
    assert project.skipped == ()
    assert project.board == f"{STEM}.kicad_pcb"
    assert project.root == root
    assert project.has_project and project.has_rules
    assert project.files[LIB] == root / LIB
    assert tree_snapshot(root) == before


def test_include_list_without_project_or_rules(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=9, project=False, rules=None, decoys=False)
    project = project_set(root / f"{STEM}.kicad_pcb")
    assert set(project.files) == {f"{STEM}.kicad_pcb", "fp-lib-table", "libs/Mini_v9.pretty"}
    assert not project.has_project and not project.has_rules


def test_skipped_rows(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    (root / "config" / "Y.pretty").mkdir(parents=True)
    (tmp_path / "Other.pretty").mkdir()
    _table(
        root,
        LibRow("Other", "KiCad", "${KIPRJMOD}/../Other.pretty"),
        LibRow("X", "KiCad", "${MYLIBS}/X.pretty"),
        LibRow("Rel", "KiCad", "Rel.pretty"),
        LibRow("Y", "KiCad", "${KIPRJMOD}/config/Y.pretty"),
        LibRow("Nested", "Table", "${KIPRJMOD}/nested-table"),
        LibRow("Gone", "KiCad", "${KIPRJMOD}/libs/Gone.pretty"),
        LibRow("Off", "KiCad", "${KIPRJMOD}/libs/Off.pretty", disabled=True),
        LibRow("Abs", "KiCad", "/opt/kicad/Abs.pretty"),
    )
    project = project_set(root)
    reasons = {s.reason for s in project.skipped}
    assert reasons == {"outside-root", "variable", "relative", "reserved-name", "nested-table", "missing"}
    assert set(project.files) == CORE
    assert [s.name for s in project.skipped if s.reason == "reserved-name"] == ["config/Y.pretty"]
    assert [s.name for s in project.skipped if s.reason == "missing"] == ["libs/Gone.pretty"]


def test_size_limit(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    core = sum((root / name).stat().st_size for name in CORE)
    project = project_set(root, max_bytes=core + 10)
    assert [(s.name, s.reason) for s in project.skipped] == [(LIB, "too-large")]
    assert set(project.files) == CORE
    assert MAX_COPY_BYTES == 256 * 2**20


def test_drawing_sheet(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    data = json.loads((root / f"{STEM}.kicad_pro").read_text(encoding="utf-8"))
    data.setdefault("pcbnew", {})["page_layout_descr_file"] = "${KIPRJMOD}/frame.kicad_wks"
    (root / f"{STEM}.kicad_pro").write_text(json.dumps(data), encoding="utf-8")
    (root / "frame.kicad_wks").write_text("(kicad_wks (version 20231118))\n", encoding="utf-8")
    assert "frame.kicad_wks" in project_set(root).files
    data["pcbnew"]["page_layout_descr_file"] = "config/frame.kicad_wks"
    (root / f"{STEM}.kicad_pro").write_text(json.dumps(data), encoding="utf-8")
    assert [(s.name, s.reason) for s in project_set(root).skipped] == [
        ("config/frame.kicad_wks", "reserved-name")
    ]
    data["pcbnew"]["page_layout_descr_file"] = "/abs/frame.kicad_wks"
    (root / f"{STEM}.kicad_pro").write_text(json.dumps(data), encoding="utf-8")
    project = project_set(root)
    assert project.skipped == () and set(project.files) == CORE | {LIB}


def test_unreadable_project_is_still_copied(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    (root / f"{STEM}.kicad_pro").write_text("{not json", encoding="utf-8")
    project = project_set(root)
    assert f"{STEM}.kicad_pro" in project.files and project.has_project


def test_ambiguous_folder(tmp_path: Path) -> None:
    for name in ("a.kicad_pcb", "b.kicad_pcb"):
        (tmp_path / name).write_text("(kicad_pcb)\n", encoding="utf-8")
    with pytest.raises(ProjectResolutionError) as info:
        resolve_board(tmp_path)
    assert info.value.cli_code == "FEN-2001"
    assert info.value.candidates == ("a.kicad_pcb", "b.kicad_pcb")


def test_board_resolution(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    board = root / f"{STEM}.kicad_pcb"
    assert resolve_board(root) == board
    assert resolve_board(root / f"{STEM}.kicad_pro") == board
    assert resolve_board(board) == board
    (root / "other.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    assert resolve_board(root) == board  # the only project file decides
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ProjectResolutionError) as info:
        resolve_board(empty)
    assert info.value.candidates == ()
    with pytest.raises(ProjectNotFoundError) as missing:
        resolve_board(tmp_path / "nowhere")
    assert missing.value.cli_code == "FEN-3001"
    board.unlink()
    with pytest.raises(ProjectNotFoundError):
        resolve_board(root / f"{STEM}.kicad_pro")


def test_worksheet_pointer_matches_pro() -> None:
    assert pro.PAGE_LAYOUT_POINTER == WORKSHEET_POINTER
