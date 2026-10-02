# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Presentation layer: drawing-sheet definitions, tokens, paper sizes (capability design-model,
"Drawing sheet definitions" and "Identifiers of drawing sheets"; change c0012)."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import _schema
import pytest

from fenolite.core.ids import derived_id, new_id
from fenolite.model import canonical
from fenolite.model.board import Board
from fenolite.model.design import Design
from fenolite.model.presentation import (
    PAPER_SIZES,
    SHEET_TOKENS,
    DrawingSheet,
    SheetBitmap,
    SheetFrameRef,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
    SheetToken,
    TitleBlock,
    join_tokens,
    split_tokens,
)

MM = 1_000_000
SETUP = SheetSetup((1_500_000, 1_500_000), 150_000, 150_000, 10 * MM, 10 * MM, 10 * MM, 10 * MM)


def test_tokens_split() -> None:
    assert split_tokens("Rev {revision} lot {param:LOT_NO} {{x}}") == (
        "Rev ",
        SheetToken("revision"),
        " lot ",
        SheetToken("LOT_NO", param=True),
        " {x}",
    )


@pytest.mark.parametrize("text", ["{owner}", "{param:9X}"])
def test_unknown_token_refused(text: str) -> None:
    with pytest.raises(ValueError, match=text.strip("{}").replace("param:", "")):
        split_tokens(text)


@pytest.mark.parametrize("text", ["{title", "a } b", "{param:}", "{param:A B}"])
def test_malformed_tokens_refused(text: str) -> None:
    with pytest.raises(ValueError):
        split_tokens(text)


@pytest.mark.parametrize("name", sorted(SHEET_TOKENS))
def test_every_token_name(name: str) -> None:
    assert split_tokens(f"{{{name}}}") == (SheetToken(name),)


@pytest.mark.parametrize("text", ["", "plain", "{{}}", "{title}/{sheets}", "a {{b}} {param:X_1}c"])
def test_join_is_the_inverse_of_split(text: str) -> None:
    assert join_tokens(split_tokens(text)) == text


def test_token_count() -> None:
    assert len(SHEET_TOKENS) == 11


def test_paper_sizes_are_exact() -> None:
    assert PAPER_SIZES["A4"] == (210_000_000, 297_000_000)
    assert PAPER_SIZES["Letter"] == (215_900_000, 279_400_000)
    assert PAPER_SIZES["Tabloid"] == (279_400_000, 431_800_000)
    assert set(PAPER_SIZES) == {"A0", "A1", "A2", "A3", "A4", "A5", "Letter", "Legal", "Tabloid"}
    assert all(type(v) is int for size in PAPER_SIZES.values() for v in size)


def test_item_order_survives_the_canonical_form() -> None:
    items = (
        SheetText("A", SheetPoint()),
        SheetShape("rect", SheetPoint(), SheetPoint()),
        SheetShape("line", SheetPoint(), SheetPoint()),
        SheetBitmap(SheetPoint(), "iVBORw0KGgo="),
    )
    sheet = DrawingSheet(id=derived_id("wks", "template", "t"), name="t", setup=SETUP, items=items)
    loaded = canonical.loads(canonical.dumps(sheet), DrawingSheet)
    assert [type(i) for i in loaded.items] == [SheetText, SheetShape, SheetShape, SheetBitmap]
    assert [getattr(i, "kind", None) for i in loaded.items] == [None, "rect", "line", None]
    assert loaded == sheet
    assert canonical.dumps(loaded) == canonical.dumps(sheet)


def test_full_values_round_trip() -> None:
    text = SheetText(
        "{title}", SheetPoint("lt", 5 * MM, 7 * MM), size=(2 * MM, 2 * MM), bold=True, italic=True,
        justify="center", vjustify="top", rotation=90_000_000, max_len=80 * MM, max_height=5 * MM,
        repeat=SheetRepeat(3, 0, 5 * MM, 0), scope="first_only", name="t", comment="c",
    )  # fmt: skip
    shape = SheetShape("line", SheetPoint("lb"), SheetPoint("rt", MM, MM), width=350_000, scope="not_first")
    sheet = DrawingSheet(id=derived_id("wks", "template", "f"), name="f", setup=SETUP, items=(text, shape))
    assert canonical.loads(canonical.dumps(sheet), DrawingSheet) == sheet


def test_definitions_are_immutable() -> None:
    point = SheetPoint("lt", 1, 2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        point.x = 3  # type: ignore[misc]


def test_float_refused() -> None:
    with pytest.raises(TypeError, match="floats"):
        canonical.dumps(SheetPoint("lt", 1.5, 0))  # type: ignore[arg-type]


def test_prefix_accepted() -> None:
    assert new_id("wks", random.Random(1)).startswith("wks_")
    with pytest.raises(ValueError):
        new_id("wkx", random.Random(1))


# -- board fields, layer files, schemas and validation (task 4.2)


PRESENTATION_CODES = ("model.sheet-", "model.param-")


def _design(sheet: SheetFrameRef | None = None, block: TitleBlock | None = None) -> Design:
    design = Design.new("p", seed=3)
    assert design.board is not None
    return dataclasses.replace(
        design, board=dataclasses.replace(design.board, sheet=sheet, title_block=block)
    )


def test_board_carries_the_sheet_and_title_block(tmp_path: Path) -> None:
    sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")
    block = TitleBlock(title="Bench", params={"LOT": "7"})
    canonical.dump_dir(_design(sheet, block), tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.board is not None
    assert (loaded.board.sheet, loaded.board.title_block) == (sheet, block)
    data = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))
    assert data["sheet"] == {"paper": "A3", "drawing_sheet": "frame.kicad_wks"}
    assert data["title_block"] == {"title": "Bench", "params": {"LOT": "7"}}


def test_board_documents_without_presentation_fields_load() -> None:
    text = canonical.dumps(Board(id=new_id("brd", random.Random(2))))
    assert "sheet" not in text and "title_block" not in text
    board = canonical.loads(text, Board)
    assert board.sheet is None and board.title_block is None
    assert _schema.validate(json.loads(text), _schema.load("fenolite.model.v0/board.json")) == []


def test_sheets_are_not_layer_content(tmp_path: Path) -> None:
    written = canonical.dump_dir(_design(SheetFrameRef("A4", drawing_sheet="frame.kicad_wks")), tmp_path)
    assert sorted(p.name for p in written) == sorted(name for name, _, _ in canonical.LAYER_FILES)
    for path in written:
        assert "setup" not in json.loads(path.read_text(encoding="utf-8"))


def test_float_rejected_in_a_sheet_document() -> None:
    sheet = DrawingSheet(
        id=derived_id("wks", "template", "f"),
        name="f",
        setup=SETUP,
        items=(SheetText("A", SheetPoint("lt", 1, 2)),),
    )
    data = json.loads(canonical.dumps(sheet))
    schema = _schema.load("fenolite.model.v0/drawing_sheet.json")
    assert _schema.validate(data, schema) == []
    data["items"][0]["pos"]["x"] = 1.5
    problems = _schema.validate(data, schema)
    assert problems and all("/items/0" in p for p in problems)


@pytest.mark.parametrize(
    ("sheet", "block", "code"),
    [
        (SheetFrameRef("A4", drawing_sheet="/srv/frames/frame.kicad_wks"), None, "model.sheet-path"),
        (SheetFrameRef("A4", drawing_sheet="C:\\\\frames\\\\frame.kicad_wks"), None, "model.sheet-path"),
        (SheetFrameRef("A4", drawing_sheet="../frame.kicad_wks"), None, "model.sheet-path"),
        (SheetFrameRef("A4", drawing_sheet="${KIPRJMOD}/../f.kicad_wks"), None, "model.sheet-path"),
        (SheetFrameRef("custom", width=279_400_000, height=215_900_000), None, "model.sheet-size"),
        (SheetFrameRef("custom", width=300_000_000), None, "model.sheet-size"),
        (
            SheetFrameRef("custom", portrait=True, width=300_000_000, height=200_000_000),
            None,
            "model.sheet-size",
        ),
        (SheetFrameRef("A4", width=300_000_000), None, "model.sheet-size"),
        (None, TitleBlock(params={"LOT NO": "7"}), "model.param-name"),
    ],
)
def test_presentation_values_validated(
    sheet: SheetFrameRef | None, block: TitleBlock | None, code: str
) -> None:
    found = [
        i for i in _design(sheet, block).validate() if i.code.startswith(("model.sheet-", "model.param-"))
    ]
    assert [i.code for i in found] == [code]
    assert all(i.severity == "error" for i in found)
    if code == "model.param-name":
        assert "LOT NO" in found[0].message


def test_valid_presentation() -> None:
    design = _design(
        SheetFrameRef("A3", drawing_sheet="${KIPRJMOD}/frame.kicad_wks"), TitleBlock(params={"LOT_NO": "7"})
    )
    assert not [i for i in design.validate() if i.code.startswith(PRESENTATION_CODES)]
    custom = _design(SheetFrameRef("custom", width=300_000_000, height=200_000_000))
    assert not [i for i in custom.validate() if i.code.startswith("model.sheet-")]
