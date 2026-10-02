# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Literal expectations of the semantic drawing-sheet probes (c0012 Decision 16), computed by hand from
the numbers of the authored probe sheets and three rules:

- corner (``H-K-WKS-CORNER``): a point is an offset from its corner of the margin box, positive toward
  the interior; no corner atom means the right-bottom corner;
- repeat (``H-K-WKS-REPEAT``): copy i is offset by i steps in the same corner frame; copies stop at the
  count or at the first copy whose start point leaves the margin box; a one-letter text steps through
  the alphabet and a decimal-integer text adds the label step per copy;
- scope (``H-K-WKS-PAGE1``): the probe sheets that use these expectations hold no scoped item.

The page size is the one read from KiCad's SVG, so no size table of KiCad is copied. Every probe sheet
has margins of 10 mm and a setup text size of 1.5 mm. ``tests/unit/templates/test_layout.py`` checks
that ``fenolite.templates.layout`` reproduces every entry (task 8.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from _sheet_bench import Expected

from fenolite.model.presentation import SheetFrameRef, TitleBlock

D = Decimal
MARGIN = D(10)
TEXT_SIZE = D("1.5")


@dataclass(frozen=True)
class Item:
    """One text item of a probe sheet, as written in the fixture (mm)."""

    text: str
    corner: str
    x: Decimal
    y: Decimal
    count: int = 1
    step_x: Decimal = D(0)
    step_y: Decimal = D(0)
    label_step: int = 1


def place(corner: str, x: Decimal, y: Decimal, width: Decimal, height: Decimal) -> tuple[Decimal, Decimal]:
    """The page point of ``(x, y)`` from ``corner`` (``H-K-WKS-CORNER``)."""
    px = MARGIN + x if corner in ("lt", "lb") else width - MARGIN - x
    py = MARGIN + y if corner in ("lt", "rt") else height - MARGIN - y
    return px, py


def label(text: str, k: int, step: int) -> str:
    if len(text) == 1 and text.isalpha():
        return chr(ord(text) + k * step)
    if text.isdigit():
        return str(int(text) + k * step)
    return text


def copies(item: Item, width: Decimal, height: Decimal) -> list[Expected]:
    found: list[Expected] = []
    for k in range(item.count):
        px, py = place(item.corner, item.x + k * item.step_x, item.y + k * item.step_y, width, height)
        if not (MARGIN <= px <= width - MARGIN and MARGIN <= py <= height - MARGIN):
            break
        found.append(Expected(label(item.text, k, item.label_step), px, py, TEXT_SIZE))
    return found


TITLE_BLOCK = (
    '(title_block (title "Bench") (date "2026-10-02") (rev "B") (company "Lab")'
    ' (comment 1 "DOC-1") (comment 2 "Ann") (comment 3 "Bob"))'
)
"""The title block of the probe boards that resolve variables."""
TITLE = TitleBlock(
    title="Bench", date="2026-10-02", revision="B", organization="Lab", doc_id="DOC-1", responsible="Ann",
    approver="Bob",
)  # fmt: skip
"""The same title block in the model, for boards written by ``write_board`` (task 6.3)."""
PARAMETER = ("LOT", "7")
"""The project text variable of ``wks-tokens``."""
RESOLVED = {
    "${TITLE}": "Bench",
    "${COMMENT1}": "DOC-1",
    "${REVISION}": "B",
    "${#}": "1",
    "${##}": "1",
    "${ISSUE_DATE}": "2026-10-02",
    "${COMPANY}": "Lab",
    "${COMMENT2}": "Ann",
    "${COMMENT3}": "Bob",
    "${FILENAME}": "board.kicad_pcb",
    "${PAPER}": "A4",
    "${LOT}": "7",
    "Title: %T": "Title: Bench",
    "Rev: %R": "Rev: B",
}
"""What KiCad draws for each variable text on an A4 probe board named ``board.kicad_pcb``."""

ITEMS: dict[str, tuple[Item, ...]] = {
    "wks-corners": (
        Item("LT", "lt", D(30), D(20)),
        Item("LB", "lb", D(30), D(20)),
        Item("RT", "rt", D(30), D(20)),
        Item("RB", "rb", D(30), D(20)),
        Item("DEF", "rb", D(60), D(40)),
    ),
    "wks-repeat": (
        Item("Repeat", "lt", D(100), D(100)),
        Item("A", "lt", D(5), D(25), count=10, step_y=D(50)),
        Item("1", "lt", D(20), D(5), count=12, step_x=D(20)),
        Item("Q", "lt", D(15), D(25), count=3, step_y=D(20)),
    ),
    "wks-percent": (
        Item("Percent", "lt", D(20), D(20)),
        Item("Title: %T", "lt", D(20), D(30)),
        Item("Rev: %R", "lt", D(20), D(40)),
    ),
    "wks-tokens": (
        Item("Tokens", "lt", D(20), D(20)),
        *(
            Item(text, "lt", D(20), D(30 + 6 * i))
            for i, text in enumerate(
                (
                    "${TITLE}",
                    "${COMMENT1}",
                    "${REVISION}",
                    "${#}",
                    "${##}",
                    "${ISSUE_DATE}",
                    "${COMPANY}",
                    "${COMMENT2}",
                    "${COMMENT3}",
                    "${FILENAME}",
                    "${PAPER}",
                    "${LOT}",
                )
            )
        ),  # fmt: skip
    ),
}
"""The text items of each semantic probe sheet, as in the fixtures."""

REPEAT_LABELS = {
    "A4": ["Repeat", "A", "B", "C", "D", *map(str, range(1, 13)), "Q", "R", "S"],
    "A3": ["Repeat", "A", "B", "C", "D", "E", "F", *map(str, range(1, 13)), "Q", "R", "S"],
}
"""The drawn texts of ``probe_repeat`` per page, counted by hand (A4 landscape margin box height 190 mm,
A3 277 mm; the number row ends at x = 10 + 20 + 11 × 20 = 250 mm on both)."""


def expected(probe: str, width: Decimal, height: Decimal) -> list[Expected]:
    """The predicted texts of ``probe`` on a ``width`` × ``height`` mm page, variables resolved."""
    found: list[Expected] = []
    for item in ITEMS[probe]:
        for e in copies(item, width, height):
            found.append(Expected(RESOLVED.get(e.text, e.text), e.x, e.y, e.height))
    return found


RESOLUTION_LINE = (D("60.000"), D(40), D(70), D(40))
"""``probe_resolution``'s line, start written 50.0006 mm and truncated to 50.000 mm (S-0035,
``H-K-WKS-RES``), ``ltcorner``, margins 10 mm."""
RESOLUTION_TOLERANCE = D("0.0001")

PAPERS: dict[str, tuple[str, Decimal, Decimal, bool]] = {
    "a0": ('(paper "A0")', D(1189), D(841), False),
    "a1": ('(paper "A1")', D(841), D(594), False),
    "a2": ('(paper "A2")', D(594), D(420), False),
    "a3": ('(paper "A3")', D(420), D(297), False),
    "a4": ('(paper "A4")', D(297), D(210), False),
    "a5": ('(paper "A5")', D(210), D(148), False),
    "a4-portrait": ('(paper "A4" portrait)', D(210), D(297), False),
    "letter": ('(paper "User" 279.4 215.9)', D("279.4"), D("215.9"), True),
    "legal": ('(paper "User" 355.6 215.9)', D("355.6"), D("215.9"), True),
    "tabloid": ('(paper "User" 431.8 279.4)', D("431.8"), D("279.4"), True),
    "custom": ('(paper "User" 300 200)', D(300), D(200), True),
}
"""Paper probes: the board's ``paper`` child and the page it must give (width × height, mm), exact for
the ``User`` form and within 0.05 mm for named sizes (A0 to A4 from S-0077, A5 and the US sizes from
S-0079; landscape unless ``portrait``)."""
PAPER_TOLERANCE = D("0.05")
_MM = 1_000_000
PAPER_REFS: dict[str, SheetFrameRef] = {
    **{f"a{n}": SheetFrameRef(f"A{n}") for n in range(6)},  # type: ignore[misc]
    "a4-portrait": SheetFrameRef("A4", portrait=True),
    "letter": SheetFrameRef("Letter"),
    "legal": SheetFrameRef("Legal"),
    "tabloid": SheetFrameRef("Tabloid"),
    "custom": SheetFrameRef("custom", width=300 * _MM, height=200 * _MM),
    "custom-mil": SheetFrameRef("custom", width=300 * _MM, height=200 * _MM),
    "custom-fraction": SheetFrameRef("custom", width=300_500_000, height=200_250_000),
}
"""The ``Board.sheet`` of each paper probe's board, written by ``write_board`` (task 6.3); its ``paper``
child is the fragment of ``PAPERS`` or ``PAPERS_MIL``."""

MIL = D("0.0254")
PAPERS_MIL: dict[str, tuple[str, Decimal, Decimal]] = {
    "custom-mil": ('(paper "User" 300 200)', 11811 * MIL, 7874 * MIL),
    "custom-fraction": ('(paper "User" 300.5 200.25)', 11830 * MIL, 7883 * MIL),
}
"""``H-K-PCB-PAPER-2``: the ``User`` page is each dimension truncated to a whole mil (0.0254 mm), as
measured on 9.0.9 and 10.0.6 on 2026-10-02 (300 mm is 11811.02 mil, drawn 299.9994 mm; 300.5 mm is
11830.7 mil, drawn 300.4820 mm, so it is truncated and not rounded). Compared exactly."""

RESOLUTION_EXACT_X = D("60.0006")
"""``H-K-WKS-RES-2``: the start of ``probe_resolution``'s line as KiCad draws it (no truncation)."""

__all__ = [
    "ITEMS",
    "PAPERS",
    "PAPERS_MIL",
    "PAPER_TOLERANCE",
    "PARAMETER",
    "REPEAT_LABELS",
    "RESOLUTION_EXACT_X",
    "RESOLUTION_LINE",
    "RESOLUTION_TOLERANCE",
    "RESOLVED",
    "TITLE_BLOCK",
    "Item",
    "expected",
]
