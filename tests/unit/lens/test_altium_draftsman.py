# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed-gate build integration and candidate drawing layout, without a native acceptance claim."""

from __future__ import annotations

from dataclasses import replace

import pytest
from _altium_job import blink_output

from fenolite.backends.altium import draftsman
from fenolite.backends.altium.read.draftsman import read_draftsman
from fenolite.backends.altium.read.outjob import read_outjob
from fenolite.backends.altium.read.project import read_project
from fenolite.exports.drawing_spec import DEFAULT
from fenolite.lens.altium_draftsman import draftsman_spec


def test_gate_off_keeps_all_file_bytes() -> None:
    off = blink_output(outjob=True)
    requested = blink_output(outjob=True, draftsman=True)
    assert off.files == requested.files
    assert requested.summary["draftsman"] is None
    assert any(i.code == "altium.draftsman-not-written" and "gate" in i.message for i in requested.issues)


def test_document_project_parameters_and_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(draftsman, "NATIVE_WRITE", True)
    built = blink_output(framed=True, outjob=True, draftsman=True)
    assert not [i for i in built.issues if i.severity == "error"], built.issues
    assert "blink.PCBDwf" in built.files and built.summary["draftsman"] is not None
    scope = draftsman.written_scope(read_draftsman(built.files["blink.PCBDwf"]).root)
    assert len(scope.sheets) == 3
    project = read_project(built.files["blink.PrjPcb"])
    paths = [document.path for document in project.documents]
    assert paths.index("blink.PCBDwf") == paths.index("blink.OutJob") + 1
    text = built.files["blink.PrjPcb"].decode("ascii")
    assert "[Parameter1]\r\nName=Title\r\nValue=Blink" in text
    assert "Name=Revision\r\nValue=B" in text
    job = read_outjob(built.files["blink.OutJob"])
    assert len(job.groups[0].outputs) == 7
    drawing = job.groups[0].outputs[-1]
    assert (drawing.type, drawing.category, drawing.document_path, drawing.enabled_media) == (
        "PCBDrawing",
        "Documentation",
        "blink.PCBDwf",
        (2,),
    )


def test_fab_notes_and_nonoverlapping_candidate_objects() -> None:
    model = blink_output().layout
    assert model is not None
    spec = replace(DEFAULT, fab=replace(DEFAULT.fab, notes=("First authored note", "Second authored note")))
    document, issues = draftsman_spec(model, spec)
    fab = document.sheets[0]
    (note,) = (item for item in fab.items if item.kind == "Note")
    assert note.texts == spec.fab.notes
    assert any(item.kind == "DrillViewView" for item in fab.items)
    assert any(item.kind == "DrillTableBoardView" for item in fab.items)
    assert any(item.name == "board" and item.kind == "Text" for item in fab.items)
    boxes = [(*i.at, i.at[0] + i.size[0], i.at[1] + i.size[1]) for i in fab.items]
    for index, a in enumerate(boxes):
        assert a[0] >= 0 and a[1] >= 0 and a[2] <= fab.size[0] and a[3] <= fab.size[1]
        for b in boxes[index + 1 :]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    assert any("native board Table" in i.message for i in issues)


def test_assembly_side_selection_and_kept_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(draftsman, "NATIVE_WRITE", True)
    base = blink_output()
    assert base.layout is not None and base.layout.board is not None
    board = replace(
        base.layout.board, footprints=tuple(replace(fp, side="top") for fp in base.layout.board.footprints)
    )
    drawing, _ = draftsman_spec(replace(base.layout, board=board))
    assert [s.name for s in drawing.sheets] == ["fab", "assembly-top"]
    kept = blink_output(outjob=True, draftsman=True, project_exists=True, project_listed=frozenset())
    assert "blink.PrjPcb" not in kept.files
    assert any(i.code == "altium.draftsman-not-listed" for i in kept.issues)
    rebuilt = blink_output(
        outjob=True, draftsman=True, project_exists=True, project_listed=frozenset(), project_digest="f" * 64
    )
    assert "blink.PrjPcb" in rebuilt.files
    assert not any(i.code == "altium.draftsman-not-listed" for i in rebuilt.issues)


def test_packing_starts_no_external_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    model = blink_output().layout
    assert model is not None

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("drawing preparation must be pure")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    drawing, _ = draftsman_spec(model)
    assert drawing.sheets
