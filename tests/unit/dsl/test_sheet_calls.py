# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.sheet()`` and ``design.title_block()`` (capability design-dsl, "Drawing sheet and title block in
the DSL"; change c0074). The names and values are made up for these tests."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, drawing_sheet_source, mm, to_model
from fenolite.model import canonical
from fenolite.model.presentation import SheetFrameRef, TitleBlock

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"


def blink() -> Design:
    design = runpy.run_path(str(BLINK))["design"]
    assert isinstance(design, Design)
    return design


def test_sheet_and_title_block_in_the_model() -> None:
    d = blink()
    d.sheet("A3", drawing_sheet="frames/company.kicad_wks")
    d.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "X1"})
    board = to_model(d).board
    assert board is not None
    assert board.sheet == SheetFrameRef("A3", drawing_sheet="blink.kicad_wks")
    assert board.title_block == TitleBlock(title="Blink", revision="B", params={"PROJECT_CODE": "X1"})
    assert drawing_sheet_source(d) == "frames/company.kicad_wks"
    assert "frames" not in "".join(canonical.dump_texts(to_model(d)).values())


def test_design_without_the_calls_is_unchanged() -> None:
    plain = to_model(blink()).board
    assert plain is not None and plain.sheet is None and plain.title_block is None
    assert drawing_sheet_source(blink()) is None


def test_paper_only_and_specification() -> None:
    d = blink()
    d.sheet("Letter", portrait=True)
    assert to_model(d).board.sheet == SheetFrameRef("Letter", portrait=True)  # type: ignore[union-attr]
    assert drawing_sheet_source(d) is None
    d = blink()
    d.sheet(drawing_sheet="frame.sheet.toml")
    assert to_model(d).board.sheet == SheetFrameRef("A4", drawing_sheet="blink.kicad_wks")  # type: ignore[union-attr]
    assert drawing_sheet_source(d) == "frame.sheet.toml"


def test_custom_paper() -> None:
    d = blink()
    d.sheet("custom", width=mm(300), height="200mm")
    assert to_model(d).board.sheet == SheetFrameRef("custom", width=300_000_000, height=200_000_000)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("kwargs", "word"),
    [
        ({"drawing_sheet": "frame.pdf"}, "frame.pdf"),
        ({"drawing_sheet": "/abs/frame.kicad_wks"}, "inside the folder"),
        ({"drawing_sheet": "../frame.kicad_wks"}, "inside the folder"),
        ({"drawing_sheet": "a//frame.kicad_wks"}, "inside the folder"),
        ({"drawing_sheet": "C:/frame.kicad_wks"}, "inside the folder"),
        ({"drawing_sheet": 7}, "7"),
        ({"paper": "B5"}, "B5"),
        ({"paper": "custom"}, "width and height"),
        ({"paper": "custom", "width": "10mm"}, "width and height"),
        ({"paper": "A4", "width": "10mm", "height": "10mm"}, "custom"),
        ({"paper": "custom", "width": "0mm", "height": "10mm"}, "positive"),
        ({"paper": "custom", "width": 10, "height": "10mm"}, "width"),
        ({"portrait": 1}, "portrait"),
    ],
)
def test_refused_sheet(kwargs: dict[str, object], word: str) -> None:
    d = blink()
    with pytest.raises(DslError, match=word):
        d.sheet(**kwargs)  # type: ignore[arg-type]
    assert d.sheet_frame is None and d.sheet_source is None


@pytest.mark.parametrize(
    ("kwargs", "word"),
    [
        ({"title": 3}, "title"),
        ({"variables": {"1X": "a"}}, "1X"),
        ({"variables": {"A B": "a"}}, "A B"),
        ({"variables": {"A": 1}}, "A"),
        ({"variables": ["A"]}, "variables"),
    ],
)
def test_refused_title_block(kwargs: dict[str, object], word: str) -> None:
    d = blink()
    with pytest.raises(DslError, match=word):
        d.title_block(**kwargs)  # type: ignore[arg-type]
    assert d.block is None


def test_each_call_once() -> None:
    d = blink()
    d.sheet()
    d.title_block()
    with pytest.raises(DslError, match="once"):
        d.sheet("A3")
    with pytest.raises(DslError, match="once"):
        d.title_block(title="x")
    assert to_model(d).board.title_block == TitleBlock()  # type: ignore[union-attr]


def test_every_field_and_sorted_variables() -> None:
    d = blink()
    d.title_block(
        title="T",
        date="2026-01-02",
        revision="C",
        organization="Org",
        doc_id="D-1",
        responsible="R",
        approver="A",
        variables={"ZED": "1", "ALPHA": "2"},
    )
    block = to_model(d).board.title_block  # type: ignore[union-attr]
    assert block == TitleBlock("T", "2026-01-02", "C", "Org", "D-1", "R", "A", {"ALPHA": "2", "ZED": "1"})
    assert list(block.params) == ["ALPHA", "ZED"]  # type: ignore[union-attr]


def test_exported() -> None:
    assert "drawing_sheet_source" in dsl.__all__ and dsl.drawing_sheet_source is drawing_sheet_source
