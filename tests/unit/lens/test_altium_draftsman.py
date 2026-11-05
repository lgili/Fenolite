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


def test_fab_sheet_of_the_routed_blink() -> None:
    """Scenario "Fabrication sheet of the routed blink" (c0388 task 4.2), native items behind the gate."""
    from fenolite.model.board import StackLayer, Stackup

    base = blink_output().layout
    assert base is not None and base.board is not None
    layers = (
        StackLayer(id="sly_top", name="F.Cu", kind="copper", thickness=35_000),
        StackLayer(id="sly_core", name="core", kind="dielectric", thickness=1_530_000, material="FR4"),
        StackLayer(id="sly_bottom", name="B.Cu", kind="copper", thickness=35_000),
    )
    model = replace(base, board=replace(base.board, stackup=Stackup(id="stk_blink", layers=layers)))
    spec = replace(DEFAULT, fab=replace(DEFAULT.fab, notes=("First authored note", "Second authored note")))
    document, issues = draftsman_spec(model, spec)
    fab = document.sheets[0]
    kinds = [item.kind for item in fab.items]
    assert fab.title == "Fabrication drawing"
    for kind in ("DrillViewView", "DrillTableBoardView", "LayerStackLegendView", "Note"):
        assert kinds.count(kind) == 1, kind
    assert [item.name for item in fab.items if item.name == "board"] == ["board"]
    (note,) = (item for item in fab.items if item.kind == "Note")
    assert len(note.texts) == 2
    width, height = (item for item in fab.items if item.kind == "LinearDimension")
    assert width.dimension is not None and height.dimension is not None
    assert width.dimension.target == height.dimension.target == "view"
    assert width.dimension.end[0] - width.dimension.start[0] == fab.items[0].size[0]
    assert height.dimension.end[1] - height.dimension.start[1] == fab.items[0].size[1]
    boxes = [(*i.at, i.at[0] + i.size[0], i.at[1] + i.size[1]) for i in fab.items]
    for index, a in enumerate(boxes):
        assert a[0] >= 0 and a[1] >= 0 and a[2] <= fab.size[0] and a[3] <= fab.size[1]
        for b in boxes[index + 1 :]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    # The writer accepts every item, and the dimension snaps name the view it measures.
    root = read_draftsman(draftsman.write_draftsman(document)).root
    scope = draftsman.written_scope(root)
    assert [item.kind for item in scope.sheets[0].items] == kinds
    assert any("dimension snaps" in i.message for i in issues)


def test_fab_dimensions_follow_the_drawing_specification() -> None:
    model = blink_output().layout
    assert model is not None
    off = replace(DEFAULT, fab=replace(DEFAULT.fab, dimensions=False))
    document, _ = draftsman_spec(model, off)
    assert not any(item.kind == "LinearDimension" for sheet in document.sheets for item in sheet.items)
    document, _ = draftsman_spec(model)
    assert all(item.kind != "LinearDimension" for item in document.sheets[1].items)


def test_no_part_on_the_bottom_gives_a_top_assembly_sheet_with_its_bom() -> None:
    base = blink_output()
    assert base.layout is not None and base.layout.board is not None
    board = replace(
        base.layout.board, footprints=tuple(replace(fp, side="top") for fp in base.layout.board.footprints)
    )
    document, _ = draftsman_spec(replace(base.layout, board=board))
    assert len(document.sheets) == 2
    top = document.sheets[1]
    assert [
        (i.kind, i.side) for i in top.items if i.kind in ("BoardAssemblyViewData", "BillOfMaterialsView")
    ] == [
        ("BoardAssemblyViewData", "Top"),
        ("BillOfMaterialsView", "Top"),
    ]
