# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board paper and title block as editable projections (capability kicad-file-backend, "Paper and title
block on boards", MODIFIED "Created board header", "Projected fields on write" and "Board read issue
codes", and kicad-slots "Slot source for model entities"; change c0012)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import FIXTURE, board

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import (
    ISSUE_CODES,
    TITLE_BLOCK_FIELDS,
    paper_node,
    project_paper,
    project_title_block,
    read_board,
    title_block_node,
    write_board,
)
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_fragment
from fenolite.backends.kicad.slots import from_ext
from fenolite.core.errors import Issue
from fenolite.model.base import Opaque
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef, TitleBlock

TWO_LAYER = FIXTURE.read_text(encoding="utf-8")
HEADER = ["version", "generator", "generator_version"]


def with_paper(text: str, paper: str) -> str:
    return text.replace('(paper "A4")', paper, 1)


def heads(text: str) -> list[str]:
    return [c.name for c in parse(text).nodes()]


def root_child(text: str, name: str) -> Node:
    found = parse(text).find(name)
    assert found is not None
    return found


def created(sheet: SheetFrameRef | None = None, block: TitleBlock | None = None) -> Design:
    design = Design.new("sheet", seed=4)
    assert design.board is not None
    board_ = dataclasses.replace(design.board, layers=created_layers(2), sheet=sheet, title_block=block)
    return dataclasses.replace(design, board=board_)


# -- reading (task 6.1)


def test_named_paper_read() -> None:
    design = read_board(with_paper(TWO_LAYER, '(paper "A3" portrait)'))
    assert design.board is not None and design.board.sheet == SheetFrameRef("A3", portrait=True)
    slots = from_ext(design.board.ext["kicad"])
    assert any(isinstance(s, Opaque) and s.fragment == '(paper "A3" portrait)' for s in slots)


@pytest.mark.parametrize(
    ("paper", "sheet"),
    [
        ('(paper "User" 215.9 279.4)', SheetFrameRef("Letter", portrait=True)),
        ('(paper "User" 279.4 215.9)', SheetFrameRef("Letter")),
        ('(paper "User" 355.6 215.9)', SheetFrameRef("Legal")),
        ('(paper "User" 431.8 279.4)', SheetFrameRef("Tabloid")),
        ('(paper "User" 300 200)', SheetFrameRef("custom", width=300_000_000, height=200_000_000)),
        ('(paper "A5")', SheetFrameRef("A5")),
    ],
)
def test_paper_forms_read(paper: str, sheet: SheetFrameRef) -> None:
    design = read_board(with_paper(TWO_LAYER, paper))
    assert design.board is not None and design.board.sheet == sheet


@pytest.mark.parametrize("paper", ['(paper "USLetter")', '(paper "B")', '(paper "User" 300.0000001 200)'])
def test_unmodelled_paper_is_an_info(paper: str) -> None:
    issues: list[Issue] = []
    design = read_board(with_paper(TWO_LAYER, paper), issues=issues)
    assert design.board is not None and design.board.sheet is None
    assert [i.code for i in issues] == ["kicad.board.paper-unmodelled"]
    assert ISSUE_CODES["kicad.board.paper-unmodelled"] == "info"


def test_board_without_paper_or_title_block() -> None:
    text = TWO_LAYER.replace('\t(paper "A4")\n', "")
    design = read_board(text)
    assert design.board is not None and design.board.sheet is None and design.board.title_block is None


def test_title_block_projected() -> None:
    node = parse_fragment(
        '(title_block (title "A") (date "2026-10-02") (rev "1") (company "Lab") (comment 1 "D-1")'
        ' (comment 2 "Ann") (comment 3 "Bob") (comment 4 "keep") (frobnicate 1))'
    )
    assert isinstance(node, Node)
    assert project_title_block(node) == TitleBlock(
        title="A", date="2026-10-02", revision="1", organization="Lab", doc_id="D-1", responsible="Ann",
        approver="Bob",
    )  # fmt: skip
    assert list(TITLE_BLOCK_FIELDS) == [
        "title",
        "date",
        "rev",
        "company",
        "comment 1",
        "comment 2",
        "comment 3",
    ]


# -- writing (task 6.2)


def test_created_head_set_without_title_block() -> None:
    nine = write_board(created(), target=9).text
    assert heads(nine) == [
        "version",
        "generator",
        "generator_version",
        "general",
        "paper",
        "layers",
        "setup",
        "net",
    ]
    assert dumps(root_child(nine, "paper"), style="compact") == '(paper "A4")'


def test_created_board_with_a_tabloid_sheet() -> None:
    ten = write_board(created(SheetFrameRef("Tabloid"), TitleBlock(title="Bench")), target=10).text
    assert heads(ten) == [*HEADER, "general", "paper", "title_block", "layers", "setup"]
    assert dumps(root_child(ten, "paper"), style="compact") == '(paper "User" 431.8 279.4)'


@pytest.mark.parametrize(
    ("sheet", "text"),
    [
        (None, '(paper "A4")'),
        (SheetFrameRef("A3", portrait=True), '(paper "A3" portrait)'),
        (SheetFrameRef("Letter"), '(paper "User" 279.4 215.9)'),
        (SheetFrameRef("Letter", portrait=True), '(paper "User" 215.9 279.4)'),
        (SheetFrameRef("custom", width=300_000_000, height=200_000_000), '(paper "User" 300 200)'),
    ],
)
def test_paper_node(sheet: SheetFrameRef | None, text: str) -> None:
    assert dumps(paper_node(sheet), style="compact") == text
    node = paper_node(sheet)
    assert project_paper(node) == (sheet or SheetFrameRef("A4"))


def test_title_block_node_order() -> None:
    block = TitleBlock(approver="Bob", title="T", doc_id="D", organization="Lab")
    assert dumps(title_block_node(block), style="compact") == (
        '(title_block (title "T") (company "Lab") (comment 1 "D") (comment 3 "Bob"))'
    )


def test_paper_edited_on_a_read_board() -> None:
    design = read_board(TWO_LAYER)
    assert design.board is not None and design.board.sheet == SheetFrameRef("A4")
    board_ = dataclasses.replace(design.board, sheet=SheetFrameRef("A3"))
    result = write_board(dataclasses.replace(design, board=board_), target=9)
    assert result.issues == ()
    source, written = heads(TWO_LAYER), heads(result.text)
    assert written.index("paper") == source.index("paper")
    assert dumps(root_child(result.text, "paper"), style="compact") == '(paper "A3")'


def test_unmodelled_paper_kept() -> None:
    text = with_paper(TWO_LAYER, '(paper "USLetter")')
    design = read_board(text)
    written = write_board(design, target=9).text
    assert dumps(root_child(written, "paper"), style="compact") == '(paper "USLetter")'


def test_title_block_edit_touches_only_the_title_block() -> None:
    design = read_board(TWO_LAYER)
    assert design.board is not None
    board_ = dataclasses.replace(design.board, title_block=TitleBlock(title="Bench"))
    written = write_board(dataclasses.replace(design, board=board_), target=9).text
    names = heads(written)
    assert names[names.index("paper") + 1] == "title_block"
    assert dumps(root_child(written, "title_block"), style="compact") == '(title_block (title "Bench"))'
    same = parse(written).with_children(
        c for c in parse(written).children if not (isinstance(c, Node) and c.name == "title_block")
    )
    unchanged = write_board(design, target=9).text
    assert dumps(same, style="kicad") == unchanged


def test_title_block_projected_and_edited_in_place() -> None:
    block = '(title_block (title "A") (rev "1") (comment 4 "keep"))'
    text = TWO_LAYER.replace('\t(paper "A4")\n', f'\t(paper "A4")\n\t{block}\n')
    design = read_board(text)
    assert design.board is not None
    assert design.board.title_block == TitleBlock(title="A", revision="1")
    edited = dataclasses.replace(design.board.title_block, title="B", organization="Lab")
    board_ = dataclasses.replace(design.board, title_block=edited)
    written = write_board(dataclasses.replace(design, board=board_), target=9).text
    assert dumps(root_child(written, "title_block"), style="compact") == (
        '(title_block (title "B") (rev "1") (company "Lab") (comment 4 "keep"))'
    )
    before = [c for c in parse(write_board(design, target=9).text).children if not _is_title(c)]
    after = [c for c in parse(written).children if not _is_title(c)]
    assert before == after


def test_emptied_field_removed_and_none_keeps_the_rest() -> None:
    block = '(title_block (title "A") (rev "1") (comment 4 "keep"))'
    text = TWO_LAYER.replace('\t(paper "A4")\n', f'\t(paper "A4")\n\t{block}\n')
    design = read_board(text)
    assert design.board is not None
    cleared = dataclasses.replace(design.board, title_block=None)
    written = write_board(dataclasses.replace(design, board=cleared), target=9).text
    assert dumps(root_child(written, "title_block"), style="compact") == '(title_block (comment 4 "keep"))'


def test_unchanged_projection_keeps_its_fragment() -> None:
    block = '(title_block (title "A")  (rev "1"))'
    text = with_paper(TWO_LAYER, '(paper "User" 279.40 215.90)').replace(
        '\t(paper "User" 279.40 215.90)\n', f'\t(paper "User" 279.40 215.90)\n\t{block}\n'
    )
    design = read_board(text)
    written = write_board(design, target=9).text
    assert dumps(root_child(written, "paper"), style="compact") == '(paper "User" 279.40 215.90)'


def _is_title(child: object) -> bool:
    return isinstance(child, Node) and child.name == "title_block"


def test_board_helper_unaffected() -> None:
    assert '(paper "A4")' in board()
