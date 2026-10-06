# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project keys for the drawing sheet and text variables (capability kicad-file-backend, "Projects carry
the drawing sheet and text variables", and the MODIFIED project requirements; change c0012)."""

from __future__ import annotations

import dataclasses
import json

import pytest

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.errors import ConsistencyError, Issue
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef, TitleBlock


def design(sheet: SheetFrameRef | None = None, block: TitleBlock | None = None) -> Design:
    base = Design.new("b", seed=21)
    assert base.board is not None
    board = dataclasses.replace(base.board, layers=created_layers(2), sheet=sheet, title_block=block)
    return dataclasses.replace(base, board=board)


def read_back(files: dict[str, str]) -> tuple[Design, pro.ProjectInfo]:
    info = pro.read_project(files["b.kicad_pro"])
    return pro.apply_project(read_board(files["b.kicad_pcb"]), info), info


def test_nothing_to_set() -> None:
    files = write_triad(design(), name="b", target=10)
    assert files["b.kicad_pro"] == pro.synthesize_project(design(), target=10, board_name="b")
    text = pro.write_project_text(pro.template(10))
    assert pro.apply_sheet_keys(text, design()) is text


def test_both_keys_written_and_read_back() -> None:
    sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")
    block = TitleBlock(title="Bench", params={"LOT": "7"})
    files = write_triad(design(sheet, block), name="b", target=10)
    data = json.loads(files["b.kicad_pro"])
    assert data["pcbnew"]["page_layout_descr_file"] == "frame.kicad_wks"
    assert data["text_variables"] == {"LOT": "7"}
    back, info = read_back(files)
    assert (info.drawing_sheet, info.text_variables) == ("frame.kicad_wks", (("LOT", "7"),))
    assert back.board is not None
    assert (back.board.sheet, back.board.title_block) == (sheet, block)


def test_default_presentation_reads_back_in_normal_form() -> None:
    files = write_triad(design(None, TitleBlock()), name="b", target=10)
    back, _ = read_back(files)
    assert back.board is not None
    assert back.board.sheet == SheetFrameRef("A4") and back.board.title_block is None


def test_existing_variables_kept() -> None:
    data = pro.template(10)
    data["text_variables"] = {"ZZ": "1", "LOT": "6"}
    existing = pro.write_project_text(data)
    files = write_triad(
        design(None, TitleBlock(params={"LOT": "7", "AA": "2"})),
        name="b",
        target=10,
        existing_project=existing,
    )
    assert list(json.loads(files["b.kicad_pro"])["text_variables"].items()) == [
        ("ZZ", "1"),
        ("LOT", "7"),
        ("AA", "2"),
    ]


def test_reserved_variable_refused() -> None:
    reserved = design(None, TitleBlock(params={"TITLE": "x"}))
    with pytest.raises(LossyWriteError) as info:
        write_triad(reserved, name="b", target=10)
    assert [i.code for i in info.value.issues] == ["kicad.project.reserved-variable"]
    assert info.value.droppable is True
    issues: list[Issue] = []
    files = write_triad(reserved, name="b", target=10, allow_lossy=True, issues=issues)
    assert "TITLE" not in json.loads(files["b.kicad_pro"]).get("text_variables", {})
    assert "kicad.project.dropped-variable" in [i.code for i in issues]


def test_schematic_key_untouched() -> None:
    files = write_triad(
        design(SheetFrameRef("A4", drawing_sheet="${KIPRJMOD}/f.kicad_wks")), name="b", target=10
    )
    data = json.loads(files["b.kicad_pro"])
    template = pro.template(10)
    assert data["schematic"] == json.loads(pro.write_project_text(template))["schematic"]
    assert data["pcbnew"]["page_layout_descr_file"] == "${KIPRJMOD}/f.kicad_wks"


def test_schematic_key_with_a_schematic() -> None:
    """c0074: a build that writes a schematic names the drawing sheet for it too (``H-K-PRO-WKS-SCH``)."""
    made = design(SheetFrameRef("A4", drawing_sheet="blink.kicad_wks"))
    template = pro.write_project_text(pro.template(10))
    both = json.loads(pro.apply_sheet_keys(template, made, schematic=True))
    board_only = json.loads(pro.apply_sheet_keys(template, made, schematic=False))
    assert both["pcbnew"]["page_layout_descr_file"] == "blink.kicad_wks"
    assert both["schematic"]["page_layout_descr_file"] == "blink.kicad_wks"
    assert board_only["pcbnew"]["page_layout_descr_file"] == "blink.kicad_wks"
    assert board_only["schematic"] == json.loads(template)["schematic"]
    rest = {k: v for k, v in both["schematic"].items() if k != "page_layout_descr_file"}
    assert rest == {
        k: v for k, v in json.loads(template)["schematic"].items() if k != "page_layout_descr_file"
    }
    # without a drawing sheet nothing is set, with or without a schematic
    assert pro.apply_sheet_keys(template, design(), schematic=True) == template


def test_unsafe_sheet_path_refused_before_any_write() -> None:
    with pytest.raises(ConsistencyError, match="model.sheet-path"):
        write_triad(design(SheetFrameRef("A4", drawing_sheet="/abs/f.kicad_wks")), name="b", target=10)


def test_unread_variable_is_an_info() -> None:
    data = pro.template(10)
    data["text_variables"] = {"N": pro.read_project_text('{"x": 3}')["x"], "OK": "1"}
    issues: list[Issue] = []
    info = pro.read_project(pro.write_project_text(data), issues=issues)
    assert info.text_variables == (("OK", "1"),)
    assert [i.code for i in issues] == ["kicad.project.unread-variable"]


def test_apply_without_board_sheet_keeps_none() -> None:
    data = pro.template(10)
    data["pcbnew"]["page_layout_descr_file"] = "frame.kicad_wks"  # type: ignore[index]
    info = pro.read_project(pro.write_project_text(data))
    applied = pro.apply_project(design(), info)
    assert applied.board is not None and applied.board.sheet is None and applied.board.title_block is None


def test_constants() -> None:
    assert pro.PAGE_LAYOUT_POINTER == "/pcbnew/page_layout_descr_file"
    assert pro.SHEET_KEY_PATHS == frozenset({"/text_variables/*"})
