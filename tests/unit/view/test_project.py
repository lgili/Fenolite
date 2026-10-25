# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tree of a project's documents (capability board-viewer, "Project tree")."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.view.project import GROUPS, load_tree

ROOT = Path(__file__).resolve().parents[3]
ALTIUM = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
KICAD = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t9" / "blink.kicad_pro"
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
HIER = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.PrjPcb"


def _groups(tree_json: dict[str, object]) -> dict[str, list[tuple[str, str, bool]]]:
    out: dict[str, list[tuple[str, str, bool]]] = {}
    for group in tree_json["groups"]:  # type: ignore[union-attr]
        out[group["name"]] = [(d["name"], d["kind"], d["viewable"]) for d in group["documents"]]  # type: ignore[index]
    return out


def test_altium_project() -> None:
    """Scenario "An Altium project"."""
    tree = load_tree(ALTIUM)
    groups = _groups(tree.to_json())
    assert tree.source == "altium" and tree.project_file == "blink.PrjPcb"
    assert ("blink.PcbDoc", "pcb", True) in groups["Source Documents"]
    assert ("blink.SchDoc", "schematic", True) in groups["Source Documents"]
    assert {name for name, _, _ in groups["Libraries"]} == {"blink.PcbLib", "blink.SchLib"}
    assert list(groups) == [g for g in GROUPS if g in groups]
    first = tree.first_viewable()
    assert first is not None and first.name == "blink.PcbDoc"


def test_schematic_documents() -> None:
    """Scenario "An Altium project with sheets" (c0177)."""
    tree = load_tree(HIER)
    sheets = [doc for doc in tree.documents if doc.kind == "schematic"]
    assert len(sheets) == 3 and all(doc.viewable for doc in sheets)
    first = tree.first_viewable()
    assert first is not None and first.kind == "schematic"
    blink = load_tree(ALTIUM)
    first = blink.first_viewable()
    assert first is not None and first.kind == "pcb"
    lone = load_tree(HIER.parent / "altium_hier.SchDoc")
    assert lone.source == "sheet" and [d.viewable for d in lone.documents] == [True]


def test_kicad_project() -> None:
    tree = load_tree(KICAD)
    groups = _groups(tree.to_json())
    assert tree.source == "kicad"
    assert ("blink.kicad_pcb", "pcb", True) in groups["Source Documents"]
    assert any(kind == "pcb-library" for _, kind, _ in groups["Libraries"])
    assert any(kind == "library-table" for _, kind, _ in groups["Settings"])


def test_folder_and_board(tmp_path: Path) -> None:
    assert load_tree(ALTIUM.parent).source == "altium"
    shutil.copy(BOARD, tmp_path / "a.kicad_pcb")
    shutil.copy(BOARD, tmp_path / "b.kicad_pcb")
    folder = load_tree(tmp_path)
    assert folder.source == "folder" and [d.name for d in folder.documents] == ["a.kicad_pcb", "b.kicad_pcb"]
    single = load_tree(BOARD)
    assert single.source == "board" and single.documents[0].viewable and single.document("doc1") is not None


def test_outside_paths_are_never_opened(tmp_path: Path) -> None:
    project = tmp_path / "p.PrjPcb"
    project.write_text(
        "[Design]\nVersion=1.0\n\n[Document1]\nDocumentPath=..\\outside.PcbDoc\n", encoding="utf-8"
    )
    tree = load_tree(project)
    (doc,) = tree.documents
    assert doc.present is False and doc.file is None


def test_refusals(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tree(tmp_path / "missing.PrjPcb")
    (tmp_path / "x.SchLib").write_bytes(b"")
    with pytest.raises(ValueError, match="schematic-library document"):
        load_tree(tmp_path / "x.SchLib")
    (tmp_path / "x.txt").write_bytes(b"")
    with pytest.raises(ValueError, match="neither"):
        load_tree(tmp_path / "x.txt")
