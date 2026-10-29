# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The allow-list of the viewer's run routes (capability board-viewer, "Allowed run commands"; c0245)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.view.project import Document, ProjectTree, load_tree
from fenolite.view.runs import Choices, RunRefused, RunRequest, offered, request

BOARD = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
CHOICES = Choices(
    stages=("drc.kicad", "copper.clearance", "model.validate"),
    default_stages=("copper.clearance",),
    document_stages=("model.validate", "parity"),
    kinds=("clearance", "creepage", "connectivity"),
    levels=(1, 2, 3),
    frames=("absolute", "relative"),
)


@pytest.fixture
def tree(tmp_path: Path) -> ProjectTree:
    shutil.copy(BOARD, tmp_path / BOARD.name)
    (tmp_path / "other.kicad_pcb").write_bytes(BOARD.read_bytes())
    return load_tree(tmp_path)


def _doc(tree: ProjectTree, name: str) -> str:
    found = tree.document(name)
    assert found is not None
    return found.id


def test_check_with_drc_on_the_board_is_accepted(tree: ProjectTree) -> None:
    body = {"command": "check", "doc": _doc(tree, BOARD.name), "options": {"stages": ["drc.kicad"]}}
    found = request(body, tree, CHOICES)
    assert isinstance(found, RunRequest)
    assert found.command == "check"
    assert found.arguments == {"path": BOARD.name, "stages": "drc.kicad"}


def test_each_row_of_the_table_is_accepted(tree: ProjectTree) -> None:
    board, other = _doc(tree, BOARD.name), _doc(tree, "other.kicad_pcb")
    analyze = request(
        {"command": "analyze", "doc": board, "options": {"kinds": ["clearance"]}}, tree, CHOICES
    )
    ready = request({"command": "ready", "doc": board, "options": {"no_kicad": True}}, tree, CHOICES)
    same = request(
        {"command": "equivalent", "doc": board, "options": {"b": other, "level": 2, "frame": "relative"}},
        tree,
        CHOICES,
    )
    assert isinstance(analyze, RunRequest) and analyze.arguments["kinds"] == "clearance"
    assert isinstance(ready, RunRequest) and ready.arguments == {"path": BOARD.name, "no_kicad": True}
    assert isinstance(same, RunRequest)
    assert same.arguments == {"a": BOARD.name, "b": "other.kicad_pcb", "level": 2, "frame": "relative"}


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"command": "tidy", "options": {}}, "not a command the page may run"),
        ({"command": "check", "options": {"exclude": "kicad.drc.x:R1:R2"}}, "no option 'exclude'"),
        ({"command": "check", "options": {"reason": "ok"}}, "no option 'reason'"),
        ({"command": "check", "options": {"kicad_cli": "/bin/sh"}}, "no option 'kicad_cli'"),
        ({"command": "analyze", "options": {"kinds": ["power"]}}, "'power' is not one of"),
        ({"command": "check", "options": {"stages": ["../../etc/passwd"]}}, "is not one of"),
        ({"command": "analyze", "options": {"requirements": "/etc/passwd"}}, "no option 'requirements'"),
        ({"command": "check", "argv": ["--exclude"]}, "takes no 'argv'"),
        ({"command": "equivalent", "options": {"b": "/etc/passwd"}}, "holds no document"),
        ({"command": "equivalent", "options": {"level": True, "b": "doc1"}}, "level: one of"),
        ({"command": "ready", "options": {"no_kicad": "yes"}}, "true or false"),
    ],
)
def test_refused_requests(tree: ProjectTree, body: dict[str, object], reason: str) -> None:
    found = request({"doc": _doc(tree, BOARD.name), **body}, tree, CHOICES)
    assert isinstance(found, RunRefused)
    assert reason in found.reason


def test_documents_missing_or_outside_are_refused(tmp_path: Path) -> None:
    board = tmp_path / "in" / BOARD.name
    board.parent.mkdir()
    shutil.copy(BOARD, board)
    outside = tmp_path / "outside.kicad_pcb"
    outside.write_bytes(BOARD.read_bytes())
    link = board.parent / "link.kicad_pcb"
    link.symlink_to(outside)
    docs = (
        Document("doc1", board.name, board.name, "pcb", "Source Documents", True, True, 1, board),
        Document(
            "doc2", "gone.kicad_pcb", "gone.kicad_pcb", "pcb", "Source Documents", False, True, None, None
        ),
        Document("doc3", "link.kicad_pcb", "link.kicad_pcb", "pcb", "Source Documents", True, True, 1, link),
    )
    tree = ProjectTree("in", "folder", board.parent, "", docs)
    for doc in ("doc2", "doc3", "doc9", 7):
        found = request({"command": "check", "doc": doc}, tree, CHOICES)
        assert isinstance(found, RunRefused), doc
    assert isinstance(request({"command": "check", "doc": "doc1"}, tree, CHOICES), RunRequest)


def test_offered_lists_the_options() -> None:
    offer = offered(CHOICES)
    assert sorted(offer) == ["analyze", "check", "equivalent", "ready"]
    assert offer["check"]["options"]["stages"]["choices"] == list(CHOICES.stages)
