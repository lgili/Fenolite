# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copy set of a project for a DRC run (capability kicad-oracle, "Check project copy set"; change
c0013). Projects are assembled in ``tmp_path``; nothing is run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _projects import STEM, authored_project, built_blink_project, hierarchy_project, tree_snapshot

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.projectset import (
    MAX_COPY_BYTES,
    SCHEMATIC_WORKSHEET_POINTER,
    SYMBOL_TABLE,
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


def test_state_folder_is_a_reserved_name(tmp_path: Path) -> None:
    """c0153: a row naming the runner's state folder is skipped like one naming its config folder."""
    root = authored_project(tmp_path, major=10, decoys=False)
    (root / ".fenolite-state" / "Z.pretty").mkdir(parents=True)
    _table(root, LibRow("Z", "KiCad", "${KIPRJMOD}/.fenolite-state/Z.pretty"))
    project = project_set(root)
    assert [(s.name, s.reason) for s in project.skipped] == [(".fenolite-state/Z.pretty", "reserved-name")]
    assert set(project.files) == CORE


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


# -- the schematic files of the set (change c0062)

SCHEMATICS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "schematic"
TRIAD = {"blink.kicad_pcb", "blink.kicad_pro", "blink.kicad_dru"}
BLINK_SET = TRIAD | {
    "blink.kicad_sch",
    "fp-lib-table",
    "sym-lib-table",
    "lib/Mini.pretty",
    "lib/Mini.kicad_sym",
    "lib/fenolite.kicad_sym",
}


def _built_blink(root: Path) -> Path:
    return built_blink_project(root, cache=False)


def _hierarchy(root: Path) -> Path:
    return hierarchy_project(root)


def test_schematic_files_included(tmp_path: Path) -> None:
    root = _built_blink(tmp_path / "blink")
    (root / "notes.txt").write_text("not a KiCad file\n", encoding="utf-8")
    (root / "blink.kicad_prl").write_text("{}\n", encoding="utf-8")
    before = tree_snapshot(root)
    project = project_set(root)
    assert set(project.files) == BLINK_SET and project.skipped == ()
    assert project.files["lib/Mini.kicad_sym"] == root / "lib" / "Mini.kicad_sym"
    assert tree_snapshot(root) == before


def test_schematic_sheet_files_of_a_hierarchy(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "hier")
    (root / "other.kicad_sch").write_bytes((SCHEMATICS / "flat.kicad_sch").read_bytes())
    project = project_set(root)
    assert {"top.kicad_sch", "child.kicad_sch"} <= set(project.files)
    assert "other.kicad_sch" not in project.files and project.skipped == ()
    assert list(project.files).index("top.kicad_sch") < list(project.files).index("child.kicad_sch")


def test_schematic_unreadable_root_is_included_alone(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "hier")
    (root / "top.kicad_sch").write_text("(", encoding="utf-8")
    project = project_set(root)
    assert [name for name in project.files if name.endswith(".kicad_sch")] == ["top.kicad_sch"]
    assert project.skipped == ()


def test_schematic_of_another_stem_is_left_out(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=True)
    (root / "other.kicad_sch").write_bytes((SCHEMATICS / "flat.kicad_sch").read_bytes())
    project = project_set(root)
    assert set(project.files) == CORE | {LIB}  # no schematic of the board's stem: no sheet, no symbol table


def test_schematic_sheet_outside_the_root_and_missing(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "p" / "hier")
    top = (root / "top.kicad_sch").read_text(encoding="utf-8")
    assert '"child.kicad_sch"' in top
    (root / "top.kicad_sch").write_text(
        top.replace('"child.kicad_sch"', '"../shared.kicad_sch"'), encoding="utf-8", newline="\n"
    )
    (root.parent / "shared.kicad_sch").write_bytes((SCHEMATICS / "flat.kicad_sch").read_bytes())
    project = project_set(root)
    assert [(s.name, s.reason) for s in project.skipped] == [("../shared.kicad_sch", "outside-root")]
    (root / "top.kicad_sch").write_text(
        top.replace('"child.kicad_sch"', '"gone.kicad_sch"'), encoding="utf-8", newline="\n"
    )
    project = project_set(root)
    assert [(s.name, s.reason) for s in project.skipped] == [("gone.kicad_sch", "missing")]
    assert "child.kicad_sch" not in project.files


def test_schematic_symbol_library_rows(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "hier")
    (root / "one.kicad_sym").write_text("(kicad_symbol_lib (version 20241209))\n", encoding="utf-8")
    (root / "many").mkdir()
    (root / "many" / "a.kicad_sym").write_text("(kicad_symbol_lib (version 20241209))\n", encoding="utf-8")
    rows = (
        LibRow("One", "KiCad", "${KIPRJMOD}/one.kicad_sym"),
        LibRow("Many", "KiCad", "${KIPRJMOD}/many"),
        LibRow("Gone", "KiCad", "${KIPRJMOD}/gone.kicad_sym"),
        LibRow("Var", "KiCad", "${KICAD10_SYMBOL_DIR}/Device.kicad_sym"),
        LibRow("Rel", "KiCad", "rel.kicad_sym"),
        LibRow("Out", "KiCad", "${KIPRJMOD}/../out.kicad_sym"),
        LibRow("Abs", "KiCad", "/abs/lib.kicad_sym"),
        LibRow("Nested", "Table", "${KIPRJMOD}/more-tables"),
        LibRow("Off", "KiCad", "${KIPRJMOD}/off.kicad_sym", disabled=True),
    )
    (root / "sym-lib-table").write_text(
        write_lib_table(LibTable("symbol", rows), target=10), encoding="utf-8"
    )
    project = project_set(root)
    assert {"sym-lib-table", "one.kicad_sym", "many"} <= set(project.files)
    assert [(s.name, s.reason) for s in project.skipped] == [
        ("gone.kicad_sym", "missing"),
        ("${KICAD10_SYMBOL_DIR}/Device.kicad_sym", "variable"),
        ("rel.kicad_sym", "relative"),
        ("${KIPRJMOD}/../out.kicad_sym", "outside-root"),
        ("${KIPRJMOD}/more-tables", "nested-table"),
    ]


def test_schematic_drawing_sheet(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "hier")
    (root / "sch.kicad_wks").write_text("(kicad_wks (version 20231118))\n", encoding="utf-8")
    data = {"schematic": {"page_layout_descr_file": "${KIPRJMOD}/sch.kicad_wks"}}
    (root / "top.kicad_pro").write_text(json.dumps(data), encoding="utf-8")
    assert "sch.kicad_wks" in project_set(root).files
    (root / "top.kicad_sch").unlink()
    assert "sch.kicad_wks" not in project_set(root).files  # only a schematic's own sheet is looked up
    assert SCHEMATIC_WORKSHEET_POINTER == "/schematic/page_layout_descr_file"
    assert SYMBOL_TABLE == "sym-lib-table"


def test_schematic_size_limit_keeps_the_root_and_the_tables(tmp_path: Path) -> None:
    root = _built_blink(tmp_path / "blink")
    always = TRIAD | {"blink.kicad_sch", "fp-lib-table", "sym-lib-table"}
    core = sum((root / name).stat().st_size for name in always)
    project = project_set(root, max_bytes=core + 10)
    assert set(project.files) == always
    assert [(s.name, s.reason) for s in project.skipped] == [
        ("lib/Mini.pretty", "too-large"),
        ("lib/Mini.kicad_sym", "too-large"),
        ("lib/fenolite.kicad_sym", "too-large"),
    ]


def test_schematic_child_too_large_is_skipped_before_the_libraries(tmp_path: Path) -> None:
    root = _hierarchy(tmp_path / "hier")
    always = sum((root / n).stat().st_size for n in ("top.kicad_pcb", "top.kicad_pro", "top.kicad_sch"))
    project = project_set(root, max_bytes=always + 10)
    assert [(s.name, s.reason) for s in project.skipped] == [("child.kicad_sch", "too-large")]
