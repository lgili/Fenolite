# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A triad whose project names the drawing sheet draws it without ``--drawing-sheet`` (capability
kicad-oracle, "One drawing sheet serves several sizes on both majors", scenario "Project key draws the
sheet"; ``H-K-PRO-WKS``; change c0012)."""

from __future__ import annotations

import dataclasses

import _acceptance as acc
import _expected as ex
import _sheetcases as sc
import pytest
from _sheet_bench import classify, export_sheet_svg

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.wks import read_drawing_sheet, write_drawing_sheet
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef
from fenolite.templates import build_sheet, example_path, load_spec

pytestmark = pytest.mark.needs_kicad
PARAMETER = ("LOT_NO", "42")


def frame_sheet() -> str:
    """The ISO example with the identification-number cell showing a project parameter instead."""
    source = example_path("iso5457_generic").read_text(encoding="utf-8")
    spec = load_spec(source.replace('token = "doc_id"', f'token = "param:{PARAMETER[0]}"'))
    return write_drawing_sheet(build_sheet(spec), target=sc.running_major()).text


def test_project_key_draws_the_sheet() -> None:
    design = Design.new("board", seed=31)
    assert design.board is not None
    block = dataclasses.replace(ex.TITLE, params=dict([PARAMETER]))
    board = dataclasses.replace(
        design.board, layers=created_layers(2), sheet=SheetFrameRef("A3", drawing_sheet="frame.kicad_wks"),
        title_block=block,
    )  # fmt: skip
    files = write_triad(dataclasses.replace(design, board=board), name="board", target=sc.running_major())
    sheet_text = frame_sheet()
    extra = {"board.kicad_pro": files["board.kicad_pro"].encode(), "frame.kicad_wks": sheet_text.encode()}
    case = export_sheet_svg(files["board.kicad_pcb"], None, files=extra)
    default = sc.default(text=files["board.kicad_pcb"])
    control = sc.control(text=files["board.kicad_pcb"])
    assert classify(case, default=default, control=control) == "load"
    assert case.svg is not None
    texts, lines = acc.prediction(read_drawing_sheet(sheet_text), case.svg, paper="A3", block=block)
    assert acc.problems_for("A3", case.svg, texts, lines) == []
    assert ex.TITLE.title in case.strings() and PARAMETER[1] in case.strings()
