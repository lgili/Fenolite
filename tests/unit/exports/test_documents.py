# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What is checked before a document is written (capability manufacturing-exports, "Board PDF export page
check" and "Schematic PDF export sheets"; change c0116). Hermetic: no tool runs."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import board, uid
from _fakecli import calls, fake_kicad_cli
from _projects import hierarchy_project

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.exports import documents
from fenolite.exports.plan import run_kind
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef

MM = 1_000_000


def _rect(x0: int, y0: int, x1: int, y1: int) -> str:
    return (
        f"(gr_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.05) (type solid)) (fill no)"
        f' (layer "Edge.Cuts") (uuid "{uid(900)}"))'
    )


def _design(tmp_path: Path, *items: str) -> Design:
    path = tmp_path / "page.kicad_pcb"
    path.write_text(board(*items), encoding="utf-8")
    return read_board(path)


def _on(design: Design, sheet: SheetFrameRef) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, sheet=sheet))


# --- page -------------------------------------------------------------------------------------------


def test_page_board_past_its_paper(tmp_path: Path) -> None:
    design = _design(tmp_path, _rect(100, 100, 258, 279))
    assert documents.page_size(design) == (297 * MM, 210 * MM)
    found = documents.page_check(design)
    assert found is not None
    assert (found.code, found.severity, found.where) == ("export.page-too-small", "warning", "pdf")
    assert "158 × 179 mm" in found.message and "297 × 210 mm" in found.message
    assert "A4" in found.hint


def test_page_board_on_its_paper(tmp_path: Path) -> None:
    assert documents.page_check(_design(tmp_path, _rect(100, 100, 176, 192))) is None


def test_page_portrait_and_custom_papers(tmp_path: Path) -> None:
    design = _design(tmp_path, _rect(100, 100, 176, 250))
    assert documents.page_check(design) is not None  # 250 mm down a landscape A4 of 210 mm
    portrait = _on(design, SheetFrameRef(paper="A4", portrait=True))
    assert documents.page_size(portrait) == (210 * MM, 297 * MM)
    assert documents.page_check(portrait) is None
    custom = _on(design, SheetFrameRef(paper="custom", width=150 * MM, height=300 * MM))
    found = documents.page_check(custom)
    assert found is not None and "150 × 300 mm" in found.message and "custom" in found.hint
    assert documents.page_check(_on(design, SheetFrameRef(paper="custom"))) is None  # no size is known


def test_page_board_left_of_the_origin(tmp_path: Path) -> None:
    found = documents.page_check(_design(tmp_path, _rect(-10, 10, 50, 60)))
    assert found is not None and "(-10, 10) mm" in found.message


def test_page_without_a_closed_outline_gives_no_warning(tmp_path: Path) -> None:
    design = _design(tmp_path)
    assert documents.page_check(design) is None
    assert documents.page_check(dataclasses.replace(design, board=None)) is None


def test_page_warning_does_not_hold_the_files_back(tmp_path: Path) -> None:
    path = tmp_path / "page.kicad_pcb"
    path.write_text(board(_rect(100, 100, 258, 279)), encoding="utf-8")
    script = fake_kicad_cli(tmp_path / "bin")
    result = run_kind(KicadCli(script), "pdf", path, {}, major=10, design=read_board(path))
    assert [i.code for i in result.issues] == ["export.page-too-small"]
    assert [a.path for a in result.artifacts] == ["pdf/page-Edge_Cuts.pdf", "pdf/page-F_Cu.pdf"]


# --- sheets -----------------------------------------------------------------------------------------


def test_sch_pdf_files_are_those_of_the_copy_set(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    found = documents.schematic_files(root / "b.kicad_pcb")
    assert found.root == "b.kicad_sch" and found.files == ("b.kicad_sch", "child.kicad_sch")
    assert found.issues == ()
    assert set(found.files) <= set(project_set(root / "b.kicad_pcb").files)


def test_sch_pdf_missing_sheet_is_refused_once(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    (root / "child.kicad_sch").unlink()
    found = documents.schematic_files(root / "b.kicad_pcb")
    assert found.files == ("b.kicad_sch",)
    (refusal,) = found.issues
    assert (refusal.code, refusal.severity, refusal.where) == (
        "export.sheet-missing",
        "error",
        "child.kicad_sch",
    )
    assert "does not exist" in refusal.message


def test_sch_pdf_sheet_outside_the_folder_is_refused(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    text = (root / "b.kicad_sch").read_text(encoding="utf-8")
    assert '"child.kicad_sch"' in text
    (root / "b.kicad_sch").write_text(
        text.replace('"child.kicad_sch"', '"../child.kicad_sch"'), encoding="utf-8"
    )
    (root / "child.kicad_sch").rename(tmp_path / "child.kicad_sch")
    (refusal,) = documents.schematic_files(root / "b.kicad_pcb").issues
    assert refusal.code == "export.sheet-missing" and refusal.where == "../child.kicad_sch"
    assert "outside" in refusal.message


def test_sch_pdf_too_large_sheet_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    board_file = root / "b.kicad_pcb"
    limit = sum((root / name).stat().st_size for name in ("b.kicad_pcb", "b.kicad_pro", "b.kicad_sch")) + 1
    small = project_set(board_file, max_bytes=limit)
    assert [(s.name, s.reason) for s in small.skipped] == [("child.kicad_sch", "too-large")]
    monkeypatch.setattr(documents, "project_set", lambda board: small)
    (refusal,) = documents.schematic_files(board_file).issues
    assert refusal.where == "child.kicad_sch" and "too large" in refusal.message
    script = fake_kicad_cli(tmp_path / "bin")
    assert run_kind(KicadCli(script), "sch-pdf", board_file, {}, major=10).artifacts == ()
    assert calls(script) == []


def test_sch_pdf_without_a_schematic_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "lone.kicad_pcb"
    path.write_text(board(), encoding="utf-8")
    found = documents.schematic_files(path)
    assert [(i.code, i.where) for i in found.issues] == [("export.sheet-missing", "lone.kicad_sch")]
